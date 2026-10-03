"""
Layer 7 Reverse Proxy Engine with Passive Failover & Immediate Retry (RFC 7230).
Triển khai cơ chế che giấu sự cố hạ tầng (Fault Transparency) trên nền AsyncIO.
"""

import asyncio
import logging
from typing import Dict, Optional
import aiohttp
from aiohttp import web
import yaml

from balancers.base import Backend, BaseBalancer
from balancers.consistent_hash import ConsistentHashBalancer

# Cấu hình log chuẩn cho Proxy
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("proxy")

# Danh sách Hop-by-Hop headers theo chuẩn RFC 7230 Section 6.1
# Các header này chỉ có ý nghĩa trên từng chặng truyền dẫn đơn lẻ và bắt buộc phải lọc bỏ khi chuyển tiếp
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

# Khởi tạo AppKey định kiểu an toàn cho trạng thái ứng dụng aiohttp (tương thích aiohttp 3.9+)
CONFIG_KEY = web.AppKey("config", dict)
BALANCER_KEY = web.AppKey("balancer", BaseBalancer)
SESSION_KEY = web.AppKey("session", Optional[aiohttp.ClientSession])


def load_config(path: str = "config.yaml") -> dict:
    """Nạp file cấu hình YAML chứa danh sách máy chủ backend và thông số vận hành."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def quarantine_recovery(backend: Backend, delay: float, balancer: BaseBalancer):
    """
    Cơ chế Cách ly Tạm thời (Quarantine Backoff Window):
    Tạm dừng điều phối traffic vào nút lỗi trong 'delay' giây để nút có thời gian tự hồi phục.
    Sau khi hết thời gian, tự động đánh dấu alive=True để nút tái gia nhập vòng băm điều phối.
    """
    await asyncio.sleep(delay)
    balancer.update_backend_status(backend.id, True)
    logger.info(f"[HEALTH] Backend {backend.id} ({backend.url}) quarantine expired, re-enabled.")


def filter_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Lọc bỏ các Hop-by-Hop headers và Content-Length để aiohttp tự tính toán kích thước gói tin chuẩn xác."""
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != "content-length"}


