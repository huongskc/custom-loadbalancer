"""
Unit & Integration Tests for Round Robin Balancer (Milestone 2.2 / Milestone 5)
Chạy độc lập: `python tests/test_round_robin.py` hoặc `pytest tests/test_round_robin.py`
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
from balancers.round_robin import RoundRobinBalancer
from proxy import create_app


def create_sample_backends(count: int = 3):
    """Tạo danh sách backend mẫu phục vụ unit test."""
    return [
        Backend(id=f"node-{i}", host="127.0.0.1", port=9000 + i, weight=1)
        for i in range(1, count + 1)
    ]


# ==========================================
# 1. Unit Tests cho Thuật toán Round Robin
# ==========================================


def test_round_robin_basic_rotation():
    """Kiểm tra tính tuần tự chuẩn xác 1 -> 2 -> 3 -> 1 -> 2 -> 3."""
    backends = create_sample_backends(3)
    lb = RoundRobinBalancer(backends)

    assert lb.name == "round_robin"
    selected = [lb.get_backend().id for _ in range(9)]
    expected = [
        "node-1", "node-2", "node-3",
        "node-1", "node-2", "node-3",
        "node-1", "node-2", "node-3",
    ]
    assert selected == expected


def test_round_robin_empty_backends():
    """Trả về None khi danh sách backend rỗng."""
    lb = RoundRobinBalancer([])
    assert lb.get_backend() is None
    assert lb.get_backend("192.168.1.100") is None


def test_round_robin_all_backends_dead():
    """Trả về None khi toàn bộ backend đều bị sập (alive = False)."""
    backends = create_sample_backends(3)
    for b in backends:
        b.alive = False

    lb = RoundRobinBalancer(backends)
    assert lb.get_backend() is None


def test_round_robin_skips_dead_node():
    """Tự động bỏ qua node chết và chỉ xoay vòng giữa các node còn sống."""
    backends = create_sample_backends(3)
    lb = RoundRobinBalancer(backends)

    # Đánh sập node-2
    lb.update_backend_status("node-2", False)

    # 4 request tiếp theo chỉ được vào node-1 và node-3
    selected = [lb.get_backend().id for _ in range(4)]
    assert selected == ["node-1", "node-3", "node-1", "node-3"]


def test_round_robin_node_recovery():
    """Node phục hồi sẽ tự động được tái hòa nhập vào vòng xoay."""
    backends = create_sample_backends(3)
    lb = RoundRobinBalancer(backends)

    # Đánh sập node-2
    lb.update_backend_status("node-2", False)
    assert lb.get_backend().id == "node-1"
    assert lb.get_backend().id == "node-3"

    # Phục hồi node-2
    lb.update_backend_status("node-2", True)
    # Vòng xoay hiện tại gồm cả 3 node: node-1, node-2, node-3
    selected = [lb.get_backend().id for _ in range(3)]
    assert set(selected) == {"node-1", "node-2", "node-3"}


def test_round_robin_explain_decision():
    """Kiểm tra chuỗi giải trình phục vụ Dashboard và Header."""
    backends = create_sample_backends(3)
    lb = RoundRobinBalancer(backends)

    b1 = lb.get_backend()
    exp1 = lb.explain_decision(chosen=b1)
    assert exp1 == "ROUND_ROBIN[step=1/3->node-1]"

    b2 = lb.get_backend()
    exp2 = lb.explain_decision(chosen=b2)
    assert exp2 == "ROUND_ROBIN[step=2/3->node-2]"

    # Khi không có node sống
    for b in backends:
        b.alive = False
    assert lb.explain_decision(chosen=None) == "ROUND_ROBIN[no_alive_backend]"


# ===================================================
# 2. Integration Test: Round Robin kết hợp với Proxy
# ===================================================


async def start_mock_backend(node_id: str) -> Tuple[web.AppRunner, int]:
    """Khởi động mock HTTP backend trên cổng ngẫu nhiên do OS cấp."""
    async def handler(request: web.Request) -> web.Response:
        headers = {"X-Backend-Node": node_id}
        return web.json_response({"node": node_id}, headers=headers)

    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port


@pytest.mark.anyio
async def test_round_robin_proxy_integration():
    """Kiểm tra Reverse Proxy hoạt động chuẩn xác với RoundRobinBalancer."""
    runners = []
    try:
        # Khởi động 3 mock backends
        r1, p1 = await start_mock_backend("mock-1")
        r2, p2 = await start_mock_backend("mock-2")
        r3, p3 = await start_mock_backend("mock-3")
        runners.extend([r1, r2, r3])

        backends = [
            Backend(id="mock-1", host="127.0.0.1", port=p1),
            Backend(id="mock-2", host="127.0.0.1", port=p2),
            Backend(id="mock-3", host="127.0.0.1", port=p3),
        ]
        lb = RoundRobinBalancer(backends)

        cfg = {
            "port": 0,
            "timeout": 2.0,
            "max_retries": 2,
            "quarantine_seconds": 5.0,
            "balancer": {"algorithm": "round_robin"},
        }
        proxy_app = create_app(config=cfg, balancer=lb)
        proxy_runner = web.AppRunner(proxy_app)
        await proxy_runner.setup()
        proxy_site = web.TCPSite(proxy_runner, "127.0.0.1", 0)
        await proxy_site.start()
        runners.append(proxy_runner)
        proxy_port = proxy_site._server.sockets[0].getsockname()[1]

        # Gửi 6 request liên tiếp qua Proxy
        served_nodes = []
        async with aiohttp.ClientSession() as session:
            for _ in range(6):
                async with session.get(f"http://127.0.0.1:{proxy_port}/api/test") as resp:
                    assert resp.status == 200
                    assert resp.headers.get("X-Balancer") == "round_robin"
                    assert "ROUND_ROBIN" in resp.headers.get("X-Balancer-Decision", "")
                    data = await resp.json()
                    served_nodes.append(data["node"])

        expected_sequence = ["mock-1", "mock-2", "mock-3", "mock-1", "mock-2", "mock-3"]
        assert served_nodes == expected_sequence

    finally:
        for r in runners:
            await r.cleanup()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
