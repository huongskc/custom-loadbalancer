"""
Traffic Simulation Script for Load Balancer.
Đóng vai trò Client thuần túy: Gửi HTTP requests liên tục hoặc theo đợt qua Proxy.

Cách dùng:
    python scripts/test_traffic.py                      # Bắn tải liên tục (~2 req/s, dừng bằng Ctrl+C)
    python scripts/test_traffic.py --requests 60        # Bắn đúng 60 requests rồi dừng
    python scripts/test_traffic.py --delay 0.5          # Khoảng nghỉ giữa các request (mặc định 0.5s)
    python scripts/test_traffic.py --concurrency 1      # Số worker đồng thời (mặc định 1)
"""

import argparse
import asyncio
import logging
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional
import aiohttp

# Đảm bảo nạp được module bất kể chạy từ thư mục nào
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Cấu hình UTF-8 an toàn cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Cấu hình log cho script bắn tải
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("traffic")

# Danh sách 10 Client IP giả lập để kiểm thử phân bổ tải và tính dính session
DEFAULT_CLIENT_IPS = [
    "192.168.1.10",
    "192.168.1.11",
    "192.168.1.12",
    "192.168.1.13",
    "192.168.1.14",
    "192.168.1.15",
    "192.168.1.16",
    "192.168.1.17",
    "192.168.1.18",
    "192.168.1.19",
]


async def send_single_request(
    session: aiohttp.ClientSession,
    url: str,
    client_ip: str,
    req_id: int,
) -> Dict:
    """Gửi một HTTP request kèm header X-Forwarded-For và ghi nhận kết quả."""
    start_time = time.perf_counter()
    headers = {"X-Forwarded-For": client_ip, "Host": "food.myproject.bar"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5.0)) as resp:
            await resp.read()
            latency = (time.perf_counter() - start_time) * 1000  # ms
            node = resp.headers.get("X-Backend-Node", "Unknown")
            algo = resp.headers.get("X-Balancer", "consistent_hash")
            decision = resp.headers.get("X-Balancer-Decision", "")
            return {
                "id": req_id,
                "ip": client_ip,
                "status": resp.status,
                "node": node,
                "algo": algo,
                "decision": decision,
                "latency_ms": latency,
                "success": 200 <= resp.status < 400,
            }
    except Exception as exc:
        latency = (time.perf_counter() - start_time) * 1000
        return {
            "id": req_id,
            "ip": client_ip,
            "status": 0,
            "node": "None",
            "algo": "unknown",
            "decision": "",
            "latency_ms": latency,
            "success": False,
            "error": str(exc),
        }


async def run_traffic_batch(
    target_url: str,
    num_requests: int = 50,
    concurrency: int = 1,
    client_ips: Optional[List[str]] = None,
) -> List[Dict]:
    """Bắn một đợt request hữu hạn với mức đồng thời chỉ định (phục vụ automated test)."""
    ips = client_ips or DEFAULT_CLIENT_IPS
    results: List[Dict] = []
    semaphore = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession() as session:
        async def worker(req_id: int):
            client_ip = ips[req_id % len(ips)]
            async with semaphore:
                res = await send_single_request(session, target_url, client_ip, req_id)
                results.append(res)

        tasks = [worker(i) for i in range(num_requests)]
        await asyncio.gather(*tasks)

    return results


async def run_traffic_continuous(
    target_url: str,
    concurrency: int = 1,
    delay: float = 0.5,
    client_ips: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Bắn tải liên tục với nhịp độ ổn định (~2 req/s mặc định) phục vụ quan sát.
    Thuần túy sinh tải: in tiến độ từng request trực tiếp ra console, không vẽ lại màn hình.
    Chỉ dừng khi người dùng nhấn Ctrl+C (KeyboardInterrupt).
    """
    ips = client_ips or DEFAULT_CLIENT_IPS
    semaphore = asyncio.Semaphore(concurrency)
    stop_event = asyncio.Event()

    print(f"[*] Khởi động Traffic Generator -> {target_url}")
    print(f"[*] Cấu hình: delay={delay}s (~{1/delay if delay > 0 else 999:.1f} req/s), workers={concurrency}")
    print(f"[*] Mở Terminal khác gõ `python scripts/dashboard.py` để xem Live Dashboard")
    print(f"[*] Nhấn Ctrl+C để dừng bắn tải.\n" + "-" * 74)

    async with aiohttp.ClientSession() as session:
        req_id = 0

        try:
            while not stop_event.is_set():
                client_ip = ips[req_id % len(ips)]
                current_id = req_id
                req_id += 1

                async def fire(cid: int, cip: str):
                    async with semaphore:
                        res = await send_single_request(session, target_url, cip, cid)
                        status_str = f"HTTP {res['status']}" if res['status'] > 0 else "FAIL"
                        print(f"[TRAFFIC #{cid + 1:>4}] Client: {cip:<15} -> {res['node']:<14} ({status_str:<8}) | {res['latency_ms']:5.1f}ms")

                # Chạy worker trong background
                asyncio.create_task(fire(current_id, client_ip))

                if delay > 0:
                    await asyncio.sleep(delay)

        except (asyncio.CancelledError, KeyboardInterrupt):
            pass


async def main_async():
    parser = argparse.ArgumentParser(description="Load Balancer Traffic Generator (Pure Load Engine)")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/order", help="Target Proxy URL")
    parser.add_argument("--requests", type=int, default=0, help="Số lượng requests (0 = liên tục cho tới khi Ctrl+C)")
    parser.add_argument("--concurrency", type=int, default=1, help="Số worker gửi đồng thời (mặc định 1)")
    parser.add_argument("--delay", type=float, default=0.5, help="Khoảng nghỉ giữa các lần gửi (giây, mặc định 0.5s = ~2 req/s)")
    args = parser.parse_args()

    if args.requests > 0:
        logger.info(f"Bắn {args.requests} requests vào {args.url} (concurrency={args.concurrency}, delay={args.delay}s)...")
        results = await run_traffic_batch(
            target_url=args.url,
            num_requests=args.requests,
            concurrency=args.concurrency,
        )
        print(f"\n[!] Hoàn thành gửi {len(results)} requests.")
    else:
        await run_traffic_continuous(
            target_url=args.url,
            concurrency=args.concurrency,
            delay=args.delay,
        )


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[!] Dừng bắn tải theo yêu cầu người dùng.")


if __name__ == "__main__":
    main()