async def handle_request(request: web.Request) -> web.Response:
    """
    Hàm xử lý chính của Layer 7 Reverse Proxy:
    - Bóc tách thông tin request từ Client (Method, Path, Headers, Body, Client IP).
    - Lựa chọn máy chủ backend phù hợp thông qua thuật toán cân bằng tải.
    - Quản lý vòng lặp thử lại tức thì (Immediate Retry) để che giấu hoàn toàn sự cố nếu có node sập.
    """
    # 1. Trích xuất tài nguyên chia sẻ từ Application context
    cfg = request.app[CONFIG_KEY]
    balancer: BaseBalancer = request.app[BALANCER_KEY]
    session: aiohttp.ClientSession = request.app[SESSION_KEY]

    # 2. Xác định Client IP (ưu tiên IP gốc từ X-Forwarded-For nếu đứng sau Cloudflare/Nginx)
    raw_ip = request.headers.get("X-Forwarded-For") or (request.remote or "127.0.0.1")
    client_ip = raw_ip.split(",")[0].strip()

    # 3. Đọc dữ liệu Payload từ Client
    body = await request.read()

    # 4. Chuẩn hóa Headers chuyển tiếp: bảo lưu Host gốc và bổ sung vết mạng X-Forwarded-For
    req_headers = filter_headers(dict(request.headers))
    req_headers["Host"] = request.headers.get("Host", "localhost")
    remote_ip = request.remote or "127.0.0.1"
    existing_xff = request.headers.get("X-Forwarded-For")
    req_headers["X-Forwarded-For"] = f"{existing_xff}, {remote_ip}" if existing_xff else remote_ip

    # 5. Vòng lặp chuyển tiếp với cơ chế Giám sát Thụ động & Chuyển tiếp Lỗi Tức thì (Immediate Retry)
    max_retries = cfg.get("max_retries", 2)
    timeout_sec = cfg.get("timeout", 5.0)
    quarantine_sec = cfg.get("quarantine_seconds", 10.0)

    for attempt in range(max_retries + 1):
        # Lấy backend tiếp theo theo thuật toán cân bằng tải
        backend = balancer.get_backend(client_ip)
        if not backend:
            logger.warning("No healthy backend available to serve request.")
            return web.json_response({"error": "No healthy backend available"}, status=503)

        try:
            # Context manager theo dõi kết nối đồng thời (phục vụ Least Connections / giám sát tải)
            with backend.track_connection():
                timeout = aiohttp.ClientTimeout(total=timeout_sec)
                async with session.request(
                    method=request.method,
                    url=f"{backend.url}{request.rel_url}",
                    headers=req_headers,
                    data=body,
                    timeout=timeout,
                    allow_redirects=False,
                ) as upstream:
                    resp_body = await upstream.read()
                    resp_headers = filter_headers(dict(upstream.headers))
                    resp_headers["X-Balancer"] = balancer.name

                    # Khi backend trả về lỗi máy chủ (5xx), kích hoạt failover và chuyển tiếp tức thì
                    if upstream.status >= 500 and attempt < max_retries:
                        logger.warning(
                            f"[FAILOVER] Backend {backend.id} ({backend.url}) returned HTTP {upstream.status}. "
                            f"Quarantined {quarantine_sec}s. Immediate retry {attempt + 1}/{max_retries + 1}."
                        )
                        balancer.update_backend_status(backend.id, False)
                        asyncio.create_task(quarantine_recovery(backend, quarantine_sec, balancer))
                        continue

                    backend.requests_count += 1
                    decision_ctx = balancer.explain_decision(client_ip, backend)
                    algo_str = f" {decision_ctx}" if decision_ctx else ""
                    logger.info(
                        f"[PROXY] {request.method} {request.rel_url} [Client: {client_ip}]{algo_str} "
                        f"-> {backend.id} ({upstream.status}) | Conns: {backend.active_conns} | Total: {backend.requests_count}"
                    )
                    return web.Response(body=resp_body, status=upstream.status, headers=resp_headers)


        except (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError, asyncio.TimeoutError) as exc:
            # Bắt lỗi mất kết nối mạng hoặc quá hạn: cách ly node hỏng và lập tức thử lại sang node khác
            logger.warning(
                f"[FAILOVER] Backend {backend.id} ({backend.url}) connection failed: {exc}. "
                f"Quarantined {quarantine_sec}s. Immediate retry {attempt + 1}/{max_retries + 1}."
            )
            balancer.update_backend_status(backend.id, False)
            asyncio.create_task(quarantine_recovery(backend, quarantine_sec, balancer))
            continue

    # Khi toàn bộ các lượt thử lại đều thất bại
    return web.json_response({"error": "All backend retry attempts failed"}, status=502)


def create_app(
    config: Optional[dict] = None,
    balancer: Optional[BaseBalancer] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> web.Application:
    """
    Factory khởi tạo ứng dụng Web Proxy:
    - Hỗ trợ Dependency Injection cho kiểm thử tự động (mock config, mock balancer, custom session).
    - Đăng ký vòng đời startup (khởi tạo ClientSession chung) và cleanup (giải phóng kết nối).
    """
    config = config or load_config()
    if balancer is None:
        backends = [
            Backend(id=b["id"], host=b["host"], port=b["port"], weight=b.get("weight", 1))
            for b in config.get("backends", [])
        ]
        balancer = ConsistentHashBalancer(backends)

    app = web.Application()
    app[CONFIG_KEY], app[BALANCER_KEY], app[SESSION_KEY] = config, balancer, session

    # Hook quản lý vòng đời HTTP ClientSession
    async def on_startup(app: web.Application):
        if app[SESSION_KEY] is None or app[SESSION_KEY].closed:
            app[SESSION_KEY] = aiohttp.ClientSession()

    async def on_cleanup(app: web.Application):
        if app.get(SESSION_KEY) and not app[SESSION_KEY].closed:
            await app[SESSION_KEY].close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Đăng ký bắt toàn bộ mọi HTTP methods và URL paths
    app.router.add_route("*", "/{path:.*}", handle_request)
    return app


def main():
    config = load_config()
    port = config.get("port", 8000)
    logger.info(f"Starting Layer 7 Reverse Proxy on 0.0.0.0:{port}...")
    web.run_app(create_app(config), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
