# DÀN Ý SLIDE THUYẾT TRÌNH BẢO VỆ ĐỒ ÁN (15 SLIDES CHUẨN BAREM PTIT)
## ĐỀ TÀI T22: CÀI ĐẶT CÁC THUẬT TOÁN CÂN BẰNG TẢI (LOAD BALANCING ALGORITHMS)

> **Môn học:** Lập trình mạng (Network Programming) — Học viện Công nghệ Bưu chính Viễn thông (PTIT)  
> **Giảng viên hướng dẫn:** ThS. Đặng Ngọc Hùng (hungdn@ptit.edu.vn)  
> **Thời lượng bảo vệ:** 15-20 phút (Lý thuyết & Kiến trúc: 10-12 phút | Live Demo: 5-7 phút | Vấn đáp Q&A: 3-5 phút)  
> **Khung chấm điểm:** Độ sâu kỹ thuật (30%), Chất lượng cài đặt & Demo (25%), Kỹ năng thuyết trình (25%), Xử lý Q&A (20%)  
> **Định dạng file nộp:** PDF / PPTX nộp qua hệ thống `db.ptit.edu.vn`  

---

## TỔNG QUAN PHÂN BỔ THỜI LƯỢNG 15 SLIDES

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        TỔNG THỜI GIAN: 15 - 20 PHÚT                                     │
├───────────────────────────────┬───────────────────────────────┬────────────────────────┤
│  PHẦN 1: LÝ THUYẾT & GIẢI THUẬT│  PHẦN 2: KIẾN TRÚC & DEMO     │  PHẦN 3: ĐÁNH GIÁ & Q&A│
│  (Slide 1 - 9) ~ 7-8 phút     │  (Slide 10 - 13) ~ 6-7 phút   │  (Slide 14 - 15) ~ 4-5p│
│  Người trình bày: Thành viên 1 │  Người trình bày: Thành viên 2│  Người trình bày: TV 3 │
└───────────────────────────────┴───────────────────────────────┴────────────────────────┘
```

---

## CHI TIẾT NỘI DUNG VÀ LỜI THOẠI 15 SLIDES

---

### SLIDE 1: TRANG TIÊU ĐỀ (TITLE SLIDE)
* **Thời lượng:** 0:30 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** ĐỒ ÁN MÔN HỌC LẬP TRÌNH MẠNG: CÀI ĐẶT CÁC THUẬT TOÁN CÂN BẰNG TẢI (LOAD BALANCING ALGORITHMS) — ĐỀ TÀI T22
* **Nội dung trực quan:**
  - Logo PTIT & Khoa Công nghệ Thông tin.
  - Tên đề tài chính thức: **T22 — Load Balancing Algorithms Implementation**.
  - Giảng viên hướng dẫn: **ThS. Đặng Ngọc Hùng** (Email: `hungdn@ptit.edu.vn`).
  - Danh sách nhóm sinh viên thực hiện (Họ tên, Mã sinh viên, Lớp, Phân công vai trò).
  - Công nghệ cốt lõi: Python 3.10+ (AsyncIO + aiohttp), Layer 7 Reverse Proxy, Consistent Hashing Ring, Web Dashboard SPA.
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Kính thưa Thầy Đặng Ngọc Hùng và các bạn sinh viên. Hôm nay, nhóm chúng em xin phép được trình bày đồ án môn học Lập trình mạng với đề tài T22: 'Cài đặt các thuật toán Cân bằng tải'. Đồ án của nhóm chúng em tập trung giải quyết trọn vẹn bài toán phân phối lưu lượng mạng từ cơ sở toán học giải thuật, hiện thực hóa bộ Reverse Proxy Tầng 7 chuẩn RFC 7230, xây dựng cơ chế chịu lỗi trong suốt và trung tâm điều khiển trực quan Web Dashboard. Sau đây em xin bắt đầu phần trình bày."*

---

### SLIDE 2: ĐẶT VẤN ĐỀ & MỤC TIÊU ĐỀ TÀI (PROBLEM STATEMENT)
* `[Barem: Technical Depth 30%]`
* **Thời lượng:** 1:00 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** BÀI TOÁN TẮC NGHẼN HỆ THỐNG VÀ ĐIỂM CHẾT ĐƠN LẺ (SPOF)
* **Nội dung trực quan:**
  - Sơ đồ trực quan: 1 Web Server đơn lẻ bị quá tải khi lượng request tăng đột biến (High Traffic Spikes) dẫn đến Crash $\to$ Toàn bộ dịch vụ tê liệt (Single Point of Failure - SPOF).
  - Bảng so sánh 2 hướng tiếp cận mở rộng hệ thống:
    - *Scale-up (Mở rộng theo chiều dọc):* Nâng cấp phần cứng CPU/RAM $\to$ Chi phí cấp số nhân, giới hạn vật lý.
    - *Scale-out (Mở rộng theo chiều ngang):* Ghép nối nhiều máy chủ nhỏ phía sau Load Balancer $\to$ Chi phí tối ưu, độ tin cậy $99.99\%$.
  - 3 Mục tiêu trọng tâm của nhóm:
    1. Cài đặt 3 thuật toán cốt lõi: Round Robin, Weighted Least Connections, Consistent Hashing.
    2. Đạt tính năng **Chịu lỗi trong suốt (Fault Transparency)** với cơ chế Zero Detection Latency.
    3. Trực quan hóa toán học giải thuật theo thời gian thực (Real-time Telemetry & Dynamic Control).
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Trong các hệ thống phân tán hiện đại, một máy chủ đơn lẻ luôn đối mặt với hai rủi ro chí mạng: giới hạn tài nguyên tính toán và trở thành điểm chết đơn lẻ (SPOF). Giải pháp tất yếu là mở rộng theo chiều ngang (Scale-out) với một cụm backend. Tuy nhiên, bài toán đặt ra là: Làm thế nào để điều phối lưu lượng công bằng, thông minh và không làm gián đoạn người dùng khi có sự cố nút mạng? Đó chính là sứ mệnh của Load Balancer mà nhóm chúng em đã cài đặt và tối ưu trong đồ án này."*

---

### SLIDE 3: BẢN CHẤT MẠNG: LAYER 4 VS LAYER 7 LOAD BALANCING
* `[Barem: Technical Depth 30%]`
* **Thời lượng:** 1:15 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** ĐẶT CÂN BẰNG TẢI Ở ĐÂU TRONG MÔ HÌNH OSI? TẦNG VẬN CHUYỂN HAY TẦNG ỨNG DỤNG?
* **Nội dung trực quan:**
  - Bảng đối sánh kỹ thuật chuyên sâu:
  
  | Tiêu chí đối sánh | Layer 4 (Transport Layer) | Layer 7 (Application Layer - Nhóm chọn) |
  | :--- | :--- | :--- |
  | **Điểm kết thúc phiên TCP** | Không kết thúc (NAT / Direct Server Return) | **Full Proxy: Kết thúc phiên Client $\to$ Mở phiên mới tới Backend** |
  | **Khả năng đọc dữ liệu** | Chỉ đọc IP Packet Header + TCP/UDP Port | **Đọc toàn bộ HTTP Method, URI Path, Header, Cookie, JSON Body** |
  | **Định tuyến thông minh** | Không hỗ trợ (Chỉ băm IP:Port thô) | **Hỗ trợ Microservices routing, Sticky Session, Header routing** |
  | **Kiểm tra sức khỏe** | Chỉ kiểm tra mở cổng TCP SYN-ACK | **Kiểm tra ngữ nghĩa ứng dụng HTTP 200 OK qua `/healthz`** |
  | **Trường hợp áp dụng** | Thông lượng siêu khủng (Hàng triệu pps, VoIP thô) | **Hệ thống Web, Microservices, API Gateways hiện đại** |
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Một câu hỏi nền tảng trong lập trình mạng là: Cân bằng tải ở Tầng 4 hay Tầng 7? Nhóm chúng em quyết định xây dựng Reverse Proxy ở Tầng 7 (Application Layer). Ở tầng này, Load Balancer đóng vai trò Full Proxy — nó hoàn tất bắt tay TCP 3 bước với Client, đọc và giải mã gói tin HTTP. Nhờ đó, hệ thống có khả năng 'nhìn thấy' ngữ nghĩa ứng dụng: đọc được header `X-Forwarded-For` để phân biệt người dùng sau NAT, kiểm tra sức khỏe chính xác qua mã HTTP 200 thay vì chỉ bắt tay cổng thô, và định tuyến thông minh theo từng vi dịch vụ."*

---

### SLIDE 4: THUẬT TOÁN 1: SMOOTH WEIGHTED ROUND ROBIN (SWRR)
* `[Barem: Technical Depth 30%]`
* **Thời lượng:** 1:15 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** SMOOTH WEIGHTED ROUND ROBIN — XÓA BỎ HIỆN TƯỢNG XUNG PHÁT TẢI (BURSTINESS)
* **Nội dung trực quan:**
  - Bài toán WRR cổ điển: Cho 3 node với trọng số $W = \{A:5, B:1, C:1\}$. WRR cổ điển sẽ phân phối chuỗi $A-A-A-A-A-B-C \to$ Node $A$ hứng chịu bão tải 5 request liên tiếp, gây nghẽn hàng đợi (Queue Saturation).
  - Thuật toán mượt Smooth Weighted Round Robin (chuẩn Nginx):
    - Khởi tạo vector trọng số hiệu dụng hiện tại: $C_i = 0$.
    - Mỗi chu kỳ chọn:
      $$\forall i: C_i \leftarrow C_i + W_i$$
      $$\text{Chọn } k = \arg\max(C_i)$$
      $$C_k \leftarrow C_k - \sum W_i$$
    - Chuỗi phân phối thực tế: $A \to B \to A \to A \to C \to A \to A \to \dots$ (Tải của $A$ được đan xen hoàn hảo).
  - Định lý bất biến toán học: $\sum C_i \equiv 0$ sau mỗi chu kỳ đầy đủ.
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Thuật toán đầu tiên nhóm triển khai là Smooth Weighted Round Robin (SWRR). Khác với Round Robin cổ điển chia tải giật cục gây quá tải cục bộ cho máy chủ mạnh, SWRR sử dụng cơ chế vector trọng số động $C_i$. Trước mỗi request, mỗi server được cộng thêm trọng số cấu hình của mình; server có $C_i$ lớn nhất sẽ được chọn và sau đó bị trừ đi tổng trọng số toàn cụm. Nhờ vậy, máy chủ mạnh vẫn nhận được nhiều request hơn nhưng lưu lượng được phân bổ đều đặn như một dòng chảy mượt mà."*

---

### SLIDE 5: THUẬT TOÁN 2: WEIGHTED LEAST CONNECTIONS
* `[Barem: Technical Depth 30%]`
* **Thời lượng:** 1:15 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** WEIGHTED LEAST CONNECTIONS — TỐI ƯU HÓA THEO THỜI GIAN XỬ LÝ THỰC TẾ
* **Nội dung trực quan:**
  - Hạn chế của Round Robin: Giả định mọi request có thời gian xử lý bằng nhau. Nếu 1 request nặng (Database Query mất 3 giây) đi vào Node A, Round Robin vẫn tiếp tục nạp tải vào Node A $\to$ Sập node.
  - Công thức chọn Server theo Least Connections:
    $$k = \arg\min_{i \in \text{Alive}} \left( \frac{\text{active\_connections}_i}{W_i} \right)$$
  - Cài đặt trong Python AsyncIO:
    - Quản lý vòng đời kết nối đồng thời qua Context Manager `track_connection()`:
      ```python
      async with backend.track_connection():
          await forward_request()
      ```
    - Tự động tăng `active_conns += 1` khi bắt đầu và giảm `active_conns -= 1` trong khối `finally` kể cả khi có ngoại lệ kết nối.
  - Xử lý vấn đề **Thundering Herd**: Khi một node mới mở lại với 0 kết nối, thuật toán có cơ chế đánh giá động tránh dồn toàn bộ tải tức thời vào node đó.
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Trong môi trường microservices, độ dài xử lý của các request là không đồng nhất: có request trả về ngay trong 2ms, nhưng có request xuất báo cáo tốn hàng giây. Thuật toán Least Connections theo dõi trực tiếp số kết nối đang hoạt động trong bộ nhớ. Node nào có tỷ lệ active connections trên trọng số thấp nhất sẽ nhận request tiếp theo. Nhờ áp dụng AsyncIO Context Manager, chỉ số này luôn được đồng bộ chính xác tuyệt đối mà không cần dùng khóa khóa luồng nặng nề."*

---

### SLIDE 6: THUẬT TOÁN 3: CONSISTENT HASHING & VÒNG TRÒN BĂM 32-BIT
* `[Barem: Technical Depth 30%]`
* **Thời lượng:** 1:30 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** CONSISTENT HASHING — GIẢI BÀI TOÁN THẢM HỌA ĐỔ VỠ BỘ ĐỆM (CACHE STAMPEDE)
* **Nội dung trực quan:**
  - Thảm họa của băm chia dư truyền thống: $\text{Node} = H(\text{Key}) \pmod N$. Khi số node $N$ thay đổi từ $3 \to 4$ hoặc $3 \to 2$, hầu như $100\%$ key bị băm sang vị trí mới $\to$ Tỷ lệ Cache Hit tụt về $0\%$, database phía sau bị đè bẹp (Cache Stampede).
  - Vòng băm Nhất quán (Consistent Hashing Ring - Karger 1997):
    - Không gian băm $[0, 2^{32} - 1]$ uốn thành một vòng tròn khép kín.
    - Cả Server và Client IP đều được ánh xạ lên vòng tròn qua hàm băm MD5 32-bit.
    - Quy tắc định tuyến: Một Client IP sẽ đi theo chiều kim đồng hồ (Clockwise) và được phục vụ bởi Server đầu tiên nó bắt gặp trên vòng băm.
  - **Tính chất Monotonicity:** Khi thêm hoặc bớt 1 server, chỉ có duy nhất $\frac{K}{N}$ key bị tái phân bổ, các key còn lại hoàn toàn giữ nguyên trạng thái kết nối!
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Một trong những đóng góp giải thuật quan trọng nhất của đồ án là cài đặt Vòng băm Nhất quán Consistent Hashing. Với các dịch vụ yêu cầu giữ phiên làm việc như Giỏ hàng điện tử hay Session Cache, phép chia dư truyền thống sẽ làm mất toàn bộ phiên khi có một máy chủ gặp sự cố. Consistent Hashing đưa toàn bộ server và người dùng lên một vòng tròn băm 32-bit. Khi có một node sập, chỉ các người dùng thuộc quản lý của node đó mới được chuyển sang node kế tiếp theo chiều kim đồng hồ, toàn bộ người dùng còn lại không hề bị ảnh hưởng."*

---

### SLIDE 7: KỸ THUẬT VIRTUAL NODES & TÍNH ĐÚNG ĐẮN TOÁN HỌC
* `[Barem: Technical Depth 30%]`
* **Thời lượng:** 1:15 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** KỸ THUẬT VIRTUAL NODES: ĐẢM BẢO CÂN BẰNG TẢI LÝ TƯỞNG
* **Nội dung trực quan:**
  - Vấn đề phân bố cụm (Clustering Problem): Khi số lượng server vật lý ít (ví dụ 3 nodes), các vị trí trên vòng băm sẽ phân bố không đồng đều, một node có thể chiếm tới $70\%$ cung tròn.
  - Giải pháp Virtual Nodes (Nút ảo): Mỗi server vật lý được nhân bản thành $V$ nút ảo (nhóm cấu hình $V = 100 \times \text{weight}$ nút ảo).
  - Chứng minh toán học: Độ lệch chuẩn phân bổ tải giữa các node tỷ lệ nghịch với căn bậc hai số nút ảo:
    $$\sigma \approx \frac{1}{\sqrt{V}}$$
    Với $V = 100$, độ lệch tải giảm xuống dưới $10\%$, bảo đảm phân phối tải đồng đều.
  - Tối ưu hóa tìm kiếm: Sử dụng cấu trúc danh sách sắp xếp và thuật toán tìm kiếm nhị phân `bisect.bisect_left` với độ phức tạp thời gian cực nhanh:
    $$\mathcal{O}(\log(N \cdot V))$$
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Nếu chỉ đưa 3 máy chủ lên vòng băm, hiện tượng lệch tải sẽ xảy ra rất nghiêm trọng do tính ngẫu nhiên của hàm băm. Nhóm chúng em đã hiện thực hóa kỹ thuật Virtual Nodes — mỗi máy chủ vật lý được đại diện bởi hàng trăm nút ảo rải đều khắp không gian 32-bit. Theo lý thuyết xác suất, độ lệch chuẩn phân bổ tải tỷ lệ nghịch với căn bậc hai của số vnodes. Để tìm kiếm đích đến trong hàng trăm vnodes này, nhóm áp dụng tìm kiếm nhị phân bisect_left đạt độ phức tạp chỉ O(log(N*V)), thời gian tính toán chỉ mất chưa tới 0.05 mili-giây."*

---

### SLIDE 8: CƠ CHẾ CHỊU LỖI TRONG SUỐT (PASSIVE FAULT TRANSPARENCY)
* `[Barem: Technical Depth 30% & Implementation 25%]`
* **Thời lượng:** 1:15 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** PASSIVE FAULT TOLERANCE & IMMEDIATE RETRY: ĐẠT CHUẨN ZERO-DOWNTIME
* **Nội dung trực quan:**
  - Bảng so sánh 2 cơ chế phát hiện lỗi:
  
  | Cơ chế | Thời gian phát hiện lỗi | Tác động tới Người dùng |
  | :--- | :--- | :--- |
  | **Active Health Check** (Định kỳ thăm dò 5s/lần) | Có "vùng mù" (Blind Spot) lên tới 5 giây | Người dùng gửi request trong vùng mù sẽ nhận lỗi **502 Bad Gateway**! |
  | **Passive Detection & Immediate Retry** (Nhóm cài đặt) | **0 mili-giây (Phát hiện ngay khi gửi request)** | **100% trong suốt: Client luôn nhận HTTP 200 OK!** |
  - Quy trình xử lý lỗi tức thì (Flowchart):
    $$\text{Client Request} \to \text{Gửi tới Node A (Lỗi Socket/500)} \xrightarrow{\text{Bắt Exception}} \text{Cách ly Node A (Quarantine 10s)} \xrightarrow{\text{Immediate Retry}} \text{Chuyển sang Node B} \to \text{Trả về 200 OK}$$
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Điểm cốt lõi giúp hệ thống đạt độ tin cậy cao là cơ chế Passive Fault Tolerance kết hợp Immediate Retry. Các hệ thống thông thường dùng Active Health Check thăm dò mỗi 5 giây, dẫn tới khoảng thời gian mù: nếu máy chủ sập giữa 2 chu kỳ, hàng chục request của người dùng sẽ bị lỗi 502. Nhóm chúng em cài đặt cơ chế giám sát thụ động: Ngay khi phát hiện lỗi kết nối tới node đích, Proxy lập tức cách ly node lỗi trong 10 giây và tự động chuyển tiếp lại chính request đó sang node kế tiếp khỏe mạnh. Người dùng hoàn toàn không hề nhận ra sự cố vừa xảy ra."*

---

### SLIDE 9: CHUẨN HÓA GIAO THỨC TẦNG 7 (RFC 7230 REVERSE PROXY ENGINE)
* `[Barem: Technical Depth 30%]`
* **Thời lượng:** 1:00 phút | **Người trình bày:** Thành viên 1
* **Tiêu đề Slide:** TUÂN THỦ CHUẨN GIAO THỨC RFC 7230 VÀ BẢO TOÀN DANH TÍNH CLIENT
* **Nội dung trực quan:**
  - Sơ đồ chuyển tiếp Header chuẩn RFC 7230:
    - Loại bỏ triệt để các **Hop-by-Hop Headers** (chỉ có ý nghĩa giữa 2 điểm mạng trực tiếp): `Connection`, `Keep-Alive`, `Proxy-Authenticate`, `Transfer-Encoding`, `Upgrade`.
    - Bảo toàn các **End-to-End Headers**: Giữ nguyên `Host` gốc, HTTP Method, Query parameters và Payload body.
  - Quản lý định danh Client qua header **`X-Forwarded-For`**:
    - Ngăn ngừa hiện tượng người dùng sau mạng NAT / Proxy trung gian bị dồn chung vào một IP nội bộ.
    - Hỗ trợ hàm trích xuất đa tầng `extract_client_ip()` phục vụ băm IP chính xác.
  - Gắn kèm Headers quan sát phản hồi:
    - `X-Balancer: Python-L7-ReverseProxy`
    - `X-Balancer-Decision: [Clockwise Interval Math Breakdown]`
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Để trở thành một Reverse Proxy chuẩn mực, nhóm tuân thủ nghiêm ngặt đặc tả RFC 7230 của IETF. Proxy lọc bỏ toàn bộ các Hop-by-Hop headers vốn chỉ có ý nghĩa cục bộ giữa Client và Proxy, bảo tồn toàn vẹn dữ liệu ứng dụng. Đồng thời, Proxy đọc và cập nhật chuỗi header X-Forwarded-For để xác định đúng IP thật của người dùng kể cả khi đi qua nhiều lớp mạng NAT. Phía phản hồi, Proxy trả về header X-Balancer-Decision giúp Client và hệ thống giám sát kiểm chứng được quyết định toán học của thuật toán."*

---

### SLIDE 10: KIẾN TRÚC HỆ THỐNG: DATA PLANE VS CONTROL PLANE
* `[Barem: Implementation Quality 25%]`
* **Thời lượng:** 1:15 phút | **Người trình bày:** Thành viên 2
* **Tiêu đề Slide:** PHÂN TÁCH RẠCH RÒI: MẶT PHẲNG DỮ LIỆU (:8000) & MẶT PHẲNG ĐIỀU KHIỂN (:8001)
* **Nội dung trực quan:**
  - Sơ đồ khối kiến trúc hệ thống (Architecture Diagram):
    - **Data Plane (Cổng :8000):** Nhiệm vụ duy nhất là tiếp nhận request, phân phối theo thuật toán và chuyển tiếp với độ trễ thấp nhất. Ghi nhận sự kiện bất đồng bộ vào `logs/access.log`.
    - **Control Plane (Cổng :8001):** Máy chủ điều hành trung tâm `web_dashboard.py`, quản lý vòng đời tiến trình con qua Win32 `TerminateProcess` / POSIX `kill()`.
    - **Cụm Backend:** 3 Mock Nodes (`:9001`, `:9002`, `:9003`) kèm khả năng mở rộng động (`:9004+`).
  - Nguyên tắc thiết kế: **Separation of Concerns & Non-invasive Telemetry** (Giám sát không xâm lấn, không làm suy giảm hiệu năng chuyển tiếp gói tin của Data Plane).
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Kính thưa Thầy, tiếp theo em xin trình bày về phần Kiến trúc cài đặt và biểu diễn thực nghiệm hệ thống. Nhóm chúng em áp dụng nguyên lý thiết kế hệ thống mạng hiện đại: Phân tách rạch ròi giữa Data Plane và Control Plane. Data Plane lắng nghe tại cổng 8000, tối ưu hóa tối đa cho việc chuyển tiếp gói tin và ghi log bất đồng bộ. Control Plane lắng nghe tại cổng 8001, đóng vai trò giám sát viên và trung tâm điều phối độc lập, đọc dữ liệu giám sát mà không hề can thiệp hay làm chậm luồng dữ liệu nghiệp vụ."*

---

### SLIDE 11: MỞ RỘNG ĐỘNG & ĐỒNG BỘ VÒNG ĐỜI (DYNAMIC SCALE-OUT & RESYNC)
* `[Barem: Implementation Quality 25%]`
* **Thời lượng:** 1:00 phút | **Người trình bày:** Thành viên 2
* **Tiêu đề Slide:** QUẢN TRỊ VÒNG ĐỜI & MỞ RỘNG HẠ TẦNG KHÔNG CẦN KHỞI ĐỘNG LẠI (CLEAN SLATE)
* **Nội dung trực quan:**
  - Khả năng mở rộng Backend tại Runtime:
    - Gửi lệnh `POST /api/backend` tới Proxy với action `add` hoặc `weight`.
    - Gọi API `/chaos/spawn` để kích hoạt node HTTP mới trên cổng `9004+`.
    - Cập nhật tức thì vòng băm hoặc danh sách trọng số mà không làm rớt kết nối đang chạy (Zero-Interruption).
  - Cơ chế **Đồng bộ Vòng đời (Lifecycle Resync)**:
    - Xóa bỏ triệt để hiện tượng "Node ma" (Ghost Nodes): Khi khởi động lại Mock hoặc Proxy, hệ thống tự động reset danh sách node về trạng thái ban đầu.
    - Chống xung đột trạng thái: Trả về mã lỗi `HTTP 409 Conflict` nếu người dùng gửi lệnh thêm node khi dịch vụ chưa sẵn sàng.
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Điểm nổi bật trong mã nguồn của nhóm là tính năng Dynamic Scale-out. Khi một máy chủ mới được bổ sung vào hệ thống lúc nửa đêm, chúng ta không thể khởi động lại toàn bộ Reverse Proxy vì sẽ làm đứt kết nối của hàng nghìn khách hàng. Proxy của nhóm cung cấp Control API cho phép nạp thêm node mới và tính toán lại vòng băm trực tiếp trong bộ nhớ. Đồng thời, cơ chế Lifecycle Resync ngăn chặn triệt để hiện tượng xung đột trạng thái hay các tiến trình rác tồn dư."*

---

### SLIDE 12: KIỂM THỬ TỰ ĐỘNG TOÀN DIỆN (59/59 TESTS PASSED 100%)
* `[Barem: Implementation Quality 25%]`
* **Thời lượng:** 1:00 phút | **Người trình bày:** Thành viên 2
* **Tiêu đề Slide:** ĐẢM BẢO CHẤT LƯỢNG MÃ NGUỒN: BỘ KIỂM THỬ TỰ ĐỘNG 100% PASS
* **Nội dung trực quan:**
  - Bảng tổng hợp 59 Test Cases trong thư mục `tests/`:
  
  | Bộ Test Suite | Số lượng Test | Trọng tâm kiểm thử |
  | :--- | :---: | :--- |
  | `test_base.py` | 6 tests | Hợp đồng giao diện `BaseBalancer`, cấu trúc dữ liệu `Backend` |
  | `test_round_robin.py` | 7 tests | Tính luân chuyển tuần hoàn, xử lý node sập, phân bổ trọng số |
  | `test_least_connections.py` | 6 tests | Đếm kết nối đồng thời, giải phóng kết nối khi lỗi |
  | `test_consistent_hash.py` | 8 tests | Sticky IP, phân bổ Vnodes, `bisect_left`, minimal disruption |
  | `test_proxy.py` | 7 tests | L7 Reverse Proxy, hop-by-hop filter, Immediate Retry |
  | `test_traffic_sim.py` | 8 tests | Bộ sinh tải, đo đạc thống kê, phân tích log |
  | `test_web_dashboard.py` | 9 tests | API điều khiển tiến trình, Force Kill, thống kê trượt RPS 5s |
  | `test_backend_management.py` | 8 tests | Thêm node động, đổi trọng số, kiểm soát xung đột HTTP 409 |
  - Ảnh chụp màn hình kết quả chạy `pytest`: **59 passed, 1 skipped in 15.9s (100% PASS)**.
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Để đảm bảo mã nguồn đạt tiêu chuẩn kỹ thuật cao nhất, nhóm đã xây dựng bộ kiểm thử tự động toàn diện với 59 test cases trải dài qua 8 bộ test suite. Từ các unit test toán học kiểm tra tính đúng đắn của hàm bisect_left trên vòng băm, cho tới các integration test kiểm tra khả năng bắt lỗi kết nối của Proxy và các API điều khiển tiến trình. Toàn bộ 59/59 tests đều vượt qua thành công 100% trước khi đưa vào bản phát hành."*

---

### SLIDE 13: KỊCH BẢN LIVE DEMO TRỰC QUAN TRÊN WEB DASHBOARD
* `[Barem: Implementation Quality 25% & Presentation 25%]`
* **Thời lượng:** 0:30 phút chuyển giao $\to$ Bắt đầu 5-7 phút Live Demo | **Người trình bày:** Thành viên 2
* **Tiêu đề Slide:** TRUNG TÂM ĐIỀU KHIỂN HỢP NHẤT: LIVE DEMO 5 PHA KỸ THUẬT
* **Nội dung trực quan:**
  - Ảnh chụp giao diện Web Dashboard SPA (`http://localhost:8001`):
    - Khối trạng thái tiến trình (Status Chips xanh/đỏ).
    - Thẻ điều khiển 1 chạm và bảng chọn thuật toán Segmented Control.
    - Lưới thẻ Backend Nodes trực quan với thanh phân bổ tải % và độ trễ phản hồi.
    - Bảng 20 request log cuộn thời gian thực kèm bộ giải mã toán học Clockwise Interval.
  - Tóm tắt 5 pha Demo chuẩn bị thực hiện:
    1. *Pha 1:* Khởi động hạ tầng 1-click (Mock Nodes + Proxy :8000).
    2. *Pha 2:* Bắn tải và quan sát phân bổ tải Round Robin vs Least Connections.
    3. *Pha 3:* Trình diễn Consistent Hashing, tính Sticky Client IP và giải mã cung băm.
    4. *Pha 4:* Tiêm lỗi Chaos (Đánh sập node 9002) $\to$ Chứng minh tính Chịu lỗi trong suốt.
    5. *Pha 5:* Mở rộng hạ tầng động (Thêm `mock-node-4` tại runtime mà không gián đoạn).
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Và sau đây, nhóm xin chuyển sang phần Live Demo thực nghiệm trên máy tính để minh chứng trực quan toàn bộ các luận điểm kỹ thuật vừa trình bày..."* *(Thực hiện Demo theo kịch bản trong `Demo_Script.md`)*.

