# HƯỚNG DẪN DÀNH CHO THÀNH VIÊN NHÓM (TEAM SETUP & REHEARSAL GUIDE)
## ĐỀ TÀI T22: CÀI ĐẶT CÁC THUẬT TOÁN CÂN BẰNG TẢI (LOAD BALANCING ALGORITHMS)

> **Môn học:** Lập trình mạng (Network Programming) — PTIT  
> **Giảng viên hướng dẫn:** ThS. Đặng Ngọc Hùng (hungdn@ptit.edu.vn)  
> **Nhóm thực hiện:** Tối đa 03 thành viên theo quy chế môn học  
> **Mã nguồn dự án:** `load-balancer-t22/`  
> **Trạng thái kỹ thuật:** 59/59 tests PASSED (100%), Web Dashboard hoàn chỉnh  

---

## 1. TỔNG QUAN VÀ PHÂN CÔNG VAI TRÒ NHÓM (03 THÀNH VIÊN)

Theo yêu cầu môn học trong `network-programing-topic.md`, mỗi nhóm tối đa 03 sinh viên. Tổng thời gian thuyết trình trước Hội đồng là **15-20 phút** (Lý thuyết: 10-12 phút, Live Demo: 5-7 phút, Q&A: 3-5 phút).

Nhóm phân chia 3 vai trò rõ ràng, bổ trợ lẫn nhau:

| Thành viên | Vai trò chính | Nhiệm vụ chi tiết | Tài liệu cần nắm vững |
| :--- | :--- | :--- | :--- |
| **Thành viên 1**<br>*(Trưởng nhóm / Trình bày Lý thuyết)* | **Lý thuyết & Cơ sở Giải thuật** | - Thuyết trình phần đặt vấn đề, Layer 4 vs Layer 7, bài toán SPOF.<br>- Trình bày bản chất toán học của 3 thuật toán: SWRR, Least Connections, Consistent Hashing ($V \text{ vnodes}, \sigma \approx 1/\sqrt{V}$).<br>- Giải thích cơ chế Chịu lỗi thụ động (Passive Failover & Immediate Retry). | `THEORY_FOUNDATION.md`<br>`Slide_Outline.md` (Slide 1-9) |
| **Thành viên 2**<br>*(Lập trình viên / Demo Operator)* | **Kiến trúc Hệ thống & Live Demo** | - Trình bày kiến trúc Data Plane (:8000) và Control Plane (:8001).<br>- Trực tiếp thao tác máy tính thực hiện Live Demo trên Web Dashboard (:8001) trong 5-7 phút theo kịch bản chuẩn.<br>- Thuyết minh các pha: Chuyển đổi thuật toán, Tiêm sự cố Chaos, Thêm node động tại runtime. | `Demo_Script.md`<br>`api.md`<br>`README.md`<br>`Slide_Outline.md` (Slide 10-13) |
| **Thành viên 3**<br>*(Kiểm thử / Phản biện & Q&A)* | **Chất lượng Mã nguồn, Đổi mới & Trả lời Q&A** | - Trình bày kết quả kiểm thử tự động (59/59 tests pass), tính đổi mới và ứng dụng thực tế.<br>- Minh bạch công cụ AI (AI Tool Disclosure theo quy chế PTIT).<br>- Đứng chính trả lời các câu hỏi vấn đáp xoáy sâu từ Giảng viên và Hội đồng phản biện. | `QA_DEFENSE_GUIDE.md`<br>`tests/`<br>`Slide_Outline.md` (Slide 14-15) |

---

## 2. HƯỚNG DẪN THIẾT LẬP MÔI TRƯỜNG CHỈ TRONG 3 PHÚT

Dự án được thiết kế **Zero-External-Dependency** (không cần Docker, không cần Redis/Nginx, không cần cài đặt Node.js/npm hay kết nối Internet khi chạy).

### Bước 1: Clone mã nguồn và mở thư mục dự án
```bash
git clone <URL_REPO_CUA_NHOM>
cd load-balancer-t22
```

### Bước 2: Kiểm tra phiên bản Python
Dự án yêu cầu **Python 3.10 trở lên** (hỗ trợ tốt nhất cú pháp gõ kiểu union `int | str` và AsyncIO hiện đại):
```bash
python --version
# Kết quả mong đợi: Python 3.10.x, 3.11.x, 3.12.x hoặc 3.13.x
```

