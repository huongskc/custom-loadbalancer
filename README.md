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

## 3. Chạy Kiểm thử (Tests)

### A. Kiểm thử Cụm Mock Server
*(Yêu cầu cụm mock server đang chạy ở Bước 2)*

```bash
python mock/test_mock.py
```

### B. Kiểm thử Thuật toán (Unit Tests)
*(Chạy độc lập, không cần khởi động mock server)*

- Chạy toàn bộ test qua `pytest`:
```bash
python -m pytest tests/ -v
```