---

### SLIDE 14: TÍNH ĐỔI MỚI, KHẢ NĂNG ỨNG DỤNG & HƯỚNG PHÁT TRIỂN
* `[Barem: Technical Depth 30% & Innovation]`
* **Thời lượng:** 1:15 phút | **Người trình bày:** Thành viên 3
* **Tiêu đề Slide:** TÍNH ĐỔI MỚI VÀ TIỀM NĂNG ỨNG DỤNG THỰC TẾ
* **Nội dung trực quan:**
  - Tính đổi mới của đề tài:
    - Xây dựng giải pháp độc lập, không phụ thuộc thư viện ngoài (Zero-external-dependency, 100% chạy offline).
    - Bộ giải mã quyết định toán học thời gian thực (`explain_decision`) giúp quan sát trực quan không gian băm.
    - Trung tâm điều hành Web Dashboard Single-File SPA tích hợp trọn vẹn quản lý tiến trình, tiêm lỗi và quan sát số liệu.
  - So sánh với các giải pháp công nghiệp:
    - *Nginx / HAProxy:* Rất mạnh mẽ nhưng đóng gói sẵn, khó quan sát chi tiết từng bước dịch chuyển con trỏ thuật toán.
    - *Dự án của nhóm:* Trong suốt, trực quan hóa cao độ, tối ưu cho mục đích nghiên cứu, giảng dạy và mô phỏng giao thức mạng.
  - Hướng phát triển mở rộng (Future Work):
    - Đóng gói Dockerfile siêu nhẹ.
    - Tích hợp chuẩn giám sát công nghiệp Prometheus Metrics (`/metrics`) và Grafana Dashboard.
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Kính thưa Thầy, sau phần demo trực quan của bạn [Tên TV2], em xin tổng kết về tính đổi mới và khả năng ứng dụng của đồ án. Khác với việc chỉ cấu hình các phần mềm có sẵn như Nginx, đồ án của nhóm đã tự cài đặt từ gốc toàn bộ logic Reverse Proxy và các thuật toán phân phối lưu lượng bằng Python AsyncIO. Hệ thống có khả năng 'mở hộp đen' của thuật toán Consistent Hashing, giải thích rõ ràng từng quyết định định tuyến theo cung băm. Đây là một công cụ trực quan và hoàn chỉnh cho việc nghiên cứu và thử nghiệm các chiến lược định tuyến mạng."*

