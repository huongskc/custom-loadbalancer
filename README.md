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

## 4. Chạy Kiểm thử (Tests)

### A. Kiểm thử Bộ Cân bằng tải & Thuật toán
Chạy toàn bộ 16 test cases (Base contract, Consistent Hashing, Reverse Proxy, Hop-by-hop stripping & Passive Failover):

```bash
python -m pytest tests/ -v
```

Hoặc chạy trực tiếp từng module test:
```bash
python tests/test_base.py
python tests/test_consistent_hash.py
python tests/test_proxy.py
```

### B. Kiểm thử Cụm Mock Server Cục bộ
*(Yêu cầu cụm mock server đang chạy ở Bước 2)*

```bash
python mock/test_mock.py
```