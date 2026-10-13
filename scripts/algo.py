"""
Algorithm Switching Tool for Load Balancers.
Công cụ độc lập để chuyển đổi thuật toán cân bằng tải tại runtime (Clean Slate).

Cách dùng:
    python scripts/algo.py [algorithm] [port]   # Mặc định port 8000
    Ví dụ:
        python scripts/algo.py round_robin
        python scripts/algo.py least_connections
        python scripts/algo.py consistent_hash
"""

import json
import sys
import urllib.request

# Cấu hình UTF-8 an toàn cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VALID_ALGOS = ["consistent_hash", "round_robin", "least_connections"]


def send_post(url: str, payload: dict) -> dict:
    """Gửi HTTP POST request với JSON payload bằng thư viện chuẩn urllib."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cmd_switch(algo: str, port: int = 8000):
    """Chuyển đổi thuật toán trên Reverse Proxy."""
    url = f"http://127.0.0.1:{port}/api/algorithm"
    try:
        res = send_post(url, {"algorithm": algo})
        print(f"\n[ALGO SWITCH] Đã chuyển đổi sang thuật toán: {res.get('algorithm', algo).upper()}!")
    except Exception as e:
        print(f"\n[ERROR] Không thể chuyển đổi thuật toán tại cổng {port}: {e}\n")


def print_usage():
    print("""
Sử dụng:
    python scripts/algo.py [algorithm] [port]   - Chuyển đổi thuật toán (mặc định port 8000)

Các thuật toán hỗ trợ:
    - consistent_hash    : Consistent Hashing với Virtual Nodes (dính theo Client IP)
    - round_robin        : Round Robin tuần hoàn đều cơ bản
    - least_connections  : Weighted Least Connections (điều phối theo tải kết nối)
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    target = sys.argv[1].lower()
    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8000

    if target not in VALID_ALGOS:
        print(f"\nThuật toán không hợp lệ: '{target}'")
        print_usage()
        sys.exit(1)

    cmd_switch(target, port)


if __name__ == "__main__":
    main()