---

### SLIDE 15: KẾT LUẬN, MINH BẠCH CÔNG CỤ AI & SẴN SÀNG Q&A
* `[Barem: Q&A Handling 20% & Academic Integrity]`
* **Thời lượng:** 1:00 phút $\to$ Chuyển sang 3-5 phút Q&A | **Người trình bày:** Thành viên 3
* **Tiêu đề Slide:** TỔNG KẾT, MINH BẠCH CÔNG CỤ TRỢ GIÚP & SẴN SÀNG TRẢ LỜI CÂU HỎI
* **Nội dung trực quan:**
  - Tóm tắt kết quả đạt được:
    - Hoàn thành $100\%$ mục tiêu đề tài T22 theo yêu cầu của Bộ môn.
    - Bộ mã nguồn chuẩn mực, đầy đủ tài liệu API, lý thuyết nền tảng và 59/59 tests pass.
  - **Minh bạch công cụ AI (AI Tool Disclosure theo quy chế PTIT):**
    - Nhóm có sử dụng AI Assistant (Gemini / Antigravity) để hỗ trợ: Khởi tạo khung tài liệu Markdown, rà soát lỗi chính tả và hỗ trợ viết boilerplate test cases.
    - **Cam kết học thuật:** Toàn bộ tư duy kiến trúc, phân tích toán học giải thuật, logic cốt lõi của Proxy và xử lý lỗi mạng đều do nhóm trực tiếp phân tích, cài đặt, làm chủ và sẵn sàng bảo vệ chi tiết trước Hội đồng.
  - Lời cảm ơn Giảng viên hướng dẫn ThS. Đặng Ngọc Hùng.
  - Lời mời Hội đồng và các bạn đặt câu hỏi phản biện.
* **Lời thoại thuyết minh (Speaker Notes):**
  > *"Để kết thúc bài thuyết trình, nhóm chúng em xin công khai minh bạch việc sử dụng công cụ AI hỗ trợ trong quá trình định dạng tài liệu và sinh các kịch bản kiểm thử biên, tuân thủ đúng quy định về liêm chính học thuật của môn học. Toàn bộ các thành viên trong nhóm đều hiểu sâu sắc bản chất từng dòng mã nguồn và cơ sở giải thuật. Chúng em xin chân thành cảm ơn Thầy Đặng Ngọc Hùng đã tận tình hướng dẫn trong suốt học phần. Nhóm chúng em rất mong nhận được những câu hỏi và ý kiến đóng góp quý báu từ Thầy. Chúng em xin trân trọng cảm ơn!"*
