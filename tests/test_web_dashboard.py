"""
Unit & Integration Tests for Web Dashboard Backend Server (web_dashboard.py).
Kiểm thử toàn diện:
1. Phát hiện cổng mạng TCP (is_port_open).
2. Tính toán số liệu thống kê & phân tích log (StatsAggregator).
3. Vòng đời tiến trình & Dừng cưỡng chế tức thì (ProcessManager.force_kill).
4. REST API Endpoints: GET /api/stats, POST /api/control/traffic, POST /api/control/chaos.
5. Phục vụ trang HTML tĩnh dự phòng (Fallback Static Handler).
"""

import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Dict, Tuple

# Thêm project root vào sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import aiohttp
from aiohttp import web
import pytest

from web_dashboard import (
    ProcessManager,
    StatsAggregator,
    create_dashboard_app,
    is_port_open,
)


async def start_ephemeral_server() -> Tuple[web.AppRunner, int]:
    """Khởi tạo một HTTP server nhẹ trên cổng ngẫu nhiên do OS cấp."""
    async def hello(request):
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", hello)
    app.router.add_get("/healthz", hello)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port


async def start_dashboard_test_server(pm: ProcessManager = None, log_path: Path = None) -> Tuple[web.AppRunner, int, str]:
    """Khởi tạo Web Dashboard server trên cổng ngẫu nhiên phục vụ kiểm thử."""
    app = create_dashboard_app(pm=pm, log_path=log_path)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    return runner, port, base_url


# ==============================================================================
# 1. Kiểm thử TCP Port Probing
# ==============================================================================

def test_is_port_open():
    """Xác nhận hàm is_port_open phát hiện đúng cổng đang mở và cổng đang đóng."""
    async def _test():
        runner, port = await start_ephemeral_server()
        assert is_port_open(port) is True

        # Khi server đã tắt
        await runner.cleanup()
        await asyncio.sleep(0.05)
        assert is_port_open(port) is False

    asyncio.run(_test())


# ==============================================================================
# 2. Kiểm thử StatsAggregator (Xử lý Log & Tính toán Metrics)
# ==============================================================================

def test_stats_aggregator_metrics_calculation():
    """Kiểm tra logic tính toán RPS, tổng request, số lượng thành công/thất bại và phân bổ tải."""
    now = time.time()
    events = [
        {"ts": now - 1.0, "status": 200, "node": "mock-node-1", "algo": "round_robin"},
        {"ts": now - 2.0, "status": 200, "node": "mock-node-2", "algo": "round_robin"},
        {"ts": now - 3.0, "status": 502, "node": "None", "algo": "round_robin"},
        {"ts": now - 4.0, "status": 200, "node": "mock-node-1", "algo": "round_robin"},
        {"ts": now - 10.0, "status": 200, "node": "mock-node-3", "algo": "round_robin"},  # Ngoài cửa sổ 5s
    ]

    metrics = StatsAggregator.calculate_metrics(events)
    assert metrics["total_requests"] == 5
    assert metrics["success_count"] == 4
    assert metrics["failed_count"] == 1
    assert metrics["success_pct"] == 80.0
    # Trong 5s có 4 request -> RPS = 4 / 5.0 = 0.8
    assert metrics["rps"] == 0.8

    dist = metrics["node_distribution"]
    assert dist["mock-node-1"]["count"] == 2
    assert dist["mock-node-1"]["pct"] == 40.0
    assert dist["mock-node-2"]["count"] == 1
    assert dist["mock-node-3"]["count"] == 1
    assert dist["None"]["count"] == 1


