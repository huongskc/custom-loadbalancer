"""
Traffic Simulation Script for Load Balancer T22.
Sinh lưu lượng thử nghiệm liên tục với Client IP giả lập để kiểm chứng phân bổ tải
và tính dính (Session Stickiness / Affinity) của các thuật toán cân bằng tải.
Cung cấp Live Terminal Dashboard cập nhật thời gian thực trong lúc bắn tải.

Cách dùng:
    python scripts/test_traffic.py                      # Bắn tải liên tục có Live Dashboard (dừng bằng Ctrl+C)
    python scripts/test_traffic.py --requests 60        # Bắn đúng 60 requests rồi dừng
    python scripts/test_traffic.py --delay 0.05         # Điều chỉnh khoảng nghỉ giữa các request (giây)
    python scripts/test_traffic.py --concurrency 5      # Số kết nối đồng thời
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from typing import Dict, List, Optional
import aiohttp

# Kích hoạt ANSI escape sequence (VT100) trên Windows Terminal / PowerShell
os.system("")

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
            return {
                "id": req_id,
                "ip": client_ip,
                "status": resp.status,
                "node": node,
                "algo": algo,
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
            "latency_ms": latency,
            "success": False,
            "error": str(exc),
        }


def render_live_dashboard(
    results: List[Dict],
    start_time: float,
    target_url: str,
    concurrency: int,
    delay: float,
    ips: List[str],
) -> str:
    """Dựng giao diện Live Terminal Dashboard thời gian thực với thanh tiến độ và tự động hoàn nguyên khi server UP."""
    total = len(results)
    elapsed = max(0.001, time.time() - start_time)
    rps = total / elapsed if total > 0 else 0.0

    successes = sum(1 for r in results if r["success"])
    failures = total - successes
    pct_succ = (successes / total * 100) if total > 0 else 100.0

    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    # Tự động nhận diện thuật toán từ header trả về
    detected_algo = "load_balancer"
    for r in reversed(results):
        if r.get("algo") and r["algo"] != "unknown":
            detected_algo = r["algo"]
            break

    # Đếm số request từng node
    node_counts: Dict[str, int] = {}
    for r in results:
        node = r["node"]
        node_counts[node] = node_counts.get(node, 0) + 1

    lines = [
        "+========================================================================+",
        f"|       LOAD BALANCER LIVE TRAFFIC DASHBOARD ({detected_algo.upper():<20}) |",
        f"| Target: {target_url:<22} | Workers: {concurrency:<2} | RPS: {rps:>5.1f} req/s       |",
        "+========================================================================+",
        f"[TRAFFIC METRICS] Sent: {total:<5} | 200 OK: {successes:<5} ({pct_succ:5.1f}%) | "
        f"Failed: {failures:<3} | Latency: {avg_lat:5.2f}ms",
        "",
        "--- [1] BACKEND TRAFFIC SHARE (ASCII PROGRESS BARS) ---",
    ]

    # Section 1: Progress bars cho từng node
    if node_counts:
        for node, count in sorted(node_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total * 100) if total > 0 else 0.0
            bar_width = 30
            filled = int(round(bar_width * pct / 100))
            bar = "#" * filled + "-" * (bar_width - filled)
            lines.append(f"{node:<16} [{bar}] {pct:5.1f}% ({count:>4} reqs)")
    else:
        lines.append("  (Đang gửi những requests đầu tiên...)")

    lines.append("")
    lines.append("--- [2] CLIENT IP ROUTING & SESSION AFFINITY ---")

    # Section 2: Quản lý trạng thái theo thời gian thực (Dynamic Session State Tracking)
    # Tự động hoàn nguyên lại ACTIVE | STICKY khi node phục hồi trở lại (Server UP)
    for ip in ips:
        ip_reqs = [r for r in results if r["ip"] == ip and r["node"] != "None"]
        if not ip_reqs:
            lines.append(f"{ip:<16} -> (đang chờ request...)")
            continue

        baseline = ip_reqs[0]["node"]
        recent = [r["node"] for r in ip_reqs[-6:]]
        current_node = recent[-1]
        is_steady = all(n == current_node for n in recent)

        if detected_algo == "round_robin":
            lines.append(f"{ip:<16} -> {current_node:<14} [ROTATING / ROUND-ROBIN]")
        elif current_node == baseline and is_steady:
            # Server đang bình thường hoặc ĐÃ PHỤC HỒI -> Tự động hoàn nguyên như ban đầu
            lines.append(f"{ip:<16} -> {current_node:<14} (ACTIVE | STICKY)")
        elif current_node != baseline:
            # Node chính đang sập, lưu lượng dạt sang node phụ
            lines.append(f"{ip:<16} -> {current_node:<14} [FAILOVER ACTIVE: shifted from {baseline}]")
        else:
            # Đang trong giai đoạn chuyển tiếp quay về node gốc
            lines.append(f"{ip:<16} -> {current_node:<14} [RECOVERING TO {baseline}...]")

    lines.append("-" * 74)
    lines.append(" [Live Demo] Mở Terminal khác gõ `python scripts/chaos.py down 9002`")
    lines.append(" [Control]   Nhấn Ctrl+C bất kỳ lúc nào để DỪNG và xem bảng tổng kết")
    lines.append("=" * 74)

    return "\n".join(lines)


async def run_traffic_batch(
    target_url: str,
    num_requests: int = 50,
    concurrency: int = 5,
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
    concurrency: int = 5,
    delay: float = 0.05,
    client_ips: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Bắn tải liên tục không giới hạn số lượng kèm Live Terminal Dashboard cập nhật mỗi giây.
    Chỉ dừng khi người dùng nhấn Ctrl+C (KeyboardInterrupt).
    """
    ips = client_ips or DEFAULT_CLIENT_IPS
    results: List[Dict] = []
    semaphore = asyncio.Semaphore(concurrency)
    stop_event = asyncio.Event()

    async with aiohttp.ClientSession() as session:
        req_id = 0
        start_time = time.time()
        last_refresh_time = time.time()

        try:
            while not stop_event.is_set():
                client_ip = ips[req_id % len(ips)]
                current_id = req_id
                req_id += 1

                async def fire(cid: int, cip: str):
                    async with semaphore:
                        res = await send_single_request(session, target_url, cip, cid)
                        results.append(res)

                # Chạy worker trong background
                asyncio.create_task(fire(current_id, client_ip))

                # Làm mới Live Terminal Dashboard định kỳ mỗi 1.0 giây hoặc mỗi 25 requests
                now = time.time()
                if now - last_refresh_time >= 1.0 or req_id % 25 == 0:
                    last_refresh_time = now
                    dashboard_output = render_live_dashboard(
                        results=results,
                        start_time=start_time,
                        target_url=target_url,
                        concurrency=concurrency,
                        delay=delay,
                        ips=ips,
                    )
                    sys.stdout.write("\033[H\033[J" + dashboard_output + "\n")
                    sys.stdout.flush()

                if delay > 0:
                    await asyncio.sleep(delay)

        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

    print("\n")
    return results