### Bước 3: Tạo môi trường ảo (Khuyên dùng) và cài đặt thư viện
```bash
# Tạo môi trường ảo venv
python -m venv venv

# Kích hoạt trên Windows PowerShell:
.\venv\Scripts\Activate.ps1
# (Hoặc Windows CMD: .\venv\Scripts\activate.bat)
# (Hoặc Linux/macOS: source venv/bin/activate)

# Cài đặt các thư viện tối giản (chỉ gồm aiohttp, pyyaml, pytest):
pip install -r requirements.txt
```

---

## 3. XÁC MINH TOÀN BỘ HỆ THỐNG KIỂM THỬ (TEST VERIFICATION)

Trước khi tiến hành chạy thử hay demo, mọi thành viên **bắt buộc** phải chạy lệnh kiểm thử để đảm bảo mã nguồn trên máy hoạt động 100%:

```bash
python -m pytest
```

### Kết quả mong đợi (Xanh 100%):
```text
============================= test session starts =============================
platform win32 -- Python 3.1x.x, pytest-x.x.x
rootdir: ...\load-balancer-t22
collected 60 items

mock\test_mock.py s                                                      [  1%]
tests\test_backend_management.py ........                                [ 15%]
tests\test_base.py ......                                                [ 25%]
tests\test_consistent_hash.py ........                                   [ 38%]
tests\test_least_connections.py ......                                   [ 48%]
tests\test_proxy.py .......                                              [ 60%]
tests\test_round_robin.py .......                                        [ 71%]
tests\test_traffic_sim.py ........                                       [ 85%]
tests\test_web_dashboard.py .........                                    [100%]

======================= 59 passed, 1 skipped in ~15s =======================
```
*(Ghi chú: 1 test skipped ở `mock/test_mock.py` là hoàn toàn bình thường vì cụm mock chưa được bật ở chế độ standalone).*

---

## 4. HƯỚNG DẪN KHỞI CHẠY VẬN HÀNH

Hệ thống hỗ trợ 2 chế độ vận hành: **Chế độ Hợp nhất Web Dashboard (Ưu tiên số 1 khi báo cáo)** và **Chế độ 5 Terminal Cổ điển (Dùng làm phương án dự phòng)**.

### Cách 1: Chế độ Web Dashboard Hợp Nhất (Single Entry Point — 1 Lệnh Duy Nhất)

Đây là chế độ **khuyên dùng tuyệt đối** khi thuyết trình trước Giảng viên vì trực quan, hiện đại, không phải nhảy qua lại nhiều cửa sổ terminal.

1. Mở duy nhất 1 cửa sổ terminal và gõ:
   ```bash
   python web_dashboard.py
   ```
2. Mở trình duyệt Web (Chrome / Edge / Firefox) tại địa chỉ:
   ```text
   http://localhost:8001
   ```
3. Trên giao diện Web:
   - **Bật hạ tầng:** Bấm nút **Khởi động** ở mục *Mock servers*, sau đó bấm **Khởi động** ở *Reverse proxy :8000*. Quan sát 3 thẻ node chuyển sang màu xanh `UP`.
   - **Bắn tải:** Bấm **Bắt đầu** ở mục *Sinh tải*. Quan sát thanh tỷ lệ tải % di chuyển, chỉ số RPS hiển thị theo thời gian thực và bảng 20 request log cuộn liên tục.
   - **Chuyển thuật toán:** Nhấp chọn giữa `Round Robin`, `Least Conn`, `Consistent Hash`.
   - **Tiêm lỗi sự cố:** Chọn `mock-node-2`, bấm **Đánh sập** $\to$ quan sát node chuyển `DOWN`, lưu lượng né sang node khác, 100% request vẫn thành công (200 OK). Bấm **Khôi phục** để đưa node trở lại bình thường.
   - **Mở rộng node động:** Nhập ID `mock-node-4`, cổng `9004`, trọng số `2` và bấm **Thêm node** $\to$ node 4 lập tức xuất hiện và nhận tải ngay tại runtime!
   - **Dừng:** Bấm **Dừng** lần lượt hoặc chỉ cần nhấn `Ctrl+C` tại terminal chạy `web_dashboard.py` (cơ chế Force Kill sẽ tự động quét sạch mọi tiến trình con).

---

