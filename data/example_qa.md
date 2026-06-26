_Two trimmed QA records from `data/luong_graph_report.html`. Sections: user query · final response · knowledge sources · final generation query._

# EXAMPLE 1 — CORRECT & GROUNDED

- **qa_id:** `qa-khoiva-0005`
- **type / difficulty / answerability:** multi_hop / hard / answerable
- **answer_score:** 10 | **doc_hit:** True | **chunk_hit:** True
- **grader reason:** Câu trả lời dự đoán hoàn toàn chính xác, khớp với golden answer: nhân viên tự ý làm thêm giờ tại nhà dù đã được phê duyệt WFH không được tính lương ngoài giờ, vì chế độ OT chỉ áp dụng khi có yêu cầu từ Công ty (LM/DH), không áp dụng cho trường hợp nhân viên tự ý hoàn thành công việc.

## 1. User query

> Nếu nhân viên 2MoreBits làm việc tại nhà đã được DH phê duyệt nhưng tự ở lại làm thêm để hoàn tất việc, họ có được tính lương ngoài giờ không?

## 2. Final response

Không, nhân viên không được tính lương ngoài giờ trong trường hợp này.

Theo bằng chứng [1], làm thêm giờ chỉ được áp dụng khi có yêu cầu từ Công ty (qua Cấp quản lý LM/DH) và **không áp dụng khi Nhân viên tự ý làm thêm giờ** để hoàn thành công việc, ngay cả khi việc làm việc tại nhà đã được phê duyệt trước đó.

## 3. Knowledge sources

_2 source chunk(s) returned._

### [1] chunk `103d4d0d9bee67e3…`  (doc `doc_7104376dd4a1…`, score 1.458377)

```
### 2.3.1. Quy định chung

- Tùy thuộc yêu cầu công việc và sự sắp xếp của Phòng ban, Nhân viên nếu phải làm việc ngoài giờ theo thời gian làm việc được quy định ở mục 2.1 được áp dụng chế độ lương ngoài giờ.
- Làm thêm giờ chỉ áp dụng khi có yêu cầu từ phía Công ty có qua đại diện là các Cấp quản lý LM/DH trong trường hợp có nhu cầu công việc phát sinh ngoài kế hoạch khẩn cấp, để phục vụ sản xuất, kinh doanh, không áp dụng khi Nhân viên tự ý làm thêm giờ để hoàn thành công việc.
- Nhân viên không được từ chối làm thêm giờ trong các trường hợp đặc biệt do pháp luật quy định.
```

### [2] chunk `921fe465988c5261…`  (doc `doc_a3c430fce842…`, score 1.888769)

```
#### 2.3.3. Lương làm việc ngoài giờ

- Lương làm việc ngoài giờ được tính toán và chi trả trong cùng kỳ lương nếu LM/DH phê duyệt đúng thời gian trước ngày chốt công hàng tháng. Các OT đã đăng ký nhưng không được phê duyệt trước ngày chốt công sẽ bị tính không có hiệu lực khi sang kỳ lương tháng kế tiếp.
- Tiền lương làm thêm giờ được tính toán, chi trả và khấu trừ thuế TNCN theo quy định của Pháp luật hiện hành:

| Phân loại | Nguyên tắc tính lương | Tổng tỷ lệ |
| :-- | :-- | :-- |
| Làm việc ngoài giờ vào Ngày thường | 150% x Đơn giá tiền lương | 150% |
| Làm việc ngoài giờ vào Ngày nghỉ tuần/Ngày Nhân viên không có lịch làm việc | 200% x Đơn giá tiền lương | 200% |
| Làm việc ngoài giờ vào Ngày Lễ/Tết | 300% x Đơn giá tiền lương | 300% |
| Phụ cấp làm việc vào Ban đêm | 30% x Đơn giá tiền lương | 30% |
| Làm việc ngoài giờ vào Ban đêm Ngày thường | (150% + 30% + 20% x 150%) x Đơn giá tiền lương | 210% |
| Làm việc ngoài giờ vào Ban đêm Ngày nghỉ tuần/Ngày Nhân viên không có lịch làm việc | (200% + 30% + 20% x 200%) x Đơn giá tiền lương | 270% |
| Làm việc ngoài giờ vào Ban đêm Ngày Lễ/Tết | (300% + 30% + 20% x 300%) x Đơn giá tiền lương | 390% |

- Công ty có thể hỗ trợ thêm Phụ cấp khi tăng ca tuỳ theo kết quả của công việc.
```

