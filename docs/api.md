# Web Dashboard API Reference (Port :8001)

Tài liệu tóm tắt các REST API tại cổng `:8001` (`web_dashboard.py`) phục vụ việc phát triển và tích hợp giao diện Frontend Web.

> **Lưu ý:** Chạy các lệnh `curl` hoặc `PowerShell` đính kèm để tự xem dữ liệu phản hồi thực tế từ server.

---

## 1. Lấy Số Liệu Thời Gian Thực (Metrics & Status)

- **Endpoint:** `GET /api/stats`
- **Chức năng:** Trả về trạng thái tiến trình (mock, proxy, traffic), sức khỏe từng node (latency, alive), metrics (RPS sliding 5s, tỷ lệ thành công, phân bổ tải) và 20 sự kiện log gần nhất.
- **Lệnh curl:**
  ```bash
  curl -s http://127.0.0.1:8001/api/stats
  ```
- **Lệnh PowerShell:**
  ```powershell
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/stats" -Method Get
  ```

---

## 2. Điều Khiển Cụm Mock Servers (:9001 - :9003)

- **Endpoint:** `POST /api/control/mock`
- **Tham số body:**
  - Bật: `{"action": "start"}`
  - Tắt: `{"action": "stop"}` (dừng cưỡng chế tức thì)
- **Lệnh curl:**
  ```bash
  # Khởi động cụm mock
  curl -s -X POST http://127.0.0.1:8001/api/control/mock -H "Content-Type: application/json" -d '{"action": "start"}'

  # Dừng cụm mock
  curl -s -X POST http://127.0.0.1:8001/api/control/mock -H "Content-Type: application/json" -d '{"action": "stop"}'
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Khởi động cụm mock
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/mock" -Method Post -ContentType "application/json" -Body '{"action":"start"}'

  # Dừng cụm mock
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/mock" -Method Post -ContentType "application/json" -Body '{"action":"stop"}'
  ```

---

## 3. Điều Khiển Reverse Proxy (:8000)

- **Endpoint:** `POST /api/control/proxy`
- **Tham số body:**
  - Bật: `{"action": "start"}`
  - Tắt: `{"action": "stop"}` (dừng cưỡng chế tức thì)
- **Lệnh curl:**
  ```bash
  # Khởi động proxy
  curl -s -X POST http://127.0.0.1:8001/api/control/proxy -H "Content-Type: application/json" -d '{"action": "start"}'

  # Dừng proxy
  curl -s -X POST http://127.0.0.1:8001/api/control/proxy -H "Content-Type: application/json" -d '{"action": "stop"}'
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Khởi động proxy
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/proxy" -Method Post -ContentType "application/json" -Body '{"action":"start"}'

  # Dừng proxy
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/proxy" -Method Post -ContentType "application/json" -Body '{"action":"stop"}'
  ```

---

## 4. Điều Khiển Bộ Sinh Tải (Traffic Generator)

- **Endpoint:** `POST /api/control/traffic`
- **Tham số body:**
  - Bật tải: `{"action": "start", "concurrency": 1, "delay": 0.4, "requests": 0}` (với `requests: 0` là chạy liên tục)
  - Dừng tải: `{"action": "stop"}`
- **Lệnh curl:**
  ```bash
  # Bắt đầu sinh tải (2 luồng đồng thời, giãn cách 0.2s, chạy liên tục)
  curl -s -X POST http://127.0.0.1:8001/api/control/traffic -H "Content-Type: application/json" -d '{"action": "start", "concurrency": 2, "delay": 0.2, "requests": 0}'

  # Dừng sinh tải
  curl -s -X POST http://127.0.0.1:8001/api/control/traffic -H "Content-Type: application/json" -d '{"action": "stop"}'
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Bắt đầu sinh tải (2 luồng đồng thời, giãn cách 0.2s, chạy liên tục)
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/traffic" -Method Post -ContentType "application/json" -Body '{"action":"start","concurrency":2,"delay":0.2,"requests":0}'

  # Dừng sinh tải
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/traffic" -Method Post -ContentType "application/json" -Body '{"action":"stop"}'
  ```

---

## 5. Chuyển Đổi Thuật Toán Cân Bằng Tải (Clean Slate)

- **Endpoint:** `POST /api/control/algorithm`
- **Tham số body:**
  - `{"algorithm": "round_robin"}`
  - `{"algorithm": "least_connections"}`
  - `{"algorithm": "consistent_hash"}`
