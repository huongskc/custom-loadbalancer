"""
Standalone Live Terminal Dashboard for Load Balancer.
Đóng vai trò Observer độc lập: Đọc log sự kiện thời gian thực từ logs/access.log
và dựng giao diện ANSI hiển thị lưu lượng và bản chất thuật toán.

Cách dùng:
    python scripts/dashboard.py                   # Tự động theo dõi logs/access.log
    python scripts/dashboard.py --interval 0.5    # Tần suất làm mới (mặc định 0.5s)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Kích hoạt ANSI escape sequence (VT100) trên Windows Terminal / PowerShell
os.system("")

# Cấu hình UTF-8 an toàn cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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


def render_live_dashboard(
    results: List[Dict],
    start_time: float,
    target_url: str = "logs/access.log",
    concurrency: int = 1,
    delay: float = 0.5,
    ips: Optional[List[str]] = None,
) -> str:
    """Dựng giao diện Live Terminal Dashboard thời gian thực với mô hình Clockwise Interval."""
    monitored_ips = ips or DEFAULT_CLIENT_IPS
    total = len(results)

    # Tính RPS từ các event trong 5 giây gần nhất
    now = time.time()
    recent_5s = [r for r in results if now - r.get("ts", now) <= 5.0]
    rps = len(recent_5s) / 5.0 if recent_5s else 0.0

    successes = sum(1 for r in results if 200 <= r.get("status", 0) < 400 or r.get("success", False))
    failures = total - successes
    pct_succ = (successes / total * 100) if total > 0 else 100.0

    latencies = [r.get("latency_ms", 0.0) for r in results if r.get("latency_ms", 0.0) > 0]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    # Tự động nhận diện thuật toán từ event mới nhất
    detected_algo = "consistent_hash"
    for r in reversed(results):
        if r.get("algo") and r["algo"] != "unknown":
            detected_algo = r["algo"]
            break

    # Đếm số request từng node
    node_counts: Dict[str, int] = {}
    for r in results:
        node = r.get("node", "unknown")
        if node and node != "None":
            node_counts[node] = node_counts.get(node, 0) + 1

    lines = [
        "+========================================================================================+",
        f"|       LOAD BALANCER LIVE DASHBOARD ({detected_algo.upper():<20})                      |",
        f"| Source: {target_url:<24} | Total Reqs: {total:<5} | RPS: {rps:>5.1f} req/s          |",
        "+========================================================================================+",
        f"[TRAFFIC METRICS] Sent: {total:<5} | 200 OK: {successes:<5} ({pct_succ:5.1f}%) | "
        f"Failed: {failures:<3} | Avg Latency: {avg_lat:5.2f}ms",
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
        lines.append("  (Đang chờ ghi nhận traffic đầu tiên...)")

    lines.append("")
    lines.append("--- [2] CLIENT IP ROUTING & ALGORITHM ESSENCE ---")
    lines.append("Mô hình Clockwise: [VNode_prev < IP_hash <= VNode_cw] -> Target Server")

    # Section 2: Quản lý trạng thái theo thời gian thực (Dynamic Session State Tracking)
    for ip in monitored_ips:
        ip_all = [r for r in results if r.get("client_ip", r.get("ip")) == ip]
        if not ip_all:
            lines.append(f"{ip:<15} -> (đang chờ request...)")
            continue

        last_req = ip_all[-1]
        last_status = last_req.get("status", 0)
        last_node = last_req.get("node", "None")
        decision_raw = last_req.get("decision", "")

        # Kiểm tra nếu request gần nhất thất bại (cụm node sập / trả về 502, 503)
        if last_status >= 500 or last_node in ("None", None):
            err_tag = f"[DOWN | HTTP {last_status}]" if last_status else "[DEAD | NO RESPONSE]"
            decision_disp = f"[{decision_raw or 'NO_HEALTHY_BACKEND'}]"
            lines.append(f"{ip:<15} -> {decision_disp:<58} -> {'None':<12} {err_tag}")
            continue

        valid_reqs = [r for r in ip_all if r.get("node") not in ("None", None) and 200 <= r.get("status", 0) < 400]
        baseline = valid_reqs[0].get("node") if valid_reqs else last_node
        recent = [r.get("node") for r in valid_reqs[-3:]] if valid_reqs else [last_node]
        current_node = recent[-1]
        is_steady = all(n == current_node for n in recent)

        # Định dạng biểu thức thuật toán
        expr_str = ""
        if decision_raw and "|" in decision_raw:
            parts = decision_raw.split("|")
            if len(parts) == 5:
                # Format: prev_vnode|prev_hash|ip_hash|cw_vnode|cw_hash
                prev_vn, prev_h, ip_h, cw_vn, cw_h = parts
                expr_str = f"[{prev_h} < {ip_h} <= {cw_h} ({cw_vn})]"
            else:
                expr_str = f"[{decision_raw}]"
        elif decision_raw:
            expr_str = f"[{decision_raw}]"
        else:
            expr_str = f"[{current_node}]"

        # Định dạng trạng thái dính / failover
        if detected_algo == "round_robin":
            state_str = "[ROTATING]"
        elif current_node == baseline and is_steady:
            state_str = "(ACTIVE | STICKY)"
        elif current_node != baseline:
            state_str = f"[FAILOVER ACTIVE: shifted from {baseline}]"
        else:
            state_str = f"[RECOVERING TO {baseline}...]"

        lines.append(f"{ip:<15} -> {expr_str:<58} -> {current_node:<12} {state_str}")

    lines.append("-" * 90)
    lines.append(" [Live Demo] Mở Terminal khác gõ: `python scripts/chaos.py down 9002`")
    lines.append(" [Live Demo] Phục hồi lại server: `python scripts/chaos.py up 9002`")
    lines.append(" [Control]   Nhấn Ctrl+C bất kỳ lúc nào để DỪNG Dashboard")
    lines.append("=" * 90)

    return "\n".join(lines)


def load_events_from_log(log_path: Path, max_lines: int = 1000) -> List[Dict]:
    """Đọc và parse các dòng JSON mới nhất từ access.log."""
    if not log_path.exists():
        return []

    events: List[Dict] = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-max_lines:]:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return events


def run_dashboard_loop(log_file: str = "logs/access.log", refresh_interval: float = 0.5):
    """Vòng lặp đọc log định kỳ và cập nhật màn hình ANSI in-place."""
    log_path = Path(log_file)
    start_time = time.time()

    print(f"[*] Khởi động Live Terminal Dashboard (quan sát {log_file})...")
    time.sleep(0.5)

    try:
        while True:
            events = load_events_from_log(log_path)
            output = render_live_dashboard(
                results=events,
                start_time=start_time,
                target_url=str(log_path),
            )
            sys.stdout.write("\033[H\033[J" + output + "\n")
            sys.stdout.flush()
            time.sleep(refresh_interval)
    except KeyboardInterrupt:
        print("\n[!] Dừng Live Dashboard theo yêu cầu người dùng.")


def main():
    parser = argparse.ArgumentParser(description="Standalone Live Terminal Dashboard for Load Balancer T22")
    parser.add_argument("--log", default="logs/access.log", help="Đường dẫn file access log của Proxy")
    parser.add_argument("--interval", type=float, default=0.5, help="Tần suất làm mới giao diện (giây, mặc định 0.5s)")
    args = parser.parse_args()

    run_dashboard_loop(log_file=args.log, refresh_interval=args.interval)


if __name__ == "__main__":
    main()