## 4. Final generation query

_LLM step 12 · model `local-model-mini`_

**[system]**

```
Bạn là trợ lý tổng hợp câu trả lời cuối cùng. Dựa trên các bằng chứng đã thu thập, hãy trả lời ĐÚNG TRỌNG TÂM câu hỏi bằng tiếng Việt, ngắn gọn và chính xác. KHÔNG trả lời thêm thông tin ngoài phạm vi câu hỏi. KHÔNG mở rộng sang chủ đề liên quan mà người dùng không hỏi. Nếu bằng chứng không đủ, không tự trả lời mà hãy nêu rõ phần còn thiếu.
```

**[human]**

```
Câu hỏi: Nếu nhân viên 2MoreBits làm việc tại nhà đã được DH phê duyệt nhưng tự ở lại làm thêm để hoàn tất việc, họ có được tính lương ngoài giờ không?

Bằng chứng:
[1] ### 2.3.1. Quy định chung

- Tùy thuộc yêu cầu công việc và sự sắp xếp của Phòng ban, Nhân viên nếu phải làm việc ngoài giờ theo thời gian làm việc được quy định ở mục 2.1 được áp dụng chế độ lương ngoài giờ.
- Làm thêm giờ chỉ áp dụng khi có yêu cầu từ phía Công ty có qua đại diện là các Cấp quản lý LM/DH trong trường hợp có nhu cầu công việc phát sinh ngoài kế hoạch khẩn cấp, để phục vụ sản xuất, kinh doanh, không áp dụng khi Nhân viên tự ý làm thêm giờ để hoàn thành công việc.
- Nhân viên không được từ chối làm thêm giờ trong các trường hợp đặc biệt do pháp luật quy định.

[2] #### 2.3.3. Lương làm việc ngoài giờ

- Lương làm việc ngoài giờ được tính toán và chi trả trong cùng kỳ lương nếu LM/DH phê duyệt đúng thời gian trước ngày chốt công hàng tháng. Các OT đã đăng ký nhưng không được phê duyệt trước ngày chốt công sẽ bị tính không có hiệu lực khi sang kỳ lương tháng kế tiếp.
- Tiền lương làm thêm giờ được tính toán, chi trả và khấu trừ thuế TNCN theo quy định của Pháp luật hiện hành:

| Phân loại | Nguyên tắc tính lương | Tổng tỷ lệ |
| :-- | :-- | :-- |
| Làm việc ngoài giờ vào Ngày thường | 150% x Đơn giá tiền lương | 150% |
| Làm việc ngoài giờ vào Ngày nghỉ tuần/Ngày Nhân viên không có lịch làm việc | 200% x Đơn giá tiền lương | 200% |
| Làm việc ngoài giờ vào Ngày Lễ/Tết | 300% x Đơn giá tiền lương | 300% |
| Phụ cấp làm việc vào Ban đêm | 30% x Đơn giá tiền lương | 30% |
| Làm việc ngoài giờ vào Ban đêm Ngày thường | (150% + 30% + 20% x 150%) x Đơn giá tiền lương | 210% |
| Làm việc ngoài giờ vào Ban đêm Ngày nghỉ tuần/Ngày Nhân viên không có lịch làm việc | (200% + 30% + 20% x 200%) x Đơn giá tiền lương | 270% |
| Làm việc ngoài giờ vào Ban đêm Ngày Lễ/Tết | (300% + 30% + 20% x 300%) x Đơn giá tiền lương | 390% |

- Công ty có thể hỗ trợ thêm Phụ cấp khi tăng ca tuỳ theo kết quả của công việc.

Trả lời câu hỏi dựa trên bằng chứng trên. Nếu thiếu thông tin, nêu rõ phần nào chưa có.
```


---

# EXAMPLE 2 — INCORRECT & GROUNDED (right chunks retrieved, answer still wrong)