def test_stats_aggregator_read_recent_events():
    """Kiểm tra đọc tệp JSONL log thực tế, bỏ qua dòng rác an toàn."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
        f.write('{"ts": 100, "status": 200, "node": "mock-node-1"}\n')
        f.write("DÒNG LỖI PARSE JSON KHÔNG HỢP LỆ\n")
        f.write('{"ts": 200, "status": 200, "node": "mock-node-2"}\n')
        f.write("\n")
        temp_path = Path(f.name)

    try:
        events = StatsAggregator.read_recent_events(temp_path)
        assert len(events) == 2
        assert events[0]["node"] == "mock-node-1"
        assert events[1]["node"] == "mock-node-2"
    finally:
        temp_path.unlink(missing_ok=True)


# ==============================================================================
# 3. Kiểm thử ProcessManager & Dừng Cưỡng Chế (Force Kill)
# ==============================================================================

def test_process_manager_force_kill():
    """Xác nhận ProcessManager.force_kill lập tức ngắt tiến trình con và dọn dẹp handle."""
    pm = ProcessManager()
    # Khởi tạo một tiến trình Python giả lập chạy vô hạn
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pm.traffic_proc = proc
    assert pm.traffic_proc.poll() is None

    # Gọi force_kill
    killed = pm.force_kill("traffic")
    assert killed is True
    assert pm.traffic_proc is None
    # Tiến trình con phải được kill hoàn toàn
    assert proc.poll() is not None


# ==============================================================================
# 4. Kiểm thử REST API Endpoints
# ==============================================================================

def test_api_get_stats_empty():
    """Kiểm tra endpoint GET /api/stats khi mới khởi tạo với log rỗng."""
    async def _test():
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as f:
            temp_path = Path(f.name)

        pm = ProcessManager()
        runner, port, base_url = await start_dashboard_test_server(pm=pm, log_path=temp_path)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/stats") as resp:
                    assert resp.status == 200
                    data = await resp.json()

                    assert "timestamp" in data
                    assert "active_algo" in data
                    assert "services" in data
                    assert "metrics" in data
                    assert "recent_events" in data

                    # Kiểm tra trạng thái mặc định
                    assert data["services"]["mock_servers"]["status"] == "stopped"
                    assert data["services"]["proxy"]["status"] == "stopped"
                    assert data["services"]["traffic"]["status"] == "stopped"
                    assert data["metrics"]["total_requests"] == 0
        finally:
            await runner.cleanup()
            temp_path.unlink(missing_ok=True)

    asyncio.run(_test())


def test_api_control_traffic_start_and_stop():
    """Kiểm tra API POST /api/control/traffic khởi động và dừng tiến trình sinh tải."""
    async def _test():
        pm = ProcessManager()
        runner, port, base_url = await start_dashboard_test_server(pm=pm)

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Bật Traffic (với delay lớn để tiến trình vẫn sống trong khi test)
                payload_start = {
                    "action": "start",
                    "concurrency": 1,
                    "delay": 2.0,
                    "requests": 10,
                }
                async with session.post(f"{base_url}/api/control/traffic", json=payload_start) as resp:
                    assert resp.status == 200
                    res = await resp.json()
                    assert res["status"] == "ok"
                    assert pm.traffic_proc is not None
                    assert pm.traffic_proc.poll() is None

                # 2. Tắt Traffic bằng Force Kill
                payload_stop = {"action": "stop"}
                async with session.post(f"{base_url}/api/control/traffic", json=payload_stop) as resp:
                    assert resp.status == 200
                    res = await resp.json()
                    assert res["status"] == "ok"
                    assert pm.traffic_proc is None
        finally:
            pm.stop_all()
            await runner.cleanup()

    asyncio.run(_test())


def test_api_control_algorithm_and_chaos_error_handling():
    """Kiểm tra xử lý lỗi khi Proxy hoặc Mock node đích chưa được bật."""
    async def _test():
        pm = ProcessManager()
        runner, port, base_url = await start_dashboard_test_server(pm=pm)

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Đổi thuật toán khi thiếu tham số
                async with session.post(f"{base_url}/api/control/algorithm", json={}) as resp:
                    assert resp.status == 400

                # 2. Đổi thuật toán khi Proxy :8000 chưa bật -> trả về 502 Bad Gateway
                async with session.post(f"{base_url}/api/control/algorithm", json={"algorithm": "round_robin"}) as resp:
                    assert resp.status == 502

                # 3. Tiêm chaos khi thiếu tham số
                async with session.post(f"{base_url}/api/control/chaos", json={"port": 9002}) as resp:
                    assert resp.status == 400

                # 4. Tiêm chaos tới node chưa bật -> trả về 502
                async with session.post(f"{base_url}/api/control/chaos", json={"port": 9999, "action": "down"}) as resp:
                    assert resp.status == 502
        finally:
            await runner.cleanup()

    asyncio.run(_test())


def test_api_static_fallback():
    """Kiểm tra endpoint GET / trả về trang HTML thông báo Backend sẵn sàng khi chưa có giao diện web/."""
    async def _test():
        pm = ProcessManager()
        runner, port, base_url = await start_dashboard_test_server(pm=pm)

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Kiểm tra phục vụ root / (trả về web/index.html thật hoặc fallback HTML)
                async with session.get(f"{base_url}/") as resp:
                    assert resp.status == 200
                    assert resp.content_type == "text/html"
                    text = await resp.text()
                    assert ("Load Balancer Control" in text) or ("Web Dashboard Backend" in text)

                # 2. Kiểm tra phục vụ file không tồn tại -> kích hoạt fallback HTML mặc định
                async with session.get(f"{base_url}/non_existent_page.xyz") as resp:
                    assert resp.status == 200
                    assert resp.content_type == "text/html"
                    text = await resp.text()
                    assert "Web Dashboard Backend" in text
                    assert "API Ready on Port 8001" in text
        finally:
            await runner.cleanup()

    asyncio.run(_test())


def test_mock_and_proxy_process_lifecycle():
    """Kiểm tra ProcessManager khởi động và dừng cưỡng chế Mock Servers và Proxy."""
    async def _test():
        pm = ProcessManager()
        try:
            # 1. Khởi động Mock Servers
            res_mock = await pm.start_mock()
            assert res_mock["status"] in ("ok", "already_running")
            assert is_port_open(9001) is True
            assert is_port_open(9002) is True
            assert is_port_open(9003) is True

            # 2. Khởi động Proxy
            res_proxy = await pm.start_proxy()
            assert res_proxy["status"] in ("ok", "already_running")
            assert is_port_open(8000) is True

            # 3. Dừng cưỡng chế Proxy
            assert pm.force_kill("proxy") is True
            await asyncio.sleep(0.1)
            assert is_port_open(8000) is False

            # 4. Dừng cưỡng chế Mock Servers
            assert pm.force_kill("mock") is True
            await asyncio.sleep(0.1)
            assert is_port_open(9001) is False
        finally:
            pm.stop_all()

    asyncio.run(_test())
