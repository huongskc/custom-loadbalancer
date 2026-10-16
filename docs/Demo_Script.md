# KỊCH BẢN LIVE DEMO TRỰC QUAN TRƯỚC HỘI ĐỒNG (5 - 7 PHÚT)
## ĐỀ TÀI T22: CÀI ĐẶT CÁC THUẬT TOÁN CÂN BẰNG TẢI (LOAD BALANCING ALGORITHMS)

> **Môn học:** Lập trình mạng (Network Programming) — PTIT  
> **Giảng viên hướng dẫn:** ThS. Đặng Ngọc Hùng (hungdn@ptit.edu.vn)  
> **Thời lượng Demo:** Đúng 5 - 7 phút theo barem chấm điểm  
> **Công cụ biểu diễn:** Web Dashboard Hợp Nhất (:8001) & Phương án dự phòng 5 Terminal CLI  
> **Mục tiêu:** Chứng minh 100% tính năng hoạt động thực tế: 3 thuật toán, chịu lỗi trong suốt (Fault Transparency), mở rộng động (Scale-out) và trực quan hóa toán học giải thuật.

---

## 1. PHÂN CÔNG VÀ CHUẨN BỊ TRƯỚC GIỜ BẢO VỆ

* **Người thao tác máy tính (Operator):** Thành viên 2 (ngồi cạnh laptop, chia sẻ màn hình máy chiếu, sẵn sàng thao tác chuột/bàn phím chính xác theo lời thoại).
* **Người thuyết minh (Speaker):** Thành viên 2 (hoặc kết hợp Thành viên 1) cầm micro thuyết minh dõng dạc, đồng bộ chuẩn xác với từng cú nhấp chuột.
* **Chuẩn bị môi trường (1 phút trước khi lên bục):**
  1. Mở sẵn 1 cửa sổ Terminal tại thư mục `load-balancer-t22/`.
  2. Mở sẵn trình duyệt Web (Chrome hoặc Edge) ở chế độ toàn màn hình (`F11`), phóng to kích thước chữ lên $110\%-125\%$ để toàn bộ Hội đồng ngồi xa đều nhìn rõ.
  3. Kiểm tra kết nối máy chiếu và đảm bảo các cổng `8000`, `8001`, `9001-9004` không bị ứng dụng khác chiếm giữ.

---

## 2. TIMELINE CHI TIẾT 6 PHA DEMO (TỔNG THỜI GIAN: 6 PHÚT 30 GIÂY)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        KỊCH BẢN LIVE DEMO CHUẨN (6 PHÚT 30 GIÂY)                        │
├─────────────┬──────────────────────────────────────────┬───────────────────────────────┤
│ Mốc thời gian│ Tên pha biểu diễn                        │ Trọng tâm kỹ thuật            │
├─────────────┼──────────────────────────────────────────┼───────────────────────────────┤
│ 0:00 - 1:00 │ Pha 1: Khởi động Hạ tầng 1-Click         │ Single Entry Point, Status    │
│ 1:00 - 2:15 │ Pha 2: Bắn tải & So sánh Round Robin/LC  │ SWRR mượt mà vs Least Conn    │
│ 2:15 - 3:45 │ Pha 3: Consistent Hashing & Giải mã cung │ Sticky IP & Clockwise Interval│
│ 3:45 - 5:00 │ Pha 4: Tiêm lỗi Chaos & Chịu lỗi Zero    │ Passive Failover & Zero-Error │
│ 5:00 - 6:00 │ Pha 5: Mở rộng Backend Động tại Runtime  │ Dynamic Scale-out (:9004)     │
│ 6:00 - 6:30 │ Pha 6: Dọn dẹp Tiến trình & Kết luận     │ Force Kill, Graceful Shutdown │
└─────────────┴──────────────────────────────────────────┴───────────────────────────────┘
```

---

### PHA 1: KHỞI ĐỘNG HẠ TẦNG VỚI 1 LỆNH DUY NHẤT (0:00 - 1:00)

* **Thao tác của Operator:**
  1. Tại terminal, gõ lệnh khởi động duy nhất:
     ```bash
     python web_dashboard.py
     ```
  2. Chuyển sang trình duyệt tại địa chỉ `http://localhost:8001`.
  3. Bấm nút **Khởi động** ở mục *Mock servers*.
  4. Bấm nút **Khởi động** ở mục *Reverse proxy :8000*.