### Cách 2: Chế độ 5 Terminal Cổ Điển (Phương án Dự phòng Backup)

Nếu máy tính phòng hội đồng không mở được trình duyệt hoặc gặp lỗi cổng:

| Terminal | Lệnh thực thi | Mục đích |
| :---: | :--- | :--- |
| **Terminal 1** | `python mock/mock_servers.py` | Khởi động 3 Mock Server trên các cổng 9001, 9002, 9003 |
| **Terminal 2** | `python proxy.py` | Khởi động Reverse Proxy Server Layer 7 tại cổng 8000 |
| **Terminal 3** | `python scripts/dashboard.py` | Màn hình quan sát trực tiếp trên terminal (bảng ANSI, progress bar) |
| **Terminal 4** | `python scripts/test_traffic.py` | Bắn tải HTTP tự động với tần suất ~2 req/s |
| **Terminal 5** | `python scripts/chaos.py down 9002`<br>`python scripts/chaos.py up 9002`<br>`python scripts/algo.py round_robin` | Công cụ gõ lệnh tiêm sự cố và đổi thuật toán tại runtime |

---

## 5. NHỮNG LƯU Ý KỸ THUẬT VÀ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

### 1. Lỗi xung đột cổng mạng (Port Already in Use)
- **Triệu chứng:** Terminal báo `OSError: [Errno 10048] address already in use` trên cổng 8000, 8001 hoặc 9001-9003 do phiên chạy trước chưa giải phóng cổng.
- **Xử lý nhanh trên Windows PowerShell:**
  ```powershell
  # Tìm và dừng tiến trình chiếm cổng 8000 hoặc 8001
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8001).OwningProcess | Stop-Process -Force
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
  ```
- **Hoặc đổi cổng Dashboard:** `python web_dashboard.py --port 8002`

### 2. Lệnh `curl` trên Windows PowerShell
- Trên PowerShell, `curl` mặc định là alias của `Invoke-WebRequest`.
- **Luôn gõ:** `curl.exe` (ví dụ: `curl.exe http://127.0.0.1:8000/api/order`) hoặc dùng cmdlet native: `Invoke-RestMethod http://127.0.0.1:8001/api/stats`.

### 3. File log `logs/access.log`
- Hệ thống tự động làm sạch file log mỗi khi khởi động lại Proxy. Nếu muốn xem trực tiếp dòng log đang ghi:
  - PowerShell: `Get-Content logs/access.log -Wait -Tail 20`
  - Linux/macOS: `tail -f logs/access.log`

---

## 6. KẾ HOẠCH LUYỆN TẬP NHÓM (REHEARSAL CHECKLIST)

Trước ngày lên bảo vệ trước ThS. Đặng Ngọc Hùng, cả 3 thành viên cần thực hiện ít nhất **2 buổi diễn tập thử (Rehearsal)**:

- [ ] **Buổi 1 — Khớp nối Lời thoại & Thời gian (Time Boxing):**
  - Bấm giờ đúng 11 phút cho phần thuyết trình lý thuyết và kiến trúc (Thành viên 1 & Thành viên 2).
  - Bấm giờ đúng 5 phút cho phần thao tác Live Demo (Thành viên 2).
  - Chuẩn bị tinh thần chuyển slide nhịp nhàng giữa các thành viên.
- [ ] **Buổi 2 — Vấn đáp Giả lập (Mock Defense):**
  - Thành viên 1 và 2 đóng vai Hội đồng phản biện, sử dụng tài liệu `QA_DEFENSE_GUIDE.md` để đặt các câu hỏi hóc búa cho Thành viên 3 (ví dụ: *Tại sao không dùng L4?*, *Bảo vệ SPOF ra sao?*, *Virtual Nodes chứng minh toán học thế nào?*, *Hiện tượng Thundering Herd giải quyết ra sao?*).
  - Hoán đổi vị trí để đảm bảo **cả 3 thành viên đều có thể trả lời được mọi câu hỏi**.
- [ ] **Kiểm tra Thiết bị (Day Before):**
  - Chuẩn bị ít nhất **2 laptop** có sẵn mã nguồn và môi trường Python đã test thành công 59/59 tests.
  - Chuẩn bị đầu chuyển HDMI/Type-C để kết nối máy chiếu phòng học PTIT.
  - Tải sẵn slide định dạng PDF phòng trường hợp lỗi font máy chiếu.