- **qa_id:** `qa-khoiva-0006`
- **type / difficulty / answerability:** multi_hop / medium / answerable
- **answer_score:** 0 | **doc_hit:** True | **chunk_hit:** True
- **grader reason:** Câu trả lời dự đoán sai khi cho rằng không có thông tin về 2MoreBits và không thể so sánh, trong khi thông tin về cả 2MoreBits và Zingplay đều có sẵn trong bằng chứng (mức hỗ trợ 500.000 đồng/tháng và điều kiện tháng gia nhập/nghỉ việc khác nhau).

## 1. User query

> So sánh chính sách hỗ trợ điện thoại của 2MoreBits và Zingplay cho bậc 4: mức hỗ trợ có khác nhau không, và khác biệt chính về tháng gia nhập/nghỉ việc là gì?

## 2. Final response

Dựa trên các bằng chứng đã cung cấp, không thể trả lời câu hỏi vì:

1.  **Không có thông tin về công ty "2MoreBits":** Các bằng chứng chỉ đề cập đến chính sách của một công ty (có thể là Zingplay hoặc một đơn vị khác) với các quy định về cấp bậc (Bậc 4, Bậc 5...) và điều kiện hưởng hỗ trợ, nhưng không có bất kỳ dữ liệu nào liên quan đến "2MoreBits".
2.  **Không có thông tin so sánh:** Do thiếu dữ liệu của 2MoreBits, không thể so sánh mức hỗ trợ hay điều kiện tháng gia nhập/nghỉ việc giữa hai đơn vị này.

**Kết luận:** Bằng chứng chỉ cung cấp thông tin về một bên (có thể là Zingplay hoặc một công ty khác), thiếu hoàn toàn thông tin về chính sách của **2MoreBits** để thực hiện so sánh.

## 3. Knowledge sources

_4 source chunk(s) returned._

### [1] chunk `db222b327367c2bf…`  (doc `doc_1416efd9f80b…`, score 1.717704)

```
### 2.3. Đối tượng và định mức hàng tháng

Định mức hưởng hỗ trợ điện thoại sẽ tùy thuộc vào cấp bậc, được quy định cụ thể như sau:

**Đơn vị tính:** VND/tháng

| Nhóm Cấp bậc | Hạn mức chi phí/tháng (bao gồm thuế) | Thời điểm hưởng |
| :-- | :-- | :-- |
| 5.3 |  |  |
| 5.2 | 2,000,000 |  |
| 5.1 |  |  |
| 4.3 |  |  |
| 4.2 | 500,000 |  |
| 4.1 |  | Tháng gia nhập công ty |
| 3.3 |  |  |
| 3.2 | 300,000 |  |
| 3.1 |  |  |
| 2.3 | 300,000 |  |
| 2.2 | 200,000 |  |

- Thành viên mới gia nhập công ty từ ngày 01 – 15 của tháng: nhận hỗ trợ từ tháng gia nhập.
- Thành viên mới gia nhập công ty từ ngày 16 – 31 của tháng: nhận hỗ trợ bắt đầu từ tháng kế tiếp.
- Thành viên nghỉ việc có ngày làm cuối tới ngày 01 – 14 của tháng: ngưng nhận hỗ trợ từ tháng nghỉ việc.
- Thành viên nghỉ việc có ngày làm cuối từ ngày 15 – 31 của tháng: ngưng nhận hỗ trợ từ tháng kế tiếp.

*Hình dấu đỏ tròn, chữ bên trong không rõ ràng, tương tự hình dấu trên trang 1.*
```

### [2] chunk `03d9ccd12dc143d9…`  (doc `doc_0e92ddd323a6…`, score 1.837784)