* **Hiện tượng quan sát được:**
  - Ở thanh trạng thái trên cùng: Chip `Mock` chuyển sang màu xanh `đang chạy (PID)`, chip `Proxy` chuyển sang màu xanh `đang chạy (PID)`.
  - Ở lưới thẻ Backend nodes: Cả 3 thẻ node (`mock-node-1 :9001`, `mock-node-2 :9002`, `mock-node-3 :9003`) lập tức hiển thị trạng thái màu xanh `UP` với độ trễ phản hồi (latency) chỉ khoảng 1-2 ms.
* **Lời thoại thuyết minh của Speaker:**
  > *"Kính thưa Thầy, đây là giao diện Web Dashboard hợp nhất do nhóm tự phát triển độc lập, phục vụ trực tiếp từ máy chủ web_dashboard.py ở cổng 8001 mà không cần bất kỳ framework hay CDN bên ngoài nào.
  > Như Thầy thấy trên màn hình, chỉ với một cú nhấp chuột, toàn bộ cụm 3 Mock Servers trên cổng 9001, 9002, 9003 và Layer 7 Reverse Proxy trên cổng 8000 đã được khởi chạy đồng bộ. Các thẻ trạng thái đều chuyển sang màu xanh UP, sẵn sàng tiếp nhận lưu lượng mạng."*

---

### PHA 2: BẮN TẢI & SO SÁNH ROUND ROBIN VỚI LEAST CONNECTIONS (1:00 - 2:15)

* **Thao tác của Operator:**
  1. Ở khung **Sinh tải**, giữ nguyên cấu hình (Số luồng: 2, Giãn cách: 0.2s), bấm nút **Bắt đầu**.
  2. Bấm chọn thuật toán **Round Robin** trên thanh Segmented Control.
  3. Để hệ thống chạy khoảng 20 giây để bảng log và thanh tiến độ tải tích lũy dữ liệu.
  4. Sau đó bấm chuyển sang **Least Conn**.
* **Hiện tượng quan sát được:**
  - Chỉ số KPI **RPS** (Requests Per Second) lập tức nhảy lên khoảng $9.5 - 10.0 \text{ req/s}$ (đo bằng cửa sổ trượt 5 giây). Tổng số request và tỷ lệ thành công hiển thị $100\%$.
  - Ở **Round Robin:** Thanh tải % của 3 node di chuyển đều đặn, số request được chia đều luân phiên giữa các node.
  - Ở **Least Conn:** Khi có kết nối đồng thời, hệ thống tự động ưu tiên đẩy request vào node có số active connection thấp nhất. Bảng log cuộn liên tục các bản ghi màu xanh mã `200 OK`.
* **Lời thoại thuyết minh của Speaker:**
  > *"Bây giờ nhóm bắt đầu kích hoạt bộ sinh tải tự động. Ngay lập tức, chỉ số RPS đo đạc theo cửa sổ trượt 5 giây tăng lên khoảng 10 requests/giây với tỷ lệ thành công tuyệt đối 100%.
  > Khi chọn Round Robin, thanh tiến độ phân bổ tải cho thấy các request được luân phiên đan xen cực kỳ nhịp nhàng giữa 3 node, phản ánh đúng cơ chế Smooth Weighted Round Robin.
  > Khi chúng em chuyển sang Least Connections, Proxy sẽ đánh giá trực tiếp số kết nối đang xử lý đồng thời qua AsyncIO Context Manager để điều phối vào node rảnh rỗi nhất."*

---

### PHA 3: CONSISTENT HASHING, STICKY CLIENT IP & GIẢI MÃ CUNG BĂM (2:15 - 3:45)

* **Thao tác của Operator:**
  1. Bấm chọn thuật toán **Consistent Hash** trên thanh Segmented Control.
  2. Cuộn màn hình xuống bảng **20 request gần nhất**.
  3. Chỉ con trỏ chuột vào cột **Giải mã quyết định băm (Clockwise Interval Breakdown)**.
