"""
Integration Tests for Layer 7 Reverse Proxy Engine & Passive Failover.
Chạy độc lập: `python tests/test_proxy.py` hoặc `pytest tests/test_proxy.py`
Toàn bộ test là self-contained: tự sinh mock server trên cổng động (ephemeral ports).
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
import pytest

from balancers.base import Backend
from balancers.consistent_hash import ConsistentHashBalancer
from proxy import create_app, quarantine_recovery


async def start_mock_backend(
    node_id: str,
    custom_headers: Dict[str, str] = None,
) -> Tuple[web.AppRunner, int]:
    """Khởi động mock HTTP backend trên cổng ngẫu nhiên do OS cấp (port 0)."""
    async def handler(request: web.Request) -> web.Response:
        body = await request.read()
        resp_data = {
            "node_id": node_id,
            "method": request.method,
            "path": request.path,
            "query": dict(request.query),
            "body": body.decode("utf-8") if body else "",
            "received_headers": dict(request.headers),
        }
        headers = dict(custom_headers or {})
        headers["X-Backend-Node"] = node_id
        return web.json_response(resp_data, headers=headers)

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port


async def start_proxy_server(balancer, config=None) -> Tuple[web.AppRunner, str]:
    """Khởi động Reverse Proxy trên cổng ngẫu nhiên."""
    cfg = config or {
        "port": 0,
        "timeout": 2.0,
        "max_retries": 2,
        "quarantine_seconds": 1.0,
    }
    app = create_app(cfg, balancer=balancer)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


def test_proxy_forward_get_and_post():
    """Kiểm thử chuyển tiếp thành công request GET và POST kèm query params và JSON body."""
    async def _test():
        runner1, port1 = await start_mock_backend("mock-1")
        backends = [Backend(id="mock-1", host="127.0.0.1", port=port1, weight=1)]
        lb = ConsistentHashBalancer(backends)
        proxy_runner, proxy_url = await start_proxy_server(lb)

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Test GET request with query params
                async with session.get(f"{proxy_url}/api/v1/menu?cat=pizza") as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["node_id"] == "mock-1"
                    assert data["method"] == "GET"
                    assert data["path"] == "/api/v1/menu"
                    assert data["query"] == {"cat": "pizza"}
                    assert resp.headers.get("X-Backend-Node") == "mock-1"

                # 2. Test POST request with body
                post_body = '{"food": "pho", "quantity": 2}'
                async with session.post(
                    f"{proxy_url}/api/v1/order",
                    data=post_body,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["node_id"] == "mock-1"
                    assert data["method"] == "POST"
                    assert data["path"] == "/api/v1/order"
                    assert "pho" in data["body"]
        finally:
            await proxy_runner.cleanup()
            await runner1.cleanup()

    asyncio.run(_test())
    print("  [PASS] test_proxy_forward_get_and_post")


def test_proxy_hop_by_hop_stripping():
    """Kiểm thử lọc bỏ Hop-by-Hop headers theo chuẩn RFC 7230 ở cả 2 chiều (inbound và outbound)."""
    async def _test():
        runner1, port1 = await start_mock_backend("mock-1")
        backends = [Backend(id="mock-1", host="127.0.0.1", port=port1, weight=1)]
        lb = ConsistentHashBalancer(backends)
        proxy_runner, proxy_url = await start_proxy_server(lb)

        try:
            async with aiohttp.ClientSession() as session:
                # Gửi các hop-by-hop headers từ client
                client_headers = {
                    "Connection": "keep-alive",
                    "Keep-Alive": "timeout=5",
                    "Upgrade": "test-proto",
                    "X-Custom-Client": "safe-value",
                }
                async with session.get(f"{proxy_url}/test-headers", headers=client_headers) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    received = {k.lower(): v for k, v in data["received_headers"].items()}

                    # Hop-by-hop headers không được lọt sang backend
                    assert "connection" not in received or received["connection"] != "keep-alive"
                    assert "keep-alive" not in received
                    assert "upgrade" not in received

                    # Header an toàn và Host được bảo lưu
                    assert received.get("x-custom-client") == "safe-value"
                    assert "host" in received
                    assert "x-forwarded-for" in received
        finally:
            await proxy_runner.cleanup()
            await runner1.cleanup()

    asyncio.run(_test())
    print("  [PASS] test_proxy_hop_by_hop_stripping")


def test_proxy_passive_failover_immediate_retry():
    """
    Kiểm thử cơ chế Passive Fault Detection & Immediate Retry (Fault Transparency):
    Node 1 bị ngắt kết nối đột ngột -> Proxy lập tức thử lại sang Node 2.
    Client nhận kết quả 200 OK thành công mà không nhận bất kỳ mã lỗi 502 nào.
    """
    async def _test():
        runner1, port1 = await start_mock_backend("mock-1")
        runner2, port2 = await start_mock_backend("mock-2")

        b1 = Backend(id="mock-1", host="127.0.0.1", port=port1, weight=1)
        b2 = Backend(id="mock-2", host="127.0.0.1", port=port2, weight=1)
        lb = ConsistentHashBalancer([b1, b2], vnodes=100)

        proxy_runner, proxy_url = await start_proxy_server(lb)

        try:
            # Tìm một Client IP mà consistent hash ánh xạ trúng vào mock-1
            target_ip = None
            for i in range(100):
                candidate_ip = f"192.168.1.{i}"
                if lb.get_backend(candidate_ip).id == "mock-1":
                    target_ip = candidate_ip
                    break

            assert target_ip is not None, "Không tìm được IP ánh xạ vào mock-1"
            assert lb.get_backend(target_ip).id == "mock-1"

            # Đánh sập mock-1 đột ngột (giả lập sự cố cúp nguồn/process crash)
            await runner1.cleanup()

            # Gửi request với target_ip
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{proxy_url}/api/chaos",
                    headers={"X-Forwarded-For": target_ip},
                ) as resp:
                    # Client PHẢI nhận được 200 OK nhờ cơ chế Immediate Retry sang mock-2!
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["node_id"] == "mock-2"
                    assert resp.headers.get("X-Backend-Node") == "mock-2"

            # Xác nhận mock-1 đã bị phát hiện lỗi thụ động và bị cách ly (alive = False)
            assert b1.alive is False
            assert b2.alive is True

        finally:
            await proxy_runner.cleanup()
            await runner2.cleanup()

    asyncio.run(_test())
    print("  [PASS] test_proxy_passive_failover_immediate_retry")


def test_proxy_all_backends_down():
    """Kiểm thử khi toàn bộ backends đều chết -> Trả về lỗi 502/503 có cấu trúc."""
    async def _test():
        # Dùng 2 cổng không có dịch vụ nào lắng nghe
        b1 = Backend(id="dead-1", host="127.0.0.1", port=59991)
        b2 = Backend(id="dead-2", host="127.0.0.1", port=59992)
        lb = ConsistentHashBalancer([b1, b2])

        proxy_runner, proxy_url = await start_proxy_server(lb, config={
            "port": 0,
            "timeout": 0.5,
            "max_retries": 1,
            "quarantine_seconds": 1.0,
        })

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{proxy_url}/test-down") as resp:
                    assert resp.status in (502, 503)
                    data = await resp.json()
                    assert "error" in data
        finally:
            await proxy_runner.cleanup()

    asyncio.run(_test())
    print("  [PASS] test_proxy_all_backends_down")


def test_proxy_quarantine_recovery():
    """Kiểm thử cơ chế tự động phục hồi nút sau khoảng thời gian cách ly (Quarantine Backoff)."""
    async def _test():
        b1 = Backend(id="recovering-node", host="127.0.0.1", port=9001)
        lb = ConsistentHashBalancer([b1])

        # Đánh dấu nút bị chết
        lb.update_backend_status("recovering-node", False)
        assert b1.alive is False
        assert len(lb.get_alive_backends()) == 0

        # Kích hoạt quarantine recovery với độ trễ ngắn 0.15s
        await quarantine_recovery(b1, 0.15, lb)

        # Sau khi hết thời gian cách ly, nút phải được bật lại
        assert b1.alive is True
        assert len(lb.get_alive_backends()) == 1

    asyncio.run(_test())
    print("  [PASS] test_proxy_quarantine_recovery")


if __name__ == "__main__":
    print("\n--- RUNNING REVERSE PROXY & PASSIVE FAILOVER INTEGRATION TESTS ---")
    test_proxy_forward_get_and_post()
    test_proxy_hop_by_hop_stripping()
    test_proxy_passive_failover_immediate_retry()
    test_proxy_all_backends_down()
    test_proxy_quarantine_recovery()
    print("--- ALL 5 PROXY INTEGRATION TESTS PASSED SUCCESSFULLY! ---\n")
