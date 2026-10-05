"""
Automated Verification for Mock Cluster
Kịch bản kiểm thử tự động toàn diện cụm Mock Servers.
Chạy trực tiếp: `python mock/test_mock.py` hoặc qua pytest: `python -m pytest mock/test_mock.py`
"""

import asyncio
import time
import aiohttp

# Danh sách 3 node kiểm thử tương ứng các cổng 9001, 9002, 9003
NODES = [
    {"name": f"mock-node-{i}", "url": f"http://127.0.0.1:{port}", "port": port}
    for i, port in enumerate([9001, 9002, 9003], 1)
]


async def run_all_tests():
    print(">>> Running Mock Cluster Tests...")
    timeout = aiohttp.ClientTimeout(total=3.0)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Bước 1: Kiểm tra tính sẵn sàng ban đầu của cả 3 node và header nhận diện
        for node in NODES:
            async with session.get(f"{node['url']}/healthz") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["status"] == "UP" and data["node"] == node["name"]
                assert resp.headers.get("X-Backend-Node") == node["name"]
                assert resp.headers.get("X-Backend-Port") == str(node["port"])
                print(f"  [PASS] {node['name']} healthz UP")

        # Bước 2: Kiểm tra xử lý request nghiệp vụ và bảo lưu Client IP (X-Forwarded-For)
        for node in NODES:
            headers = {"X-Forwarded-For": "192.168.1.50"}
            async with session.get(f"{node['url']}/api/orders?item=pho", headers=headers) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["backend"] == node["name"] and data["client_ip"] == "192.168.1.50"
                print(f"  [PASS] {node['name']} routing OK")

        # Bước 3: Thử nghiệm kịch bản Chaos - Đánh sập node 2 (500 DOWN) và hồi phục (200 UP)
        node2_url = "http://127.0.0.1:9002"
        # Đánh sập node 2
        async with session.post(f"{node2_url}/chaos/down") as resp:
            assert resp.status == 200
        async with session.get(f"{node2_url}/healthz") as resp:
            assert resp.status == 500
        print("  [PASS] mock-node-2 chaos DOWN verified (500)")

        # Khôi phục node 2
        async with session.post(f"{node2_url}/chaos/up") as resp:
            assert resp.status == 200
        async with session.get(f"{node2_url}/healthz") as resp:
            assert resp.status == 200
        print("  [PASS] mock-node-2 chaos UP verified (200)")

        # Bước 4: Thử nghiệm kịch bản giả lập độ trễ (Latency Injection) trên node 3
        node3_url = "http://127.0.0.1:9003"
        async with session.post(f"{node3_url}/chaos/delay?ms=200") as resp:
            assert resp.status == 200
        t0 = time.time()
        async with session.get(f"{node3_url}/api/delay-test") as resp:
            assert resp.status == 200
            assert (time.time() - t0) >= 0.18
        # Đặt lại độ trễ về 0ms
        await session.post(f"{node3_url}/chaos/delay?ms=0")
        print("  [PASS] mock-node-3 latency injection verified (200ms)")

    print(">>> ALL MOCK TESTS PASSED [100%]\n")


def test_mock_cluster():
    """Entry point tương thích với pytest tiêu chuẩn (không cần plugin ngoài)."""
    try:
        import pytest
    except ImportError:
        pytest = None

    try:
        asyncio.run(run_all_tests())
    except (aiohttp.ClientConnectorError, ConnectionRefusedError, OSError) as exc:
        if pytest:
            pytest.skip(f"Mock servers (9001-9003) not running: {exc}")
        else:
            print(f"[SKIP] Mock servers not running: {exc}")


if __name__ == "__main__":
    test_mock_cluster()

