"""
Automated tests for Terminal Observability and Traffic Simulation.
Kiểm thử tự động tính năng theo dõi lưu lượng, xuất bảng thống kê tải
và tính năng bắn tải mô phỏng của scripts/test_traffic.py.
Chạy độc lập: `python tests/test_traffic_sim.py` hoặc `pytest tests/test_traffic_sim.py`
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Tuple

# Thêm thư mục gốc vào sys.path để chạy trực tiếp
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import aiohttp
from aiohttp import web

from balancers.base import Backend
from balancers.consistent_hash import ConsistentHashBalancer
from proxy import create_app
from scripts.test_traffic import run_traffic_batch, send_single_request


async def start_mock_backend(node_id: str) -> Tuple[web.AppRunner, int]:
    """Khởi động mock HTTP backend trên cổng ngẫu nhiên do OS cấp (port 0)."""
    state = {"is_alive": True}

    async def handle_healthz(request: web.Request) -> web.Response:
        status = 200 if state["is_alive"] else 500
        return web.json_response({"status": "UP" if state["is_alive"] else "DOWN", "node": node_id}, status=status)

    async def handle_chaos_down(request: web.Request) -> web.Response:
        state["is_alive"] = False
        return web.json_response({"is_alive": False, "node": node_id})

    async def handle_chaos_up(request: web.Request) -> web.Response:
        state["is_alive"] = True
        return web.json_response({"is_alive": True, "node": node_id})

    async def handler(request: web.Request) -> web.Response:
        if not state["is_alive"]:
            return web.json_response({"error": "node down"}, status=500)
        headers = {"X-Backend-Node": node_id}
        return web.json_response({"node": node_id, "path": request.path}, headers=headers)

    app = web.Application()
    app.router.add_get("/healthz", handle_healthz)
    app.router.add_post("/chaos/down", handle_chaos_down)
    app.router.add_post("/chaos/up", handle_chaos_up)
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port


async def start_proxy_server(balancer) -> Tuple[web.AppRunner, str]:
    """Khởi động Reverse Proxy trên cổng ngẫu nhiên."""
    cfg = {
        "port": 0,
        "timeout": 2.0,
        "max_retries": 2,
        "quarantine_seconds": 2.0,
        "backends": [],
    }
    app = create_app(config=cfg, balancer=balancer)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    proxy_port = site._server.sockets[0].getsockname()[1]
    proxy_url = f"http://127.0.0.1:{proxy_port}"
    return runner, proxy_url


def test_lean_proxy_and_algo_header():
    """Kiểm tra proxy tinh gọn: trả về header X-Balancer và không còn endpoint /_stats."""
    async def _test():
        runner1, port1 = await start_mock_backend("mock-1")
        try:
            backends = [Backend(id="mock-1", host="127.0.0.1", port=port1, weight=1)]
            balancer = ConsistentHashBalancer(backends)
            proxy_runner, proxy_url = await start_proxy_server(balancer)

            try:
                async with aiohttp.ClientSession() as session:
                    # Gửi 1 request kiểm tra header X-Balancer và X-Balancer-Decision
                    async with session.get(f"{proxy_url}/api/test", headers={"X-Forwarded-For": "10.0.0.1"}) as r:
                        assert r.status == 200
                        assert r.headers.get("X-Balancer") == "consistent_hash"
                        assert r.headers.get("X-Backend-Node") == "mock-1"
                        assert "X-Balancer-Decision" in r.headers
                        decision = r.headers.get("X-Balancer-Decision")
                        assert len(decision.split("|")) == 5

                    # Kiểm tra endpoint /_stats không còn được proxy xử lý nội bộ
                    async with session.get(f"{proxy_url}/_stats") as r:
                        data = await r.json()
                        # Được forward sang mock server (không phải json trả về total_requests của proxy cũ)
                        assert "total_requests" not in data
            finally:
                await proxy_runner.cleanup()
        finally:
            await runner1.cleanup()

    asyncio.run(_test())
    print("  [PASS] test_lean_proxy_and_algo_header")



def test_traffic_batch_simulation():
    """Kiểm thử script bắn tải run_traffic_batch phân bổ thành công 100% qua proxy."""
    async def _test():
        runner1, port1 = await start_mock_backend("mock-1")
        runner2, port2 = await start_mock_backend("mock-2")

        try:
            backends = [
                Backend(id="mock-1", host="127.0.0.1", port=port1, weight=1),
                Backend(id="mock-2", host="127.0.0.1", port=port2, weight=1),
            ]
            balancer = ConsistentHashBalancer(backends)
            proxy_runner, proxy_url = await start_proxy_server(balancer)

            try:
                # Gửi 20 request với mức đồng thời 4
                results = await run_traffic_batch(
                    target_url=f"{proxy_url}/api/order",
                    num_requests=20,
                    concurrency=4,
                )

                assert len(results) == 20
                # Tất cả phải thành công 100%
                successes = [r for r in results if r["success"] and r["status"] == 200]
                assert len(successes) == 20

                # Cả hai node đều nhận được lưu lượng
                nodes_hit = {r["node"] for r in results}
                assert "mock-1" in nodes_hit
                assert "mock-2" in nodes_hit

            finally:
                await proxy_runner.cleanup()
        finally:
            await runner1.cleanup()
            await runner2.cleanup()

    asyncio.run(_test())
    print("  [PASS] test_traffic_batch_simulation")


def test_traffic_simulation_during_node_crash():
    """Kiểm chứng kịch bản Chaos: Khi 1 node bị sập, script bắn tải vẫn nhận 100% 200 OK (Immediate Retry)."""
    async def _test():
        runner1, port1 = await start_mock_backend("mock-1")
        runner2, port2 = await start_mock_backend("mock-2")

        try:
            backends = [
                Backend(id="mock-1", host="127.0.0.1", port=port1, weight=1),
                Backend(id="mock-2", host="127.0.0.1", port=port2, weight=1),
            ]
            balancer = ConsistentHashBalancer(backends)
            proxy_runner, proxy_url = await start_proxy_server(balancer)

            try:
                # Làm sập mock-1 ngay lập tức
                await runner1.cleanup()

                # Bắn 10 request qua Proxy
                results = await run_traffic_batch(
                    target_url=f"{proxy_url}/api/failover",
                    num_requests=10,
                    concurrency=2,
                )

                # 100% request vẫn phải trả về 200 OK nhờ Immediate Retry sang mock-2
                assert len(results) == 10
                for r in results:
                    assert r["status"] == 200
                    assert r["node"] == "mock-2"

                # mock-1 phải bị cách ly
                assert backends[0].alive is False

            finally:
                await proxy_runner.cleanup()
        finally:
            await runner2.cleanup()

    asyncio.run(_test())
    print("  [PASS] test_traffic_simulation_during_node_crash")


def test_chaos_cli_commands():
    """Kiểm thử các lệnh điều khiển sự cố trong scripts/chaos.py (down, up, delay)."""
    async def _test():
        from scripts.chaos import send_post

        loop = asyncio.get_running_loop()
        runner1, port1 = await start_mock_backend("mock-1")
        try:
            async with aiohttp.ClientSession() as session:
                # 1. Ban đầu node hoạt động (200 OK)
                async with session.get(f"http://127.0.0.1:{port1}/healthz") as resp:
                    assert resp.status == 200

                # 2. Đánh sập node qua endpoint chaos_down
                res = await loop.run_in_executor(None, send_post, f"http://127.0.0.1:{port1}/chaos/down")
                assert res.get("is_alive") is False

                # Healthz phải trả về 500
                async with session.get(f"http://127.0.0.1:{port1}/healthz") as resp:
                    assert resp.status == 500

                # 3. Khôi phục node qua endpoint chaos_up
                res = await loop.run_in_executor(None, send_post, f"http://127.0.0.1:{port1}/chaos/up")
                assert res.get("is_alive") is True

                # Healthz phải trả về 200 trở lại
                async with session.get(f"http://127.0.0.1:{port1}/healthz") as resp:
                    assert resp.status == 200
        finally:
            await runner1.cleanup()

    asyncio.run(_test())
    print("  [PASS] test_chaos_cli_commands")


def test_render_live_dashboard():
    """Kiểm tra hàm render_live_dashboard hiển thị đầy đủ metrics, progress bars và mô hình Clockwise Interval."""
    import time
    from scripts.dashboard import render_live_dashboard
    results = [
        {"id": 0, "ip": "192.168.1.10", "node": "mock-1", "status": 200, "latency_ms": 3.0, "success": True, "algo": "consistent_hash", "decision": "mock-2#vn10|0x2f300000|0x2f3a1b0c|mock-1#vn37|0x2f41e9a0"},
        {"id": 1, "ip": "192.168.1.10", "node": "mock-1", "status": 200, "latency_ms": 2.5, "success": True, "algo": "consistent_hash", "decision": "mock-2#vn10|0x2f300000|0x2f3a1b0c|mock-1#vn37|0x2f41e9a0"},
        {"id": 2, "ip": "192.168.1.11", "node": "mock-2", "status": 200, "latency_ms": 4.0, "success": True, "algo": "consistent_hash", "decision": "mock-1#vn45|0x7a800000|0x7a89bc12|mock-2#vn14|0x7a901004"},
    ]
    output = render_live_dashboard(
        results=results,
        start_time=time.time() - 2.0,
        target_url="http://127.0.0.1:8000/api/order",
        concurrency=1,
        delay=0.5,
        ips=["192.168.1.10", "192.168.1.11"],
    )
    assert "LOAD BALANCER LIVE DASHBOARD" in output
    assert "mock-1" in output
    assert "mock-2" in output
    assert "192.168.1.10" in output
    assert "(ACTIVE | STICKY)" in output
    assert "[0x2f300000 < 0x2f3a1b0c <= 0x2f41e9a0 (mock-1#vn37)]" in output
    print("  [PASS] test_render_live_dashboard")


def test_dashboard_dynamic_recovery_when_server_up():
    """Kiểm chứng tính năng hoàn nguyên: khi server UP trở lại, dashboard lập tức hiện lại ACTIVE | STICKY."""
    import time
    from scripts.dashboard import render_live_dashboard
    # 1. Ban đầu IP 192.168.1.12 dính vào mock-2
    results = [
        {"id": 0, "ip": "192.168.1.12", "node": "mock-2", "status": 200, "latency_ms": 3.0, "success": True, "algo": "consistent_hash"},
    ]
    out1 = render_live_dashboard(results, time.time() - 1, "http://127.0.0.1:8000", 1, 0.05, ["192.168.1.12"])
    assert "(ACTIVE | STICKY)" in out1

    # 2. Node mock-2 sập -> failover sang mock-3
    results.append({"id": 1, "ip": "192.168.1.12", "node": "mock-3", "status": 200, "latency_ms": 3.0, "success": True, "algo": "consistent_hash"})
    out2 = render_live_dashboard(results, time.time() - 2, "http://127.0.0.1:8000", 1, 0.05, ["192.168.1.12"])
    assert "FAILOVER ACTIVE" in out2

    # 3. Node mock-2 hồi phục -> các request mới quay về mock-2
    for i in range(2, 9):
        results.append({"id": i, "ip": "192.168.1.12", "node": "mock-2", "status": 200, "latency_ms": 3.0, "success": True, "algo": "consistent_hash"})
    out3 = render_live_dashboard(results, time.time() - 3, "http://127.0.0.1:8000", 1, 0.05, ["192.168.1.12"])
    # Dashboard PHẢI hoàn nguyên về lại (ACTIVE | STICKY) như ban đầu!
    assert "(ACTIVE | STICKY)" in out3
    assert "FAILOVER ACTIVE" not in out3
    print("  [PASS] test_dashboard_dynamic_recovery_when_server_up")


def test_dashboard_load_events_from_log(tmp_path):
    """Kiểm tra hàm load_events_from_log đọc và parse JSON từ file access.log đúng chuẩn."""
    from scripts.dashboard import load_events_from_log
    log_file = tmp_path / "test_access.log"

    # 1. Khi file chưa tồn tại -> trả về rỗng
    assert load_events_from_log(log_file) == []

    # 2. Ghi 2 dòng log hợp lệ và 1 dòng rác
    with open(log_file, "w", encoding="utf-8") as f:
        f.write('{"ts": 100.0, "client_ip": "10.0.0.1", "node": "mock-1", "status": 200}\n')
        f.write("corrupted json line\n")
        f.write('{"ts": 101.0, "client_ip": "10.0.0.2", "node": "mock-2", "status": 200}\n')

    events = load_events_from_log(log_file)
    assert len(events) == 2
    assert events[0]["client_ip"] == "10.0.0.1"
    assert events[1]["client_ip"] == "10.0.0.2"
    print("  [PASS] test_dashboard_load_events_from_log")


def test_dashboard_down_state_when_all_nodes_fail():
    """Kiểm chứng khi server sập hết và trả 503, dashboard không còn báo sticky mà hiện DOWN | HTTP 503."""
    import time
    from scripts.dashboard import render_live_dashboard
    results = [
        {"id": 0, "ip": "192.168.1.10", "node": "mock-3", "status": 200, "latency_ms": 3.0, "success": True, "algo": "consistent_hash"},
        # Khi server sập hết: proxy ghi nhận 503 và node=None
        {"id": 1, "ip": "192.168.1.10", "node": "None", "status": 503, "latency_ms": 1.0, "success": False, "algo": "consistent_hash", "decision": "NO_HEALTHY_BACKEND"},
    ]
    output = render_live_dashboard(results, time.time() - 1, "http://127.0.0.1:8000", 1, 0.5, ["192.168.1.10"])
    assert "[DOWN | HTTP 503]" in output
    assert "(ACTIVE | STICKY)" not in output
    assert "Failed: 1" in output
    print("  [PASS] test_dashboard_down_state_when_all_nodes_fail")


if __name__ == "__main__":
    test_lean_proxy_and_algo_header()
    test_traffic_batch_simulation()
    test_traffic_simulation_during_node_crash()
    test_chaos_cli_commands()
    test_render_live_dashboard()
    test_dashboard_dynamic_recovery_when_server_up()
    test_dashboard_down_state_when_all_nodes_fail()
    print("All traffic simulation tests PASSED!")