- **Lệnh curl:**
  ```bash
  # Chuyển sang Round Robin
  curl -s -X POST http://127.0.0.1:8001/api/control/algorithm -H "Content-Type: application/json" -d '{"algorithm": "round_robin"}'

  # Chuyển sang Least Connections
  curl -s -X POST http://127.0.0.1:8001/api/control/algorithm -H "Content-Type: application/json" -d '{"algorithm": "least_connections"}'

  # Chuyển sang Consistent Hashing
  curl -s -X POST http://127.0.0.1:8001/api/control/algorithm -H "Content-Type: application/json" -d '{"algorithm": "consistent_hash"}'
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Chuyển sang Round Robin
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/algorithm" -Method Post -ContentType "application/json" -Body '{"algorithm":"round_robin"}'

  # Chuyển sang Least Connections
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/algorithm" -Method Post -ContentType "application/json" -Body '{"algorithm":"least_connections"}'

  # Chuyển sang Consistent Hashing
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/algorithm" -Method Post -ContentType "application/json" -Body '{"algorithm":"consistent_hash"}'
  ```

---

## 6. Tiêm Sự Cố Mock Node (Chaos Injection)

- **Endpoint:** `POST /api/control/chaos`
- **Tham số body:**
  - Đánh sập node: `{"port": 9002, "action": "down"}`
  - Khôi phục node: `{"port": 9002, "action": "up"}`
  - Thêm độ trễ: `{"port": 9002, "action": "delay", "ms": 500}`
- **Lệnh curl:**
  ```bash
  # Đánh sập node 9002
  curl -s -X POST http://127.0.0.1:8001/api/control/chaos -H "Content-Type: application/json" -d '{"port": 9002, "action": "down"}'

  # Khôi phục node 9002
  curl -s -X POST http://127.0.0.1:8001/api/control/chaos -H "Content-Type: application/json" -d '{"port": 9002, "action": "up"}'

  # Thêm 500ms trễ vào node 9003
  curl -s -X POST http://127.0.0.1:8001/api/control/chaos -H "Content-Type: application/json" -d '{"port": 9003, "action": "delay", "ms": 500}'
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Đánh sập node 9002
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/chaos" -Method Post -ContentType "application/json" -Body '{"port":9002,"action":"down"}'

  # Khôi phục node 9002
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/chaos" -Method Post -ContentType "application/json" -Body '{"port":9002,"action":"up"}'

  # Thêm 500ms trễ vào node 9003
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/chaos" -Method Post -ContentType "application/json" -Body '{"port":9003,"action":"delay","ms":500}'
  ```

---

## 7. Quản Lý Backend Nodes & Trọng Số Động (Dynamic Nodes & Weights)

- **Endpoint:** `POST /api/control/backend`
- **Chức năng:**
  - Thêm node mới vào cụm cân bằng tải tại runtime (tự động bật HTTP Mock Server con nếu chưa có).
  - Cập nhật trọng số (`weight`) động cho bất kỳ node nào (Consistent Hash tự tính lại Virtual Nodes, Least Connections tự cập nhật score).
- **Tham số body:**
  - **Thêm node:** `{"action": "add", "id": "mock-node-4", "port": 9004, "weight": 2, "host": "127.0.0.1"}` (`id` và `port` bắt buộc; `weight` mặc định 1, `host` mặc định `127.0.0.1`)
  - **Đổi trọng số:** `{"action": "weight", "id": "mock-node-1", "weight": 10}` (`id` và `weight` bắt buộc)
- **Lệnh curl:**
  ```bash
  # Thêm mock-node-4 trên cổng 9004 với trọng số 2
  curl -s -X POST http://127.0.0.1:8001/api/control/backend -H "Content-Type: application/json" -d '{"action": "add", "id": "mock-node-4", "port": 9004, "weight": 2}'

  # Cập nhật trọng số của mock-node-1 lên 10
  curl -s -X POST http://127.0.0.1:8001/api/control/backend -H "Content-Type: application/json" -d '{"action": "weight", "id": "mock-node-1", "weight": 10}'
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Thêm mock-node-4 trên cổng 9004 với trọng số 2
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/backend" -Method Post -ContentType "application/json" -Body '{"action":"add","id":"mock-node-4","port":9004,"weight":2}'

  # Cập nhật trọng số của mock-node-1 lên 10
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/backend" -Method Post -ContentType "application/json" -Body '{"action":"weight","id":"mock-node-1","weight":10}'
  ```