```
### 3.1. Hỗ trợ điện thoại

- Hỗ trợ điện thoại được áp dụng cho Nhân viên với định mức theo cấp bậc như sau:

| Cấp bậc | Định mức đồng/tháng |
| :-- | :-- |
| Bậc 5 | 2,000,000 |
| Bậc 4 | 500,000 |
| Bậc 2.3 – 3.3 | 300,000 |
| Bậc 2.2 | 200,000 |

- Các trường hợp đặc biệt cần có sự phê duyệt của ĐH.
- Hỗ trợ điện thoại của tháng gia nhập Công ty và tháng nghỉ việc không được tính hưởng nếu:
  - Nhân viên nhận việc sau ngày 20 của tháng;
  - Nhân viên nghỉ việc trước ngày 10 của tháng.
- Trường hợp Nhân viên thay đổi cấp bậc nếu có thay đổi định mức, Hỗ trợ điện thoại theo cấp bậc mới được áp dụng theo nguyên tắc:
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 01 đến ngày 20: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng hiệu lực thay đổi cấp bậc;
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 21 đến cuối tháng: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng kế tiếp tháng hiệu lực thay đổi cấp bậc.
- Hỗ trợ điện thoại được chuyển trực tiếp qua ví điện tử Zalopay hoặc Công ty hỗ trợ thanh toán theo hình thức thuê bao được quy định trong Chính sách hỗ trợ điện thoại do Phòng AF ban hành.
- Thông tin hỗ trợ cụ thể được quy định trong Chính sách hỗ trợ điện thoại do phòng AF ban hành.
```

### [3] chunk `532eab65249e8891…`  (doc `doc_ddfc2812450d…`, score 1.806614)

```
## 3.1. Hỗ trợ điện thoại

Hỗ trợ điện thoại được áp dụng cho Nhân viên với định mức theo cấp bậc như sau:

| Cấp bậc       | Định mức đồng/tháng |
| :------------ | :------------------ |
| Bậc 5         | 2,000,000           |
| Bậc 4         | 500,000             |
| Bậc 2.3 – 3.3 | 300,000             |
| Bậc 2.2       | 200,000             |
|               |                     |

- Các trường hợp đặc biệt cần có sự phê duyệt của ĐH.
- Hỗ trợ điện thoại của tháng gia nhập Công ty và tháng nghỉ việc không được tính hưởng nếu:
  - Nhân viên nhận việc sau ngày 20 của tháng;
  - Nhân viên nghỉ việc trước ngày 10 của tháng.
- Trường hợp Nhân viên thay đổi cấp bậc nếu có thay đổi định mức, Hỗ trợ điện thoại theo cấp bậc mới được áp dụng theo nguyên tắc:
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 01, đến ngày 20: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng hiệu lực thay đổi cấp bậc;
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 21 đến cuối tháng: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng kế tiếp tháng hiệu lực thay đổi cấp bậc.
- Hỗ trợ điện thoại được chuyển trực tiếp qua ví điện tử Zalopay hoặc Công ty hỗ trợ thanh toán theo hình thức thuê bao được quy định trong Chính sách hỗ trợ điện thoại do Phòng AF ban hành.
- Thông tin hỗ trợ cụ thể được quy định trong Chính sách hỗ trợ điện thoại do phòng AF ban hành.
```

### [4] chunk `e85a55ef011be887…`  (doc `doc_2e5f577e2e72…`, score 1.803276)

```
## 3.1. Hỗ trợ điện thoại

Hỗ trợ điện thoại được áp dụng cho Nhân viên với định mức theo cấp bậc như sau:

| Cấp bậc       | Định mức đồng/tháng |
| :------------ | :------------------ |
| Bậc 5         | 2,000,000           |
| Bậc 4         | 500,000             |
| Bậc 2.3 – 3.3 | 300,000             |
| Bậc 2.2       | 200,000             |

- Các trường hợp đặc biệt cần có sự phê duyệt của DH.
- Hỗ trợ điện thoại của tháng gia nhập Công ty và tháng nghỉ việc không được tính hưởng nếu:
  - Nhân viên nghỉ việc trước ngày 20 của tháng.
  - Nhân viên làm việc trước ngày 10 của tháng.
- Trường hợp Nhân viên thay đổi cấp bậc nếu có thay đổi định mức, Hỗ trợ điện thoại theo cấp bậc mới được áp dụng theo nguyên tắc:
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 01 đến ngày 20: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng hiệu lực thay đổi cấp bậc.
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 21 đến cuối tháng: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng kế tiếp tháng hiệu lực thay đổi cấp bậc.
- Hỗ trợ điện thoại được chuyển trực tiếp qua ví điện tử Zalopay hoặc Công ty hỗ trợ thanh toán theo hình thức thuê bao được quy định trong Chính sách hỗ trợ điện thoại do Phòng AF ban hành.
- Thông tin hỗ trợ cụ thể được quy định trong Chính sách hỗ trợ điện thoại do phòng AF ban hành.
```

