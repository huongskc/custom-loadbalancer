# Load Balancer

## 1. Cài đặt môi trường

Yêu cầu: Python 3.10 trở lên.

```bash
pip install -r requirements.txt
```

---

## 2. Trung Tâm Điều Khiển Hợp Nhất (Web Dashboard - Single Entry Point)

**Khuyến nghị:** Bạn chỉ cần mở duy nhất 1 terminal và chạy lệnh:

```bash
python web_dashboard.py
```

Truy cập trình duyệt tại **`http://localhost:8001`**. Giao diện (`web/index.html`) được `web_dashboard.py` phục vụ trực tiếp, không cần cài thêm gì và không cần build.

### Hướng dẫn mở và sử dụng giao diện

1. **Mở giao diện:** chạy `python web_dashboard.py`, rồi mở `http://localhost:8001` trên trình duyệt. Nếu cổng 8001 đang bận, dùng `python web_dashboard.py --port 8002`.
2. **Khởi động hệ thống:** ở khung **Dịch vụ**, bấm **Khởi động** cho Mock servers, sau đó cho Reverse proxy. Ba thẻ node trong khung **Backend nodes** sẽ chuyển sang `UP`.
3. **Sinh tải:** ở khung **Sinh tải**, chọn số luồng và giãn cách, bấm **Bắt đầu**. Bảng **20 request gần nhất** và các chỉ số (RPS, tỷ lệ thành công, phần trăm tải mỗi node) cập nhật mỗi giây.
4. **Đổi thuật toán:** bấm `Round Robin`, `Least Conn` hoặc `Consistent Hash` ở khung **Thuật toán cân bằng tải**. Lệnh này gửi qua proxy nên cần bật proxy trước.
5. **Tiêm sự cố:** ở khung **Tiêm sự cố**, chọn node rồi bấm **Đánh sập**, **Khôi phục** hoặc nhập độ trễ (ms) và bấm **Áp dụng**. Quan sát cơ chế failover: node chuyển `DOWN` nhưng request vẫn trả 200.
6. **Quản lý backend:** ở khung **Quản lý backend**, nhập ID và cổng để **Thêm node** mới khi hệ thống đang chạy, hoặc chọn node và **Lưu** trọng số mới.
7. **Dừng:** bấm **Dừng** ở từng dịch vụ. Khi tắt `web_dashboard.py` (Ctrl+C), các tiến trình con do nó khởi động cũng bị dừng theo.

Giao diện cho phép:
- Khởi động / Dừng cụm 3 Mock Servers (`:9001`, `:9002`, `:9003`).
- Khởi động / Dừng Reverse Proxy (`:8000`).
- Bật / Tắt bộ sinh tải với tần suất và luồng tùy chỉnh.
- Chuyển đổi thuật toán Clean Slate trực tiếp trên UI.
- Tiêm sự cố sập node hoặc giả lập độ trễ (Chaos Testing) chỉ bằng 1 cú click.
- Thêm node mới và chỉnh trọng số động tại runtime.

> **Xử lý sự cố thường gặp**
> - Trang báo "Mất kết nối tới web_dashboard": `web_dashboard.py` chưa chạy hoặc sai cổng.
> - Đổi thuật toán, thêm node hoặc đổi trọng số báo lỗi 502: Reverse proxy chưa được khởi động.
> - Trang trắng hoặc hiện "API Ready on Port 8001": thiếu file `web/index.html`, kiểm tra thư mục `web/` nằm ở gốc dự án.

> 📖 **Tài liệu API Web Dashboard:** Xem chi tiết tại [docs/api.md](docs/api.md).

---

## 3. Khởi chạy Thủ công Từng Thành phần (Manual CLI Execution)

Nếu muốn khởi chạy thủ công từng dịch vụ trên các terminal riêng biệt:

### A. Khởi chạy Cụm Mock Servers (3 Nodes)
Khởi động đồng thời 3 máy chủ HTTP backend độc lập tại các cổng `9001`, `9002`, `9003`:

```bash
python mock/mock_servers.py
```

### B. Khởi chạy Layer 7 Reverse Proxy Server
Khởi động bộ cân bằng tải tại cổng `:8000`:

```bash
python proxy.py
```

Proxy tự động nạp cấu hình `config.yaml`, điều phối lưu lượng đến 3 mock nodes và tự động chuyển vùng dự phòng (Passive Failover / Immediate Retry) khi có node gặp sự cố.

---

## 4. Quan sát, Bắn tải & Quản trị Chaos (Observability & Testing)

Khi cụm Mock Servers và Reverse Proxy đang chạy, mở các cửa sổ terminal mới để quan sát và kiểm thử:

### A. Màn hình Quan sát Trực quan (Live Terminal Dashboard)
Mở một terminal riêng để quan sát phân bổ tải và khoảng chặn thuật toán Consistent Hashing theo thời gian thực (đọc từ `logs/access.log`):

```bash
python scripts/dashboard.py
```

### B. Bắn tải Thuần túy (Pure Traffic Generator)
Mở một terminal khác để gửi luồng tải HTTP liên tục qua Reverse Proxy:

```bash
python scripts/test_traffic.py
```

### C. Quản trị Sự cố Độc lập (Independent Chaos Management)
Mở một cửa sổ terminal để gõ lệnh làm sập, làm trễ hoặc phục hồi node và quan sát ngay phản ứng chuyển vùng tức thì (Immediate Retry) trên Dashboard:

```bash
# Đánh sập node 9002 (trả về HTTP 500)
python scripts/chaos.py down 9002

# Khôi phục node 9002 (trả về HTTP 200)
python scripts/chaos.py up 9002

# Thêm 500ms delay cho node 9001
python scripts/chaos.py delay 9001 500
```

### D. Chuyển đổi Thuật toán (Algorithm Switching)
Mở một terminal để chuyển đổi thuật toán cân bằng tải tại runtime (hỗ trợ `consistent_hash`, `round_robin`, `least_connections`):

```bash
python scripts/algo.py round_robin
```

---

## 5. Chạy Kiểm thử Tự động (Automated Tests)

### A. Kiểm thử Toàn diện Hệ thống
Chạy toàn bộ 57 test cases tự động (Base contract, Consistent Hashing, Round Robin, Least Connections, Reverse Proxy & Control API, Failover, Traffic Simulation, Web Dashboard Coordinator & Force Kill):

```bash
python -m pytest tests/ -v
```

Hoặc chạy trực tiếp từng module test:
```bash
python tests/test_base.py
python tests/test_consistent_hash.py
python tests/test_round_robin.py #chú ý @pytest.mark.anyio
python tests/test_least_connections.py
python tests/test_proxy.py
python tests/test_traffic_sim.py
python tests/test_web_dashboard.py
```

### B. Kiểm thử Cụm Mock Server Cục bộ
*(Yêu cầu cụm mock server đang chạy ở Mục 2)*

```bash
python mock/test_mock.py
```