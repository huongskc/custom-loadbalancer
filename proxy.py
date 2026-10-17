"""
Layer 7 Reverse Proxy Engine with Passive Failover & Immediate Retry (RFC 7230).
Triển khai cơ chế che giấu sự cố hạ tầng (Fault Transparency) trên nền AsyncIO.
"""

import asyncio
import json
import logging
from pathlib import Path
import time
from typing import Dict, Optional
import aiohttp
from aiohttp import web
import yaml

from balancers.base import Backend, BaseBalancer, extract_client_ip
from balancers.consistent_hash import ConsistentHashBalancer
from balancers.least_connections import LeastConnectionsBalancer
from balancers.round_robin import RoundRobinBalancer

ALGORITHMS = {
    "consistent_hash": ConsistentHashBalancer,
    "round_robin": RoundRobinBalancer,
    "least_connections": LeastConnectionsBalancer,
}

# Cấu hình log chuẩn cho Proxy (Terminal output chỉ hiện WARNING/INFO quan trọng, không in per-request)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("proxy")

# Cấu hình Access Logger ghi nhận toàn bộ access events vào logs/access.log cho Dashboard
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)
access_logger = logging.getLogger("proxy.access")
access_logger.setLevel(logging.INFO)
access_logger.propagate = False
if not access_logger.handlers:
    file_handler = logging.FileHandler(LOGS_DIR / "access.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    access_logger.addHandler(file_handler)

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


def log_access_event(
    req: web.Request,
    client_ip: str,
    node: str,
    status: int,
    algo: str,
    decision: str = "",
    decision_snapshot: Optional[Dict] = None,
):
    """Ghi nhận sự kiện truy cập chuẩn hóa dạng JSONL vào logs/access.log cho Dashboard."""
    event_data = {
        "ts": time.time(),
        "method": req.method,
        "path": req.rel_url.path,
        "client_ip": client_ip,
        "node": node,
        "status": status,
        "algo": algo,
        "decision": decision,
        "snapshot": decision_snapshot,
    }
    access_logger.info(json.dumps(event_data))


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
    client_ip = extract_client_ip(dict(request.headers), request.remote)

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
            log_access_event(request, client_ip, "None", 503, balancer.name, "NO_HEALTHY_BACKEND")
            return web.json_response({"error": "No healthy backend available"}, status=503)

        # Chụp lại trạng thái quyết định tại đúng thời điểm lựa chọn (chính xác active_conns & score)
        decision_ctx = balancer.explain_decision(client_ip, backend)
        decision_snapshot = balancer.get_visualizer_state()

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
                    if decision_ctx:
                        resp_headers["X-Balancer-Decision"] = decision_ctx

                    # Ghi nhận event vào logs/access.log phục vụ Dashboard quan sát độc lập kèm snapshot trạng thái
                    log_access_event(request, client_ip, backend.id, upstream.status, balancer.name, decision_ctx, decision_snapshot)

                    logger.debug(
                        f"[PROXY] {request.method} {request.rel_url} [Client: {client_ip}] {decision_ctx} "
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
    log_access_event(request, client_ip, "None", 502, balancer.name, "ALL_RETRIES_FAILED")
    return web.json_response({"error": "All backend retry attempts failed"}, status=502)


async def handle_change_algorithm(request: web.Request) -> web.Response:
    """
    Control API: Chuyển đổi thuật toán cân bằng tải tại runtime (Clean Slate).
    Tái tạo danh sách Backend mới tinh từ config (alive=True, active_conns=0) và làm sạch access.log.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    new_algo = data.get("algorithm")
    if not new_algo or new_algo not in ALGORITHMS:
        return web.json_response({
            "error": f"Invalid algorithm '{new_algo}'",
            "available": list(ALGORITHMS.keys()),
        }, status=400)

    # Clean Slate: Tái tạo danh sách Backend mới tinh từ config hoặc balancer hiện tại
    config = request.app[CONFIG_KEY]
    raw_backends = config.get("backends", [])
    if raw_backends:
        backends = [
            Backend(id=b["id"], host=b["host"], port=b["port"], weight=b.get("weight", 1))
            for b in raw_backends
        ]
    else:
        current_lb = request.app.get(BALANCER_KEY)
        backends = [
            Backend(id=b.id, host=b.host, port=b.port, weight=b.weight)
            for b in (current_lb.backends if current_lb else [])
        ]
    new_balancer_cls = ALGORITHMS[new_algo]
    new_balancer = new_balancer_cls(backends)
    if hasattr(request.app, "_state"):
        request.app._state[BALANCER_KEY] = new_balancer
    else:
        request.app[BALANCER_KEY] = new_balancer

    # Làm sạch access.log để Dashboard đếm thống kê lại từ đầu cho thuật toán mới
    access_log_path = LOGS_DIR / "access.log"
    with open(access_log_path, "w", encoding="utf-8"):
        pass

    logger.info(f"[CONTROL] Algorithm switched to '{new_algo}' (Clean Slate: backends & access.log reset)")
    return web.json_response({
        "status": "ok",
        "algorithm": new_algo,
        "message": f"Successfully switched to {new_algo}",
    })


async def handle_get_balancer_state(request: web.Request) -> web.Response:
    """
    Control API: Trả về trạng thái chi tiết của thuật toán cân bằng tải hiện tại
    phục vụ Algorithm Visualizer trên Web Dashboard.
    """
    balancer: BaseBalancer = request.app[BALANCER_KEY]
    state = balancer.get_visualizer_state()
    state["algorithm"] = balancer.name
    return web.json_response(state)


async def handle_manage_backend(request: web.Request) -> web.Response:
    """
    Control API: Quản lý thêm backend node hoặc cập nhật trọng số tại runtime.
    - action: "add" -> Thêm backend node mới (yêu cầu id, port, optional host, optional weight)
    - action: "weight" -> Cập nhật trọng số của backend node (yêu cầu id, weight)
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    action = data.get("action", "add")
    balancer: BaseBalancer = request.app[BALANCER_KEY]

    if action == "add":
        b_id = data.get("id")
        port = data.get("port")
        host = data.get("host", "127.0.0.1")
        weight = int(data.get("weight", 1))

        if not b_id or not port:
            return web.json_response({"error": "Missing required fields: 'id' and 'port'"}, status=400)

        new_backend = Backend(id=str(b_id), host=str(host), port=int(port), weight=max(1, weight))
        success = balancer.add_backend(new_backend)
        if not success:
            return web.json_response({"error": f"Backend with id '{b_id}' or port {port} already exists"}, status=400)

        # Cập nhật danh sách backends trong app[CONFIG_KEY] để giữ lại node khi chuyển đổi thuật toán
        cfg_backends = request.app[CONFIG_KEY].setdefault("backends", [])
        cfg_backends.append({"id": new_backend.id, "host": new_backend.host, "port": new_backend.port, "weight": new_backend.weight})

        logger.info(f"[CONTROL] Added new backend {new_backend.id} ({new_backend.url}) with weight {new_backend.weight}")
        return web.json_response({
            "status": "ok",
            "message": f"Backend {b_id} added successfully",
            "backend": new_backend.to_dict(),
        })

    elif action == "weight":
        b_id = data.get("id")
        weight = data.get("weight")
        if not b_id or weight is None:
            return web.json_response({"error": "Missing required fields: 'id' and 'weight'"}, status=400)

        try:
            w_int = int(weight)
            if w_int <= 0:
                return web.json_response({"error": "Weight must be a positive integer (> 0)"}, status=400)
        except (ValueError, TypeError):
            return web.json_response({"error": "Weight must be an integer"}, status=400)

        success = balancer.update_backend_weight(str(b_id), w_int)
        if not success:
            return web.json_response({"error": f"Backend with id '{b_id}' not found"}, status=404)

        # Cập nhật weight trong app[CONFIG_KEY]
        for b in request.app[CONFIG_KEY].get("backends", []):
            if b.get("id") == b_id:
                b["weight"] = w_int

        logger.info(f"[CONTROL] Updated backend {b_id} weight to {w_int}")
        return web.json_response({
            "status": "ok",
            "message": f"Updated weight of {b_id} to {w_int}",
            "id": str(b_id),
            "weight": w_int,
        })

    elif action == "reset":
        raw_config = load_config()
        default_backends = [
            Backend(id=b["id"], host=b["host"], port=b["port"], weight=b.get("weight", 1))
            for b in raw_config.get("backends", [])
        ]
        algo_name = balancer.name
        new_balancer = ALGORITHMS[algo_name](default_backends)
        if hasattr(request.app, "_state"):
            request.app._state[BALANCER_KEY] = new_balancer
        else:
            request.app[BALANCER_KEY] = new_balancer
        request.app[CONFIG_KEY]["backends"] = [
            {"id": b.id, "host": b.host, "port": b.port, "weight": b.weight}
            for b in default_backends
        ]
        logger.info(f"[CONTROL] Reset backends to defaults: {[b.id for b in default_backends]}")
        return web.json_response({
            "status": "ok",
            "message": "Backends reset to default config",
            "backends": [b.to_dict() for b in default_backends],
        })

    return web.json_response({"error": f"Unknown action '{action}'. Available: 'add', 'weight', 'reset'"}, status=400)


async def handle_update_backend_status(request: web.Request) -> web.Response:
    """
    Control API: Cập nhật trạng thái sống/chết (alive=True/False) cho một backend node tại runtime.
    Giúp đồng bộ ngay lập tức khi người dùng tiêm sự cố (chaos down/up) từ Dashboard.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    port = data.get("port")
    b_id = data.get("id")
    alive = data.get("alive")

    if alive is None:
        return web.json_response({"error": "Missing 'alive' boolean"}, status=400)

    balancer: BaseBalancer = request.app[BALANCER_KEY]
    found = False
    for b in balancer.backends:
        if (port and b.port == int(port)) or (b_id and b.id == str(b_id)):
            balancer.update_backend_status(b.id, bool(alive))
            found = True
            logger.info(f"[CONTROL] Updated backend {b.id} (port {b.port}) status to alive={alive}")
            break

    if not found:
        return web.json_response({"error": "Backend not found"}, status=404)

    return web.json_response({
        "status": "ok",
        "message": f"Updated backend status to alive={alive}",
        "balancer_state": balancer.get_visualizer_state(),
    })


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
        algo = config.get("balancer", {}).get("algorithm") or config.get("algorithm", "consistent_hash")
        if algo not in ALGORITHMS:
            raise ValueError(f"Unknown algorithm '{algo}'. Available: {list(ALGORITHMS)}")
        balancer = ALGORITHMS[algo](backends)

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

    # Đăng ký Control API trước catch-all route
    app.router.add_get("/api/balancer/state", handle_get_balancer_state)
    app.router.add_post("/api/algorithm", handle_change_algorithm)
    app.router.add_post("/api/backend", handle_manage_backend)
    app.router.add_post("/api/backend/status", handle_update_backend_status)

    # Đăng ký bắt toàn bộ mọi HTTP methods và URL paths
    app.router.add_route("*", "/{path:.*}", handle_request)
    return app


def main():
    config = load_config()
    port = config.get("port", 8000)

    # Làm sạch access.log khi khởi động phiên Proxy mới
    access_log_path = Path("logs/access.log")
    access_log_path.parent.mkdir(exist_ok=True)
    with open(access_log_path, "w", encoding="utf-8"):
        pass

    logger.info(f"Starting Layer 7 Reverse Proxy on 0.0.0.0:{port}...")
    web.run_app(create_app(config), host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
