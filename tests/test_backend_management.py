"""
Automated Tests for Dynamic Backend Node & Weight Management.
Kiểm thử tính năng thêm node backend và cập nhật trọng số động tại runtime.
"""

import asyncio
from pathlib import Path
import sys
from typing import Tuple

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import aiohttp
from aiohttp import web
import pytest

from balancers.base import Backend, BaseBalancer
from balancers.round_robin import RoundRobinBalancer
from balancers.least_connections import LeastConnectionsBalancer
from balancers.consistent_hash import ConsistentHashBalancer
from proxy import create_app
from web_dashboard import create_dashboard_app, ProcessManager
from mock.mock_servers import MockNode, NODES, RUNNERS


async def start_proxy_test_server(config: dict) -> Tuple[web.AppRunner, int, str]:
    app = create_app(config=config)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port, f"http://127.0.0.1:{port}"


async def start_mock_test_node(port: int = 0) -> Tuple[web.AppRunner, int, MockNode]:
    node = MockNode("test-mock", 0)
    runner = web.AppRunner(node.app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assigned_port = site._server.sockets[0].getsockname()[1]
    node.port = assigned_port
    return runner, assigned_port, node


async def start_dashboard_test_server(pm: ProcessManager = None) -> Tuple[web.AppRunner, int, str]:
    app = create_dashboard_app(pm=pm)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, port, f"http://127.0.0.1:{port}"


def test_balancer_add_backend_and_duplicate_check():
    b1 = Backend(id="node-1", host="127.0.0.1", port=9001, weight=1)
    b2 = Backend(id="node-2", host="127.0.0.1", port=9002, weight=1)
    lb = RoundRobinBalancer([b1, b2])

    # 1. Thêm node mới thành công
    b3 = Backend(id="node-3", host="127.0.0.1", port=9003, weight=2)
    assert lb.add_backend(b3) is True
    assert len(lb.backends) == 3
    assert lb.get_backend_by_id("node-3") == b3

    # 2. Thêm trùng ID -> thất bại
    b_dup_id = Backend(id="node-1", host="127.0.0.1", port=9099, weight=1)
    assert lb.add_backend(b_dup_id) is False

    # 3. Thêm trùng host:port -> thất bại
    b_dup_port = Backend(id="node-99", host="127.0.0.1", port=9002, weight=1)
    assert lb.add_backend(b_dup_port) is False


def test_consistent_hash_dynamic_add_and_weight():
    b1 = Backend(id="node-1", host="127.0.0.1", port=9001, weight=1)
    lb = ConsistentHashBalancer([b1], vnodes=50)
    initial_vnodes = len(lb._sorted_keys)
    assert initial_vnodes == 50

    # Thêm node-2 với weight=2 -> vnodes thêm 100
    b2 = Backend(id="node-2", host="127.0.0.1", port=9002, weight=2)
    assert lb.add_backend(b2) is True
    assert len(lb._sorted_keys) == 150

    # Cập nhật weight của node-1 lên 3 -> vnodes thành 3*50 + 2*50 = 250
    assert lb.update_backend_weight("node-1", 3) is True
    assert len(lb._sorted_keys) == 250
    assert b1.weight == 3

    # Cập nhật node không tồn tại
    assert lb.update_backend_weight("non-existent", 5) is False


def test_least_connections_dynamic_weight_affects_score():
    b1 = Backend(id="node-1", host="127.0.0.1", port=9001, weight=1, active_conns=2)
    b2 = Backend(id="node-2", host="127.0.0.1", port=9002, weight=1, active_conns=2)
    lb = LeastConnectionsBalancer([b1, b2])

    # Ban đầu score b1 = 2/1 = 2.0, b2 = 2/1 = 2.0
    assert lb._score(b1) == 2.0

    # Tăng weight b1 lên 4 -> score b1 = 2/4 = 0.5 < score b2 = 2.0
    assert lb.update_backend_weight("node-1", 4) is True
    assert lb._score(b1) == 0.5
    # Do b1 có score nhỏ hơn, get_backend sẽ chọn b1
    assert lb.get_backend() == b1


def test_proxy_api_manage_backend_add_and_weight():
    async def _test():
        backends = [{"id": "node-1", "host": "127.0.0.1", "port": 9001, "weight": 1}]
        cfg = {"backends": backends, "algorithm": "round_robin"}
        runner, port, base_url = await start_proxy_test_server(cfg)

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Thêm backend node-2
                async with session.post(f"{base_url}/api/backend", json={"action": "add", "id": "node-2", "port": 9002, "weight": 3}) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["status"] == "ok"
                    assert data["backend"]["id"] == "node-2"
                    assert data["backend"]["weight"] == 3

                # 2. Thêm lại node-2 -> báo lỗi 400
                async with session.post(f"{base_url}/api/backend", json={"action": "add", "id": "node-2", "port": 9002}) as resp:
                    assert resp.status == 400

                # 3. Thêm thiếu trường bắt buộc -> báo lỗi 400
                async with session.post(f"{base_url}/api/backend", json={"action": "add", "id": "node-3"}) as resp:
                    assert resp.status == 400

                # 4. Đổi weight của node-1 lên 5
                async with session.post(f"{base_url}/api/backend", json={"action": "weight", "id": "node-1", "weight": 5}) as resp:
                    assert resp.status == 200
                    data_w = await resp.json()
                    assert data_w["weight"] == 5

                # 5. Đổi weight node không tồn tại -> 404
                async with session.post(f"{base_url}/api/backend", json={"action": "weight", "id": "ghost", "weight": 5}) as resp:
                    assert resp.status == 404

                # 6. Đổi weight với giá trị không hợp lệ -> 400
                async with session.post(f"{base_url}/api/backend", json={"action": "weight", "id": "node-1", "weight": -1}) as resp:
                    assert resp.status == 400
        finally:
            await runner.cleanup()

    asyncio.run(_test())


def test_mock_node_chaos_spawn():
    async def _test():
        runner, assigned_port, node = await start_mock_test_node()
        try:
            async with aiohttp.ClientSession() as session:
                # Gọi spawn node 9889
                async with session.post(f"http://127.0.0.1:{assigned_port}/chaos/spawn", json={"port": 9889, "name": "spawned-node-9889"}) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["status"] == "ok"
                    assert 9889 in NODES
        finally:
            await runner.cleanup()
            if 9889 in NODES:
                del NODES[9889]

    asyncio.run(_test())


def test_web_dashboard_control_backend_error_cases():
    async def _test():
        pm = ProcessManager()
        runner, port, base_url = await start_dashboard_test_server(pm=pm)
        try:
            async with aiohttp.ClientSession() as session:
                # Missing fields for add
                async with session.post(f"{base_url}/api/control/backend", json={"action": "add", "id": "node-x"}) as resp:
                    assert resp.status == 400

                # Missing fields for weight
                async with session.post(f"{base_url}/api/control/backend", json={"action": "weight", "id": "node-x"}) as resp:
                    assert resp.status == 400

                # Unknown action
                async with session.post(f"{base_url}/api/control/backend", json={"action": "delete"}) as resp:
                    assert resp.status == 400
        finally:
            await runner.cleanup()

    asyncio.run(_test())
