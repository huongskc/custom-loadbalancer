# Load Balancer

## 1. Cài đặt môi trường

Yêu cầu: Python 3.10 trở lên.

```bash
pip install -r requirements.txt
```

---

## 2. Khởi chạy Cụm Mock Servers (3 Nodes)

Khởi động đồng thời 3 máy chủ HTTP backend độc lập tại các cổng `9001`, `9002`, `9003` trong cùng 1 lệnh:

```bash
python mock/mock_servers.py
```

*(Tùy chọn chạy bằng Docker Compose)*
```bash
docker compose -f mock/docker-compose.mock.yaml up -d
```

---

## 3. Khởi chạy Layer 7 Reverse Proxy Server

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

---

## 5. Chạy Kiểm thử Tự động (Automated Tests)

### A. Kiểm thử Toàn diện Hệ thống
Chạy toàn bộ 24 test cases tự động (Base contract, Consistent Hashing, Reverse Proxy, Failover, Traffic Simulation, Chaos CLI, Dynamic Recovery):

```bash
python -m pytest tests/ -v
```

Hoặc chạy trực tiếp từng module test:
```bash
python tests/test_base.py
python tests/test_consistent_hash.py
python tests/test_proxy.py
python tests/test_traffic_sim.py
```

### B. Kiểm thử Cụm Mock Server Cục bộ
*(Yêu cầu cụm mock server đang chạy ở Mục 2)*

```bash
python mock/test_mock.py
```