## 4. Final generation query

_LLM step 7 · model `local-model-mini`_

**[system]**

```
Bạn là trợ lý tổng hợp câu trả lời cuối cùng. Dựa trên các bằng chứng đã thu thập, hãy trả lời ĐÚNG TRỌNG TÂM câu hỏi bằng tiếng Việt, ngắn gọn và chính xác. KHÔNG trả lời thêm thông tin ngoài phạm vi câu hỏi. KHÔNG mở rộng sang chủ đề liên quan mà người dùng không hỏi. Nếu bằng chứng không đủ, không tự trả lời mà hãy nêu rõ phần còn thiếu.
```

**[human]**

```
Câu hỏi: So sánh chính sách hỗ trợ điện thoại của 2MoreBits và Zingplay cho bậc 4: mức hỗ trợ có khác nhau không, và khác biệt chính về tháng gia nhập/nghỉ việc là gì?

Bằng chứng:
[1] ### 2.3. Đối tượng và định mức hàng tháng

Định mức hưởng hỗ trợ điện thoại sẽ tùy thuộc vào cấp bậc, được quy định cụ thể như sau:

**Đơn vị tính:** VND/tháng

| Nhóm Cấp bậc | Hạn mức chi phí/tháng (bao gồm thuế) | Thời điểm hưởng |
| :-- | :-- | :-- |
| 5.3 |  |  |
| 5.2 | 2,000,000 |  |
| 5.1 |  |  |
| 4.3 |  |  |
| 4.2 | 500,000 |  |
| 4.1 |  | Tháng gia nhập công ty |
| 3.3 |  |  |
| 3.2 | 300,000 |  |
| 3.1 |  |  |
| 2.3 | 300,000 |  |
| 2.2 | 200,000 |  |

- Thành viên mới gia nhập công ty từ ngày 01 – 15 của tháng: nhận hỗ trợ từ tháng gia nhập.
- Thành viên mới gia nhập công ty từ ngày 16 – 31 của tháng: nhận hỗ trợ bắt đầu từ tháng kế tiếp.
- Thành viên nghỉ việc có ngày làm cuối tới ngày 01 – 14 của tháng: ngưng nhận hỗ trợ từ tháng nghỉ việc.
- Thành viên nghỉ việc có ngày làm cuối từ ngày 15 – 31 của tháng: ngưng nhận hỗ trợ từ tháng kế tiếp.

*Hình dấu đỏ tròn, chữ bên trong không rõ ràng, tương tự hình dấu trên trang 1.*

[2] ### 3.1. Hỗ trợ điện thoại

- Hỗ trợ điện thoại được áp dụng cho Nhân viên với định mức theo cấp bậc như sau:

| Cấp bậc | Định mức đồng/tháng |
| :-- | :-- |
| Bậc 5 | 2,000,000 |
| Bậc 4 | 500,000 |
| Bậc 2.3 – 3.3 | 300,000 |
| Bậc 2.2 | 200,000 |

- Các trường hợp đặc biệt cần có sự phê duyệt của ĐH.
- Hỗ trợ điện thoại của tháng gia nhập Công ty và tháng nghỉ việc không được tính hưởng nếu:
  - Nhân viên nhận việc sau ngày 20 của tháng;
  - Nhân viên nghỉ việc trước ngày 10 của tháng.
- Trường hợp Nhân viên thay đổi cấp bậc nếu có thay đổi định mức, Hỗ trợ điện thoại theo cấp bậc mới được áp dụng theo nguyên tắc:
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 01 đến ngày 20: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng hiệu lực thay đổi cấp bậc;
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 21 đến cuối tháng: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng kế tiếp tháng hiệu lực thay đổi cấp bậc.
- Hỗ trợ điện thoại được chuyển trực tiếp qua ví điện tử Zalopay hoặc Công ty hỗ trợ thanh toán theo hình thức thuê bao được quy định trong Chính sách hỗ trợ điện thoại do Phòng AF ban hành.
- Thông tin hỗ trợ cụ thể được quy định trong Chính sách hỗ trợ điện thoại do phòng AF ban hành.

[3] ## 3.1. Hỗ trợ điện thoại

Hỗ trợ điện thoại được áp dụng cho Nhân viên với định mức theo cấp bậc như sau:

| Cấp bậc       | Định mức đồng/tháng |
| :------------ | :------------------ |
| Bậc 5         | 2,000,000           |
| Bậc 4         | 500,000             |
| Bậc 2.3 – 3.3 | 300,000             |
| Bậc 2.2       | 200,000             |
|               |                     |

- Các trường hợp đặc biệt cần có sự phê duyệt của ĐH.
- Hỗ trợ điện thoại của tháng gia nhập Công ty và tháng nghỉ việc không được tính hưởng nếu:
  - Nhân viên nhận việc sau ngày 20 của tháng;
  - Nhân viên nghỉ việc trước ngày 10 của tháng.
- Trường hợp Nhân viên thay đổi cấp bậc nếu có thay đổi định mức, Hỗ trợ điện thoại theo cấp bậc mới được áp dụng theo nguyên tắc:
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 01, đến ngày 20: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng hiệu lực thay đổi cấp bậc;
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 21 đến cuối tháng: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng kế tiếp tháng hiệu lực thay đổi cấp bậc.
- Hỗ trợ điện thoại được chuyển trực tiếp qua ví điện tử Zalopay hoặc Công ty hỗ trợ thanh toán theo hình thức thuê bao được quy định trong Chính sách hỗ trợ điện thoại do Phòng AF ban hành.
- Thông tin hỗ trợ cụ thể được quy định trong Chính sách hỗ trợ điện thoại do phòng AF ban hành.

[4] ## 3.1. Hỗ trợ điện thoại

Hỗ trợ điện thoại được áp dụng cho Nhân viên với định mức theo cấp bậc như sau:

| Cấp bậc       | Định mức đồng/tháng |
| :------------ | :------------------ |
| Bậc 5         | 2,000,000           |
| Bậc 4         | 500,000             |
| Bậc 2.3 – 3.3 | 300,000             |
| Bậc 2.2       | 200,000             |

- Các trường hợp đặc biệt cần có sự phê duyệt của DH.
- Hỗ trợ điện thoại của tháng gia nhập Công ty và tháng nghỉ việc không được tính hưởng nếu:
  - Nhân viên nghỉ việc trước ngày 20 của tháng.
  - Nhân viên làm việc trước ngày 10 của tháng.
- Trường hợp Nhân viên thay đổi cấp bậc nếu có thay đổi định mức, Hỗ trợ điện thoại theo cấp bậc mới được áp dụng theo nguyên tắc:
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 01 đến ngày 20: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng hiệu lực thay đổi cấp bậc.
  - Ngày hiệu lực thay đổi cấp bậc từ ngày 21 đến cuối tháng: định mức Hỗ trợ điện thoại theo cấp bậc mới được áp dụng từ tháng kế tiếp tháng hiệu lực thay đổi cấp bậc.
- Hỗ trợ điện thoại được chuyển trực tiếp qua ví điện tử Zalopay hoặc Công ty hỗ trợ thanh toán theo hình thức thuê bao được quy định trong Chính sách hỗ trợ điện thoại do Phòng AF ban hành.
- Thông tin hỗ trợ cụ thể được quy định trong Chính sách hỗ trợ điện thoại do phòng AF ban hành.

Trả lời câu hỏi dựa trên bằng chứng trên. Nếu thiếu thông tin, nêu rõ phần nào chưa có.
```

