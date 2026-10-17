# Web Dashboard API Reference (Port :8001)

Tài liệu tóm tắt các REST API tại cổng `:8001` (`web_dashboard.py`) phục vụ việc phát triển và tích hợp giao diện Frontend Web.

> **Lưu ý:** Chạy các lệnh `curl` hoặc `PowerShell` đính kèm để tự xem dữ liệu phản hồi thực tế từ server.

---

## 1. Lấy Số Liệu Thời Gian Thực (Metrics & Status)

- **Endpoint:** `GET /api/stats`
- **Chức năng:** Trả về trạng thái tiến trình con (mock, proxy, traffic), sức khỏe từng node (latency ms, alive), metrics tổng hợp (RPS sliding window 5s, tỷ lệ thành công, phân bổ tải các node), 20 sự kiện log gần nhất, đối tượng `balancer_state` (phục vụ trực tiếp cho Algorithm Decision Visualizer: góc Virtual Nodes trên vòng băm 360°, điểm tải Least Connections hoặc bước tuần hoàn Round Robin) và `last_event` (sự kiện truy cập mới nhất).
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
  - Bật tải: `{"action": "start", "delay": 0.4, "requests": 0}` (với `requests: 0` là sinh tải liên tục; sử dụng cơ chế dispatch async task không nghẽn)
  - Dừng tải: `{"action": "stop"}` (dừng cưỡng chế tức thì via Force Kill)
- **Lệnh curl:**
  ```bash
  # Bắt đầu sinh tải (giãn cách 0.4s, chạy liên tục)
  curl -s -X POST http://127.0.0.1:8001/api/control/traffic -H "Content-Type: application/json" -d '{"action": "start", "delay": 0.4, "requests": 0}'

  # Dừng sinh tải
  curl -s -X POST http://127.0.0.1:8001/api/control/traffic -H "Content-Type: application/json" -d '{"action": "stop"}'
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Bắt đầu sinh tải (giãn cách 0.4s, chạy liên tục)
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/traffic" -Method Post -ContentType "application/json" -Body '{"action":"start","delay":0.4,"requests":0}'

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
  - Thêm node mới vào cụm cân bằng tải tại runtime (tự động spawn HTTP Mock Server con nếu chưa có và đồng bộ sang Proxy :8000; trả về HTTP 409 Conflict nếu Mock hoặc Proxy chưa chạy).
  - Cập nhật trọng số (`weight`) động cho bất kỳ node nào (Consistent Hash tự tính lại Virtual Nodes, Least Connections tự cập nhật score).
  - Khôi phục danh sách node về cấu hình mặc định ban đầu (`reset`).
- **Tham số body:**
  - **Thêm node:** `{"action": "add", "id": "mock-node-4", "port": 9004, "weight": 2, "host": "127.0.0.1"}` (`id` và `port` bắt buộc; `weight` mặc định 1, `host` mặc định `127.0.0.1`)
  - **Đổi trọng số:** `{"action": "weight", "id": "mock-node-1", "weight": 10}` (`id` và `weight` bắt buộc)
  - **Khôi phục mặc định:** `{"action": "reset"}`
- **Lệnh curl:**
  ```bash
  # Thêm mock-node-4 trên cổng 9004 với trọng số 2
  curl -s -X POST http://127.0.0.1:8001/api/control/backend -H "Content-Type: application/json" -d '{"action": "add", "id": "mock-node-4", "port": 9004, "weight": 2}'

  # Cập nhật trọng số của mock-node-1 lên 10
  curl -s -X POST http://127.0.0.1:8001/api/control/backend -H "Content-Type: application/json" -d '{"action": "weight", "id": "mock-node-1", "weight": 10}'

  # Khôi phục danh sách node về mặc định ban đầu
  curl -s -X POST http://127.0.0.1:8001/api/control/backend -H "Content-Type: application/json" -d '{"action": "reset"}'
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Thêm mock-node-4 trên cổng 9004 với trọng số 2
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/backend" -Method Post -ContentType "application/json" -Body '{"action":"add","id":"mock-node-4","port":9004,"weight":2}'

  # Cập nhật trọng số của mock-node-1 lên 10
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/backend" -Method Post -ContentType "application/json" -Body '{"action":"weight","id":"mock-node-1","weight":10}'

  # Khôi phục danh sách node về mặc định ban đầu
  Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/control/backend" -Method Post -ContentType "application/json" -Body '{"action":"reset"}'
  ```

---

## 8. Luồng Sự Kiện Trực Tiếp Server-Sent Events (Real-time SSE Stream)

- **Endpoint:** `GET /api/events/stream`
- **Chức năng:** Thiết lập kết nối HTTP Streaming dạng SSE (`text/event-stream`). Máy chủ quét file `logs/access.log` định kỳ mỗi 40ms (~25fps) và phát trực tiếp các sự kiện truy cập mới về trình duyệt kèm `snapshot` trạng thái thuật toán. Điều này giúp Algorithm Decision Visualizer trên Web UI cập nhật tức thì với độ trễ 0ms ngay cả khi tải cao. Kết nối được quản lý dọn dẹp an toàn qua typed `SHUTDOWN_KEY`.
- **Định dạng dữ liệu:**
  - Thông điệp bắt đầu kết nối: `: connected\n\n`
  - Sự kiện truy cập:
    ```text
    data: {"ts": 1729158000.123, "method": "GET", "path": "/api/order", "client_ip": "192.168.1.10", "node": "mock-node-1", "status": 200, "algo": "consistent_hash", "decision": "mock-node-3#vn1|0x12|0x34|mock-node-1#vn0|0x56", "snapshot": {"type": "consistent_hash", "ring": [...]}}
    ```
- **Lệnh curl (chế độ unbuffered stream):**
  ```bash
  curl -N -s http://127.0.0.1:8001/api/events/stream
  ```
- **Lệnh PowerShell:**
  ```powershell
  # Mở kết nối stream và đọc luồng sự kiện thời gian thực
  Invoke-WebRequest -Uri "http://127.0.0.1:8001/api/events/stream"
  ```

