"""
Mock Server Cluster for Load Balancer T22
Khởi chạy đồng thời 3 backend HTTP độc lập (ports 9001, 9002, 9003) trong 1 tiến trình bất đồng bộ.
Hỗ trợ kiểm tra sức khỏe (/healthz) và giả lập sự cố (/chaos/*) phục vụ kiểm thử Load Balancer.
"""

import asyncio
import logging
from aiohttp import web

# Cấu hình log hệ thống
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class MockNode:
    """Đại diện cho một backend server độc lập với trạng thái và endpoint riêng."""

    def __init__(self, name: str, port: int):
        self.name = name
        self.port = port
        self.is_alive = True          # Trạng thái sống/chết (phục vụ health check và failover)
        self.delay_ms = 0.0           # Độ trễ nhân tạo (phục vụ test thuật toán Least Connections)
        self.requests = 0             # Bộ đếm số request đã xử lý

        # Khởi tạo aiohttp application và đăng ký định tuyến
        self.app = web.Application()
        self.app.router.add_get("/healthz", self.healthz)
        self.app.router.add_post("/chaos/down", self.chaos_down)
        self.app.router.add_post("/chaos/up", self.chaos_up)
        self.app.router.add_post("/chaos/delay", self.chaos_delay)
        self.app.router.add_route("*", "/{tail:.*}", self.handle_request)

    @property
    def headers(self) -> dict:
        """HTTP headers gắn vào mọi phản hồi để Load Balancer và client nhận diện nguồn gốc."""
        return {"X-Backend-Node": self.name, "X-Backend-Port": str(self.port)}

    async def healthz(self, request: web.Request) -> web.Response:
        """Endpoint kiểm tra sức khỏe định kỳ cho Active Health Checker (200=UP, 500=DOWN)."""
        status = 200 if self.is_alive else 500
        state = "UP" if self.is_alive else "DOWN"
        return web.json_response(
            {"status": state, "node": self.name, "port": self.port},
            status=status,
            headers=self.headers,
        )

    async def chaos_down(self, request: web.Request) -> web.Response:
        """Giả lập sự cố: đánh sập node để kiểm thử cơ chế phát hiện lỗi và Failover."""
        self.is_alive = False
        logging.warning(f"[{self.name}] Node set to DOWN")
        return web.json_response({"action": "chaos_down", "node": self.name, "is_alive": False})

    async def chaos_up(self, request: web.Request) -> web.Response:
        """Giả lập hồi phục: khôi phục node hoạt động trở lại sau sự cố."""
        self.is_alive = True
        logging.info(f"[{self.name}] Node set to UP")
        return web.json_response({"action": "chaos_up", "node": self.name, "is_alive": True})

    async def chaos_delay(self, request: web.Request) -> web.Response:
        """Giả lập độ trễ mạng/tải cao (ms) để kiểm thử thuật toán Least Connections."""
        self.delay_ms = float(request.query.get("ms", 0))
        logging.info(f"[{self.name}] Node delay set to {self.delay_ms}ms")
        return web.json_response({"action": "chaos_delay", "node": self.name, "delay_ms": self.delay_ms})

    async def handle_request(self, request: web.Request) -> web.Response:
        """Xử lý mọi HTTP request thông thường chuyển tiếp từ Load Balancer."""
        # Từ chối request nếu node đang bị đánh sập
        if not self.is_alive:
            return web.json_response({"error": "node down", "node": self.name}, status=500, headers=self.headers)

        # Mô phỏng độ trễ xử lý nếu có
        if self.delay_ms > 0:
            await asyncio.sleep(self.delay_ms / 1000.0)

        self.requests += 1

        # Trích xuất Client IP (ưu tiên header X-Forwarded-For do Load Balancer chuyển tiếp)
        client_ip = request.headers.get("X-Forwarded-For", request.remote or "127.0.0.1").split(",")[0].strip()

        return web.json_response(
            {
                "backend": self.name,
                "port": self.port,
                "method": request.method,
                "path": request.path_qs,
                "client_ip": client_ip,
                "total_requests": self.requests,
            },
            headers=self.headers,
        )

    async def start(self) -> web.AppRunner:
        """Khởi động TCP site lắng nghe trên cổng được chỉ định."""
        runner = web.AppRunner(self.app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", self.port)
        await site.start()
        logging.info(f"[{self.name}] Listening on http://127.0.0.1:{self.port}")
        return runner


async def main():
    # Khởi tạo cụm 3 node(cổng 9001, 9002, 9003)
    nodes = [MockNode(f"mock-node-{i}", port) for i, port in enumerate([9001, 9002, 9003], 1)]

    # Chạy đồng thời cả 3 server trong cùng 1 Event Loop
    runners = await asyncio.gather(*(node.start() for node in nodes))

    try:
        # Giữ tiến trình chạy liên tục cho đến khi nhận tín hiệu dừng
        await asyncio.Event().wait()
    finally:
        # Dọn dẹp tài nguyên khi dừng cụm
        await asyncio.gather(*(r.cleanup() for r in runners))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