---

# Appendix — EXACTLY what is fed to the final generation (INPUT ONLY)

This is the **complete input** to the final-generation LLM call — and **nothing else**. It is the `prompt` array only: one `system` message + one `human` message. The model's answer (`response`) is **excluded** — it is output, not input. No agent prompt, tool history, or scratchpad is present. This is the literal payload, verbatim.

## EXAMPLE 1 — correct & grounded — `qa-khoiva-0005` (llm_trace step 12)

```json
{
  "model": "local-model-mini",
  "messages": [
    {
      "role": "system",
      "content": "Bạn là trợ lý tổng hợp câu trả lời cuối cùng. Dựa trên các bằng chứng đã thu thập, hãy trả lời ĐÚNG TRỌNG TÂM câu hỏi bằng tiếng Việt, ngắn gọn và chính xác. KHÔNG trả lời thêm thông tin ngoài phạm vi câu hỏi. KHÔNG mở rộng sang chủ đề liên quan mà người dùng không hỏi. Nếu bằng chứng không đủ, không tự trả lời mà hãy nêu rõ phần còn thiếu."
    },
    {
      "role": "human",
      "content": "Câu hỏi: Nếu nhân viên 2MoreBits làm việc tại nhà đã được DH phê duyệt nhưng tự ở lại làm thêm để hoàn tất việc, họ có được tính lương ngoài giờ không?\n\nBằng chứng:\n[1] ### 2.3.1. Quy định chung\n\n- Tùy thuộc yêu cầu công việc và sự sắp xếp của Phòng ban, Nhân viên nếu phải làm việc ngoài giờ theo thời gian làm việc được quy định ở mục 2.1 được áp dụng chế độ lương ngoài giờ.\n- Làm thêm giờ chỉ áp dụng khi có yêu cầu từ phía Công ty có qua đại diện là các Cấp quản lý LM/DH trong trường hợp có nhu cầu công việc phát sinh ngoài kế hoạch khẩn cấp, để phục vụ sản xuất, kinh doanh, không áp dụng khi Nhân viên tự ý làm thêm giờ để hoàn thành công việc.\n- Nhân viên không được từ chối làm thêm giờ trong các trường hợp đặc biệt do pháp luật quy định.\n\n[2] #### 2.3.3. Lương làm việc ngoài giờ\n\n- Lương làm việc ngoài giờ được tính toán và chi trả trong cùng kỳ lương nếu LM/DH phê duyệt đúng thời gian trước ngày chốt công hàng tháng. Các OT đã đăng ký nhưng không được phê duyệt trước ngày chốt công sẽ bị tính không có hiệu lực khi sang kỳ lương tháng kế tiếp.\n- Tiền lương làm thêm giờ được tính toán, chi trả và khấu trừ thuế TNCN theo quy định của Pháp luật hiện hành:\n\n| Phân loại | Nguyên tắc tính lương | Tổng tỷ lệ |\n| :-- | :-- | :-- |\n| Làm việc ngoài giờ vào Ngày thường | 150% x Đơn giá tiền lương | 150% |\n| Làm việc ngoài giờ vào Ngày nghỉ tuần/Ngày Nhân viên không có lịch làm việc | 200% x Đơn giá tiền lương | 200% |\n| Làm việc ngoài giờ vào Ngày Lễ/Tết | 300% x Đơn giá tiền lương | 300% |\n| Phụ cấp làm việc vào Ban đêm | 30% x Đơn giá tiền lương | 30% |\n| Làm việc ngoài giờ vào Ban đêm Ngày thường | (150% + 30% + 20% x 150%) x Đơn giá tiền lương | 210% |\n| Làm việc ngoài giờ vào Ban đêm Ngày nghỉ tuần/Ngày Nhân viên không có lịch làm việc | (200% + 30% + 20% x 200%) x Đơn giá tiền lương | 270% |\n| Làm việc ngoài giờ vào Ban đêm Ngày Lễ/Tết | (300% + 30% + 20% x 300%) x Đơn giá tiền lương | 390% |\n\n- Công ty có thể hỗ trợ thêm Phụ cấp khi tăng ca tuỳ theo kết quả của công việc.\n\nTrả lời câu hỏi dựa trên bằng chứng trên. Nếu thiếu thông tin, nêu rõ phần nào chưa có."
    }
  ]
}
```

## EXAMPLE 2 — incorrect & grounded — `qa-khoiva-0006` (llm_trace step 7)

```json

```
