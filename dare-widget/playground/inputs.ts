/**
 * Playground inputs — the REAL qa-0164 record, VIETNAMESE original.
 *
 * This is what the model actually generated (and the chunks it actually saw), so
 * POSTing these to /attribute computes attribution on the real text — not the
 * English gloss in sample.ts. Auto-generated from data/raw_responses.jsonl; do
 * not hand-edit the Vietnamese.
 */
import type { DareChunk } from "../src/types";

export const QUERY = "Nhân viên VNG có thâm niên 2 năm được chẩn đoán mắc bệnh Parkinson. Họ có đủ điều kiện tạm ứng lương không, và nếu đủ điều kiện thì mức tạm ứng tối đa là bao nhiêu tháng lương?";

export const ANSWER = "Dựa trên bằng chứng đã cung cấp:\n\n1.  **Điều kiện đủ:** Nhân viên có thâm niên 2 năm (đủ điều kiện từ 1 năm trở lên theo Điều 17) và mắc bệnh Parkinson (thuộc nhóm bệnh hiểm nghèo theo Điều 2.1).\n2.  **Mức tạm ứng tối đa:** **03 tháng lương gộp**.\n\n*Lưu ý: Để hoàn tất thủ tục, nhân viên cần đảm bảo thêm các điều kiện khác như hợp đồng lao động còn hiệu lực ít nhất 3 tháng, không đang trong giai đoạn hoàn ứng khoản vay khác, không vướng xử lý kỷ luật 6 tháng gần nhất và không trong giai đoạn xử lý thôi việc (theo Điều 2.1).*";

export const CHUNKS: DareChunk[] = [
  {
    "content": "### Điều 17. Tạm ứng lương\n\nCông Ty áp dụng Chính Sách Tạm Ứng Lương cho Nhân viên đã qua thời gian thử việc để hỗ trợ tài chính cho các trường hợp bản thân hoặc người thân mắc bệnh hiểm nghèo.\n\n1. NLĐ có thâm niên làm việc từ 1 năm trở lên, được tạm ứng tối đa 03 tháng lương gộp và thời gian hoàn ứng tối đa 10 tháng kể từ tháng kế tiếp sau khi nhận được lương tạm ứng.\n2. NLĐ có thâm niên làm việc từ 3 năm trở lên được tạm ứng tối đa 06 tháng lương gộp và thời gian hoàn ứng tối đa 18 tháng kể từ tháng kế tiếp sau khi nhận được lương tạm ứng.",
    "chunk_id": "7387464543234bf11c3f6ac08af7a823dddb6e36304c13cc6b4696ab94242825",
    "document_id": "doc_b8a1e08191f021bb",
    "score": 1.663459
  },
  {
    "content": "## 2.1. Điều kiện tạm ứng\n\n- Nhân viên có nhu cầu tài chính đột xuất để thanh toán các khoản chi phí điều trị bệnh nặng, bệnh hiểm nghèo (theo danh sách bệnh hiểm nghèo do Chính phủ /Bộ Y Tế và Tổng Liên Đoàn Lao động Việt Nam quy định) cho bản thân Nhân viên hoặc Thân nhân.\n- Nhân viên có thời hạn HĐLĐ còn hiệu lực ít nhất ba (03) tháng.\n- Trường hợp HĐLĐ sắp hết hạn, cần có xác nhận của DH về việc gia hạn ký tiếp HĐLĐ\n- Nhân viên không đang trong giai đoạn hoàn ứng cho khoản vay khác, không vướng xử lý kỷ luật trong vòng 06 tháng gần nhất và không trong giai đoạn xử lý thôi việc.",
    "chunk_id": "aca79e2a9fe63e8900f7a84438b6d90dde26000a7920aed66eceac06864d9eb2",
    "document_id": "doc_1726111893d7b3d8",
    "score": 1.81129
  }
];
