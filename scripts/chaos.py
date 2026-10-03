"""
Chaos Injection & Mock Cluster Management Tool for Load Balancer T22.
Công cụ độc lập để giả lập sự cố (sập node, tăng độ trễ) và kiểm tra sức khỏe cụm Mock Servers.

Cách dùng:
    python scripts/chaos.py down [port]       # Đánh sập node (mặc định port 9002)
    python scripts/chaos.py up [port]         # Khôi phục node (mặc định port 9002)
    python scripts/chaos.py delay [port] [ms] # Giả lập độ trễ xử lý (ms)
    python scripts/chaos.py status            # Xem trạng thái sức khỏe toàn bộ cụm mock
"""

import json
import sys
import urllib.error
import urllib.request

DEFAULT_PORTS = [9001, 9002, 9003]


def send_post(url: str) -> dict:
    """Gửi HTTP POST request bằng thư viện chuẩn urllib."""
    req = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_get(url: str) -> tuple[int, dict]:
    """Gửi HTTP GET request bằng thư viện chuẩn urllib."""
    try:
        with urllib.request.urlopen(url, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {"error": str(e)}
        return e.code, data
    except Exception as e:
        return 0, {"error": str(e)}


def cmd_down(port: int = 9002):
    """Đánh sập node chỉ định."""
    url = f"http://127.0.0.1:{port}/chaos/down"
    try:
        res = send_post(url)
        print(f"\n[CHAOS DOWN] Node {res.get('node', f'port {port}')} set to DOWN (Offline)!")
        print("  -> Node này sẽ trả về HTTP 500 khi nhận request.")
        print("  -> Reverse Proxy sẽ tự động bắt lỗi và chuyển tiếp tức thì (Immediate Retry) sang node khác.\n")
    except Exception as e:
        print(f"\n[ERROR] Không thể kết nối tới node tại cổng {port}: {e}\n")


def cmd_up(port: int = 9002):
    """Khôi phục node chỉ định."""
    url = f"http://127.0.0.1:{port}/chaos/up"
    try:
        res = send_post(url)
        print(f"\n[CHAOS UP] Node {res.get('node', f'port {port}')} restored to UP (Healthy)!")
        print("  -> Node này đã sẵn sàng phục vụ và sẽ được điều phối lưu lượng trở lại.\n")
    except Exception as e:
        print(f"\n[ERROR] Không thể kết nối tới node tại cổng {port}: {e}\n")


def cmd_delay(port: int = 9002, delay_ms: float = 500.0):
    """Giả lập độ trễ xử lý."""
    url = f"http://127.0.0.1:{port}/chaos/delay?ms={delay_ms}"
    try:
        res = send_post(url)
        print(f"\n[CHAOS DELAY] Node {res.get('node', f'port {port}')} delay set to {delay_ms}ms!\n")
    except Exception as e:
        print(f"\n[ERROR] Không thể kết nối tới node tại cổng {port}: {e}\n")


def cmd_status():
    """Kiểm tra và hiển thị trạng thái sức khỏe của toàn bộ cụm mock servers."""
    print("\n+========================= MOCK CLUSTER STATUS =========================+")
    print("| Backend Node  | Address         | HTTP Status | State  | Total Requests|")
    print("+---------------+-----------------+-------------+--------+---------------+ ")
    for port in DEFAULT_PORTS:
        url = f"http://127.0.0.1:{port}/healthz"
        status, data = send_get(url)
        node_name = data.get("node", f"node-{port}")
        state = data.get("status", "DOWN" if status != 200 else "UP")
        if status == 0:
            status_str = "UNREACHABLE"
            state_str = "DEAD"
            total_reqs = "-"
        else:
            status_str = f"{status} OK" if status == 200 else f"{status} ERR"
            state_str = state
            total_reqs = str(data.get("requests", "-"))

        print(f"| {node_name:<13} | 127.0.0.1:{port:<6} | {status_str:<11} | {state_str:<6} | {total_reqs:<13} |")
    print("+---------------+-----------------+-------------+--------+---------------+\n")


def print_usage():
    print("""
Sử dụng:
    python scripts/chaos.py down [port]        - Đánh sập node (mặc định 9002)
    python scripts/chaos.py up [port]          - Khôi phục node (mặc định 9002)
    python scripts/chaos.py delay [port] [ms]  - Giả lập độ trễ (mặc định 9002, 500ms)
    python scripts/chaos.py status             - Xem trạng thái cụm mock servers
""")


def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    action = sys.argv[1].lower()
    port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 9002

    if action == "down":
        cmd_down(port)
    elif action == "up":
        cmd_up(port)
    elif action == "delay":
        ms = float(sys.argv[3]) if len(sys.argv) > 3 else 500.0
        cmd_delay(port, ms)
    elif action == "status":
        cmd_status()
    else:
        print(f"Hành động không hợp lệ: {action}")
        print_usage()


if __name__ == "__main__":
    main()