def print_client_summary(results: List[Dict], title: str = "CLIENT TRAFFIC SUMMARY"):
    """In bảng tổng kết toàn diện kết quả lưu lượng phía client kèm phân tích tính dính."""
    total = len(results)
    if total == 0:
        logger.warning("Không có request nào được gửi.")
        return

    successes = sum(1 for r in results if r["success"])
    failures = total - successes
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    min_lat = min(latencies) if latencies else 0.0
    max_lat = max(latencies) if latencies else 0.0

    detected_algo = "load_balancer"
    for r in reversed(results):
        if r.get("algo") and r["algo"] != "unknown":
            detected_algo = r["algo"]
            break

    # 1. Đếm số request từng node phản hồi
    node_counts: Dict[str, int] = {}
    ip_node_map: Dict[str, Dict[str, int]] = {}

    for r in results:
        node = r["node"]
        node_counts[node] = node_counts.get(node, 0) + 1
        cip = r["ip"]
        if cip not in ip_node_map:
            ip_node_map[cip] = {}
        ip_node_map[cip][node] = ip_node_map[cip].get(node, 0) + 1

    pct_success = (successes / total) * 100

    print("\n" + "=" * 74)
    print(f" {f'{title} ({detected_algo.upper()})'.center(72)} ")
    print("=" * 74)
    print(f"Total Requests Sent: {total:<5} | Success (2xx/3xx): {successes} ({pct_success:.1f}%) | Failed: {failures}")
    print(f"Latency: Avg={avg_lat:.2f}ms | Min={min_lat:.2f}ms | Max={max_lat:.2f}ms")
    print("-" * 74)
    print(f"{'Backend Node Served':<25} | {'Requests Received':<20} | {'Traffic Share (%)':<20}")
    print("-" * 74)
    for node, count in sorted(node_counts.items(), key=lambda x: x[1], reverse=True):
        share = (count / total) * 100
        print(f"{node:<25} | {count:<20} | {share:5.1f}%")
    print("-" * 74)

    # 2. Bảng phân rã tính dính theo Client IP
    print("\n" + "+========================== CLIENT IP ROUTING & SESSION AFFINITY ====================+")
    print(f"| {'Client IP':<16} | {'Primary Node':<14} | {'Requests':<8} | {'Affinity':<12} | {'Details':<20} |")
    print("+-----------------+----------------+----------+--------------+----------------------+")

    switched_ips = 0
    total_ips = len(ip_node_map)

    for cip, hits in sorted(ip_node_map.items()):
        total_ip_reqs = sum(hits.values())
        primary_node, primary_count = max(hits.items(), key=lambda x: x[1])
        affinity_pct = (primary_count / total_ip_reqs * 100) if total_ip_reqs > 0 else 0.0

        if len(hits) == 1:
            affinity_str = "100.0% Sticky"
            detail_str = f"[{primary_node}: {primary_count}]"
        else:
            switched_ips += 1
            affinity_str = f"{affinity_pct:5.1f}% Main"
            detail_str = ", ".join(f"{n}:{c}" for n, c in sorted(hits.items(), key=lambda x: x[1], reverse=True))

        print(f"| {cip:<16} | {primary_node:<14} | {total_ip_reqs:<8} | {affinity_str:<12} | {detail_str:<20} |")

    print("+====================================================================================+")

    # 3. Phân tích tác động Failover nếu có sự cố
    if switched_ips > 0:
        unaffected = total_ips - switched_ips
        pct_unaffected = (unaffected / total_ips * 100) if total_ips > 0 else 0.0
        print(f"\n[SESSION AFFINITY & FAILOVER IMPACT ANALYSIS ({detected_algo.upper()})]")
        print(f"- Total Client IPs Monitored : {total_ips}")
        print(f"- Unaffected Sessions (Stable): {unaffected} ({pct_unaffected:.1f}%)")
        print(f"- Remapped Sessions (Failover): {switched_ips} ({100 - pct_unaffected:.1f}%)")
        print(f"=> Phân tích xáo trộn phiên hoàn tất cho thuật toán {detected_algo.upper()}!")
    else:
        print(f"\n[ROUTING STABILITY] 100% Client Sessions đều đạt tính dính tuyệt đối trên {detected_algo.upper()}!")

    print("=" * 74 + "\n")


async def main_async():
    parser = argparse.ArgumentParser(description="Load Balancer Traffic Generator")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/order", help="Target Proxy URL")
    parser.add_argument("--requests", type=int, default=0, help="Số lượng requests (mặc định 0 = liên tục cho tới khi Ctrl+C)")
    parser.add_argument("--concurrency", type=int, default=5, help="Số worker gửi đồng thời")
    parser.add_argument("--delay", type=float, default=0.05, help="Khoảng nghỉ giữa các lần gửi (giây, mặc định 0.05s = ~20 req/s)")
    args = parser.parse_args()

    results: List[Dict] = []
    if args.requests > 0:
        logger.info(f"Bắn {args.requests} requests vào {args.url} (concurrency={args.concurrency})...")
        results = await run_traffic_batch(
            target_url=args.url,
            num_requests=args.requests,
            concurrency=args.concurrency,
        )
    else:
        results = await run_traffic_continuous(
            target_url=args.url,
            concurrency=args.concurrency,
            delay=args.delay,
        )

    print_client_summary(results)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[!] Dừng bắn tải theo yêu cầu người dùng.")


if __name__ == "__main__":
    main()
