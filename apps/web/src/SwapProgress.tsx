const steps: Record<string, string> = {
  AWAITING_PAYMENT: 'Đang xác minh thanh toán mô phỏng. Chưa cho phép bàn giao pin.',
  AWAITING_RETURN: 'Chờ trả đúng pin cũ vào ngăn nhận và đóng cửa. ACK chưa xác nhận đã trả pin.',
  RETURN_ACCEPTED: 'Backend đã xác minh pin cũ và cửa nhận đóng. Đang kiểm tra điều kiện cấp pin.',
  AWAITING_PICKUP: 'Chờ lấy pin mới từ ngăn cấp và đóng cửa. Chỉ hoàn tất khi Backend xác minh đủ bằng chứng.',
  COMPLETED: 'Đổi pin mô phỏng đã hoàn tất: Backend đã xác minh cả hai bước bàn giao.',
  REVIEW_REQUIRED: 'Cần nhân viên kiểm tra. Tài nguyên tiếp tục được giữ; không tự mở thêm ngăn hoặc thu thêm phí.',
};

const reasons: Record<string, string> = {
  COMMAND_OBSERVATION_MISMATCH: 'Pin quan sát không khớp với phiên đổi. Dừng cấp pin và chờ nhân viên kiểm tra.',
  SWAP_RETURN_EVIDENCE: 'Bằng chứng trả pin chưa đầy đủ, hết hạn hoặc không còn khớp trạng thái hiện tại.',
  SWAP_SUPPLY_INTERLOCK: 'Pin cấp hoặc trạng thái ngăn không còn đủ điều kiện. Pin đã trả vẫn được ghi nhận.',
  SWAP_PICKUP_EVIDENCE: 'Chưa đủ bằng chứng hợp lệ để xác nhận nhận pin. Không cấp thêm pin.',
  COMMAND_TIMEOUT: 'Hết thời gian chờ lệnh hoặc thao tác vật lý. Chưa xác nhận bàn giao thành công.',
};

export function SwapProgress({swap}: {swap: {state: string; review_reason?: string; return_observed_at?: string; pickup_observed_at?: string}}) {
  if (!steps[swap.state]) return null;
  return <section aria-label="Tiến trình đổi pin" aria-live="polite">
    <h4>Tiến trình đổi pin mô phỏng</h4><p>{steps[swap.state]}</p>
    {swap.review_reason && reasons[swap.review_reason] && <p role="alert">{reasons[swap.review_reason]}</p>}
    {swap.return_observed_at && <p>Đã xác minh trả pin: {new Date(swap.return_observed_at).toLocaleString('vi-VN')}</p>}
    {swap.pickup_observed_at && <p>Đã xác minh nhận pin: {new Date(swap.pickup_observed_at).toLocaleString('vi-VN')}</p>}
  </section>;
}