* **Hiện tượng quan sát được:**
  - Bộ đếm tổng request được reset về 0 (cơ chế Clean Slate) để bắt đầu đo lường chính xác cho thuật toán mới.
  - Khác với Round Robin luân chuyển liên tục, ở Consistent Hashing, toàn bộ các request từ cùng một Client IP (ví dụ `127.0.0.1`) luôn được định tuyến cố định (**Sticky**) vào duy nhất một node (ví dụ `mock-node-1`).
  - Trong bảng log, cột chuỗi quyết định hiển thị trực quan công thức toán học dạng:
    `[3521876420 < 3789123450 <= 3892019481] -> mock-node-1`
* **Lời thoại thuyết minh của Speaker:**
  > *"Điểm đặc sắc nhất của đồ án nằm ở thuật toán Consistent Hashing. Khi chuyển sang thuật toán này, toàn bộ request từ Client IP 127.0.0.1 đều được dính chặt (Sticky) vào một server cố định, đảm bảo tính toàn vẹn của phiên làm việc.
  > Đặc biệt, hệ thống của nhóm không phải là một 'hộp đen'. Ở bảng log thời gian thực phía dưới, nhóm đã bóc tách chuỗi quyết định toán học: Giá trị băm MD5 của Client IP nằm trong khoảng chặn giữa nút ảo phía trước và nút ảo kế tiếp theo chiều kim đồng hồ, dẫn thẳng tới server đích. Nhờ thuật toán tìm kiếm nhị phân bisect_left, việc tìm kiếm cung băm này chỉ diễn ra trong vài phần triệu giây."*

---

### PHA 4: TIÊM SỰ CỐ CHAOS & CHỨNG MINH CHỊU LỖI TRONG SUỐT (3:45 - 5:00)

* **Thao tác của Operator:**
  1. Vẫn đang giữ luồng sinh tải chạy liên tục.
  2. Ở khung **Tiêm sự cố**, chọn node mục tiêu: `mock-node-2`.
  3. Bấm nút màu đỏ: **Đánh sập**.
  4. Đợi 5 giây quan sát bảng log, sau đó bấm nút màu xanh: **Khôi phục**.
* **Hiện tượng quan sát được:**
  - Ngay khi bấm *Đánh sập*, thẻ của `mock-node-2` đổi sang màu đỏ với nhãn **`DOWN`** và thanh tải dừng lại.
  - **Điều kỳ diệu:** Trên bảng KPI, **tỷ lệ thành công vẫn giữ nguyên 100%**, hoàn toàn không có bất kỳ một mã lỗi 502 Bad Gateway nào trả về cho Client!
  - Trong bảng log: Các request lẽ ra đi vào node 2 đã được Proxy tự động chuyển tiếp tức thì (Immediate Retry) sang node khỏe mạnh tiếp theo.
  - Khi bấm *Khôi phục*: Thẻ node 2 chuyển lại màu xanh **`UP`** và bắt đầu nhận tải bình thường trở lại sau khi hết thời gian cách ly (Quarantine 10s).
* **Lời thoại thuyết minh của Speaker:**
  > *"Bây giờ, nhóm xin kiểm chứng khả năng chịu lỗi trong suốt (Fault Transparency). Chúng em sẽ đóng vai kẻ tấn công, tiêm sự cố đánh sập hoàn toàn mock-node-2 ngay khi hệ thống đang nhận tải liên tục.
  > Như Thầy thấy, thẻ node 2 đã lập tức chuyển sang màu đỏ DOWN. Nhưng nhìn lên bảng chỉ số KPI, tỷ lệ thành công vẫn là 100% màu xanh, số lượng lỗi là 0!
  > Điều này chứng minh cơ chế Passive Fault Detection và Immediate Retry của nhóm hoạt động hoàn hảo: Proxy phát hiện lỗi kết nối ngay lập tức, tự động cách ly node 2 và chuyển tiếp tức thì request sang node khác. Người dùng hoàn toàn không hề nhận ra sự cố. Khi em bấm Khôi phục, node 2 đã khỏe mạnh trở lại và tiếp tục nhận tải."*

---

### PHA 5: MỞ RỘNG BACKEND ĐỘNG TẠI RUNTIME (DYNAMIC SCALE-OUT) (5:00 - 6:00)

* **Thao tác của Operator:**
  1. Tại khung **Quản lý backend (Runtime)**, nhập thông tin node mới:
     - ID node: `mock-node-4`
     - Cổng: `9004`
     - Trọng số: `2`
  2. Bấm nút: **Thêm node**.
* **Hiện tượng quan sát được:**
  - Thông báo Toast hiển thị: *"Đã thêm mock-node-4 (cổng 9004, trọng số 2) thành công"*.
  - Lưới thẻ Backend nodes lập tức xuất hiện thẻ thứ tư: `mock-node-4 :9004` màu xanh `UP` với trọng số $W=2$.
  - Danh sách cổng của Mock servers hiển thị `9001, 9002, 9003, 9004`.
  - Ngay lập tức, thanh tải của `mock-node-4` bắt đầu tăng lên, bảng log ghi nhận các request mới bắt đầu được phân phối vào node 4 theo đúng tỷ lệ trọng số, toàn bộ quá trình diễn ra **không cần khởi động lại Reverse Proxy**!
* **Lời thoại thuyết minh của Speaker:**
  > *"Tiếp theo là tính năng mở rộng hạ tầng động (Dynamic Scale-out). Khi tải hệ thống tăng cao, chúng em có thể bổ sung ngay một máy chủ mới vào cụm lúc nửa đêm mà không cần dừng hệ thống.
  > Em vừa nhập thông số node 4 trên cổng 9004 với trọng số là 2 và bấm Thêm node. Ngay lập tức, máy chủ mock-node-4 được kích hoạt ngầm, Proxy nạp node mới vào bộ nhớ, tính toán lại 200 nút ảo trên vòng băm và chia tải ngay cho node 4 mà không làm gián đoạn bất kỳ kết nối nào đang có."*

---

### PHA 6: DỌN DẸP TIẾN TRÌNH & KẾT THÚC DEMO (6:00 - 6:30)

* **Thao tác của Operator:**
  1. Bấm nút **Dừng** ở mục *Sinh tải*.
  2. Bấm nút **Dừng** ở *Reverse proxy :8000*.
  3. Bấm nút **Dừng** ở *Mock servers*.
  4. Chuyển sang cửa sổ Terminal nhấn `Ctrl+C` để dừng `web_dashboard.py`.
* **Hiện tượng quan sát được:**
  - Các chip trạng thái chuyển về màu xám `đã dừng`.
  - Cơ chế Win32 Force Kill thu dọn sạch sẽ toàn bộ các tiến trình con, giải phóng toàn bộ các cổng mạng tức thì mà không để lại bất kỳ tiến trình chạy ngầm nào.
* **Lời thoại thuyết minh của Speaker:**
  > *"Cuối cùng, khi bấm Dừng hệ thống, cơ chế quản lý tiến trình của nhóm sẽ áp dụng phương thức Force Kill để giải phóng sạch sẽ toàn bộ các socket cổng mạng trong vài mili-giây, ngăn chặn hoàn toàn rò rỉ tài nguyên trên hệ điều hành.
  > Phần Live Demo của nhóm đến đây là kết thúc thành công tốt đẹp, chứng minh trọn vẹn toàn bộ các tính năng kỹ thuật. Chúng em xin nhường lời cho bạn [Tên TV3] trình bày phần kết luận và bước vào phần hỏi đáp Q&A!"*

---

## 3. PHƯƠNG ÁN DỰ PHÒNG: DEMO BẰNG 5 TERMINAL CỔ ĐIỂN (PLAN B)

Nếu trong phòng thi máy chiếu hoặc trình duyệt gặp sự cố bất khả kháng, Operator nhanh chóng chuyển sang phương án 5 Terminal đã được chuẩn bị sẵn:

```bash
# Terminal 1: Khởi động 3 Mock Server
python mock/mock_servers.py

# Terminal 2: Khởi động Reverse Proxy
python proxy.py

# Terminal 3: Mở Live Terminal Dashboard (Hiển thị ANSI & Progress Bar)
python scripts/dashboard.py

# Terminal 4: Bắn tải liên tục
python scripts/test_traffic.py

# Terminal 5: Tiêm lỗi và chuyển thuật toán
python scripts/chaos.py down 9002
python scripts/algo.py round_robin
```
*Tất cả thông số tải, tỷ lệ % và chuyển vùng failover vẫn hiển thị trực quan trên giao diện dòng lệnh ANSI của Terminal 3.*
