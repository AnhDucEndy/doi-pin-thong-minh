import { useEffect, useMemo, useState } from 'react';
import { RecoveryClient, closed, completeProof, hasRejection, operationId, operationOf, purposes,
  receiptOf, requestFor, sources, stageOf } from './recoveryModel';
import type { Action, Api, Case, Operation, Stage } from './recoveryModel';

const labels: Record<Stage, string> = {
  LEGACY: 'Đối soát 0.1',
  PRE_ACTION_INSPECTION: 'PRE_ACTION_INSPECTION — kiểm tra trước action',
  POST_ACTION_RECEIPT: 'POST_ACTION_RECEIPT — xác nhận sau action',
  RECONCILIATION_INSPECTION: 'RECONCILIATION_INSPECTION — quan sát successor chỉ đọc',
};
export function RecoveryDetails({ record, role }: { record: Case; role: string }) {
  const op = operationOf(record, role);
  return <div>
    <p>Trạng thái Backend: <strong>{record.state}</strong></p>
    {role !== 'CUSTOMER' && <p>Pin cấp: {record.new_pin_delivered ?? 'UNKNOWN'} · Nghĩa vụ pin cũ: {record.old_pin_settled ? 'Backend đã xác minh' : 'Chưa giải quyết'}</p>}
    <p>UI không tự thay đổi Payment hoặc giải phóng ba holds. Chỉ Backend quyết định custody và trạng thái kết thúc.</p>
    {!op ? <p>Chưa có operation hiện hành để xác nhận.</p> : <OperationDetails op={op} customer={role === 'CUSTOMER'} />}
  </div>;
}
function OperationDetails({ op, customer }: { op: Operation; customer: boolean }) {
  const receipt = receiptOf(op);
  return <div className="card">
    <p>Mục đích: {op.purpose}</p>
    <p style={{ overflowWrap: 'anywhere' }}>Operation: <code>{operationId(op)}</code></p>
    <p>Context hash: <code style={{ overflowWrap: 'anywhere' }}>{op.context_hash}</code></p>
    <p>Trạm: {op.station_id}</p><p>Principal nhận/trình: {op.customer_id}</p>
    <p>Serial cần đối chiếu: {op.expected_serial}. Việc trình/nhận vật lạ chưa chứng minh quyền sở hữu.</p>
    <p>Hạn: {new Date(op.expires_at).toLocaleString('vi-VN')}</p>
    <p>{op.confirmation_status === 'CONSUMED' || op.consumed_at ? 'Operation đã consumed'
      : op.confirmation_status === 'CANCELLED' || op.cancelled_at ? 'Operation đã đóng'
      : op.confirmation_status === 'REVOKED' ? 'REVOKED — operation đã bị thu hồi'
      : op.confirmation_status === 'EXPIRED' || closed(op) ? 'EXPIRED — tiếp tục review; chưa chứng minh no-effect'
      : 'Operation còn hạn'}</p>
    {customer ? <>
      <p>Stage: {op.stage ? labels[op.stage] : 'Đối soát 0.1; thiếu metadata staged'}</p>
      <p>Trạng thái xác nhận: {op.confirmation_status ?? 'Chưa có projection đầy đủ'}</p>
      {op.protocol_version === '0.2' ? <p>
        Receipt Backend: {op.receipt_id ?? 'Chưa có'}<br />
        Hash: <code style={{ overflowWrap: 'anywhere' }}>{op.receipt_hash ?? 'Chưa có'}</code><br />
        Quan sát: {op.receipt_observed_at ? new Date(op.receipt_observed_at).toLocaleString('vi-VN') : 'UNKNOWN'}
      </p> : op.purpose === 'RETURN_FOREIGN_OBJECT' && <p>API chưa trả protocol và receipt phù hợp; xác nhận bị chặn.</p>}
    </> : <>
      <p>Stage hiện tại: {labels[stageOf(op)]}</p>
      {op.context?.predecessor_id && <p>Predecessor: {op.context.predecessor_id}. Successor chỉ quan sát; không cấp action mới.</p>}
      {(['LEGACY', 'PRE_ACTION_INSPECTION', 'POST_ACTION_RECEIPT', 'RECONCILIATION_INSPECTION'] as Stage[]).map(stage => {
        const entries = sources(op, stage);
        return entries.length > 0 && <div key={stage}><h3>{labels[stage]}</h3><ul>{entries.map(p => <li key={p.id}>
          {p.source_kind}: {p.payload.confirm === false ? 'REJECT' : p.payload.confirm === true ? 'CONFIRM' : p.payload.result ?? 'UNKNOWN'}
          {' · '}receipt {p.id}<br />Hash: <code style={{ overflowWrap: 'anywhere' }}>{p.payload_hash}</code>
          <br />Quan sát: {new Date(p.observed_at).toLocaleString('vi-VN')}
        </li>)}</ul></div>;
      })}
      {receipt ? <p>Reference cho thao tác kế tiếp: {receipt.id} · {labels[stageOf(op)]}.
        Serial quan sát: {receipt.payload.actual_serial ?? 'UNKNOWN'} · Recipient quan sát: {receipt.payload.recipient_id ?? 'Không có trong receipt'}.
        Backend kiểm lại freshness và provenance khi ghi nhận.</p> : <p>Thiếu receipt simulator đúng stage. Chưa thể xác nhận staged proof.</p>}
      {op.authorization && <p>Intent {op.authorization.id} · ACK: {op.authorization.transport_acknowledged ? op.authorization.acknowledgment_id : 'Chưa có'} · {op.authorization.revoked_at ? 'REVOKED' : 'ACK chưa chứng minh handover'}</p>}
      <p>API chưa trả closure intent/activation summary. cancelled_at chỉ xác nhận operation đã đóng; không suy trạng thái fence từ TTL hoặc thiếu receipt.</p>
    </>}
  </div>;
}

export function Recovery({ api, role }: { api: Api; role: string }) {
  const [identity, setIdentity] = useState('');
  const [loaded, setLoaded] = useState('');
  const [record, setRecord] = useState<Case | null>(null);
  const [purpose, setPurpose] = useState(purposes[0]);
  const [serial, setSerial] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [, tick] = useState(0);
  const client = useMemo(() => new RecoveryClient(api, role, setRecord), [api, role]);
  useEffect(() => {
    const timer = setInterval(() => tick(n => n + 1), 1000);
    return () => { clearInterval(timer); client.reset(); };
  }, [client]);
  const op = record ? operationOf(record, role) : undefined;
  async function load(id: string) {
    if (client.busy) return;
    setBusy(true); setError(''); setNotice(''); client.reset();
    try { await client.load(id); setLoaded(id); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function act(action: Action) {
    if (!record || client.busy) return;
    setBusy(true); setError(''); setNotice('');
    try {
      if (await client.mutate(loaded, record, action, note, serial, purpose)) {
        setNotice('API đã ghi nhận yêu cầu. Dữ liệu hiển thị được tải lại từ Backend.');
        setSerial('');
      }
    } catch (e) {
      const failure = e as Error & { code?: string };
      setError((failure.code ? failure.code + ' — ' : '') + failure.message
        + ' Nếu mất response, hãy tra cứu trạng thái; không suy đoán effect hoặc gửi action vật lý lại.');
    } finally { setBusy(false); }
  }
  function enabled(action: Action) {
    if (!record || busy) return false;
    try { requestFor(record, role, action, note, serial, purpose); return true; } catch { return false; }
  }
  const already = op && sources(op).some(p => p.source_kind === role);
  return <section className="card">
    <h2>Recovery — đối soát mô phỏng</h2>
    <p>UNKNOWN/REVIEW_REQUIRED cần bằng chứng được Backend chấp nhận. Payment SUCCEEDED chưa chứng minh COMPLETED.</p>
    <form onSubmit={e => { e.preventDefault(); void load(identity.trim()); }}>
      <label>ID phiên<input value={identity} disabled={busy} required onChange={e => {
        setIdentity(e.target.value); setLoaded(''); client.reset(); setError(''); setNotice('');
      }} /></label>
      <button disabled={busy || !identity.trim()}>Tra cứu trạng thái Backend</button>
    </form>
    {busy && <p role="status">Đang xử lý…</p>}
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {record && <>
      <button disabled={busy} onClick={() => void load(loaded)}>Làm mới trước thao tác</button>
      <RecoveryDetails record={record} role={role} />
      {role === 'TECHNICIAN' && record.state !== 'RESOLVED' && <>
        <label>Ghi chú<input value={note} onChange={e => setNote(e.target.value)} disabled={busy} /></label>
        <label>Mục đích<select value={purpose} disabled={busy} onChange={e => setPurpose(e.target.value)}>{purposes.map(p => <option key={p}>{p}</option>)}</select></label>
        <button disabled={!enabled('BEGIN')} onClick={() => void act('BEGIN')}>Tạo operation</button>
        {op && <>
          <label>Serial thực tế Technician đã kiểm tra<input value={serial} disabled={busy} onChange={e => setSerial(e.target.value)} /></label>
          <button disabled={!enabled('CONFIRM') || already} onClick={() => void act('CONFIRM')}>Technician CONFIRM — {labels[stageOf(op)]}</button>
          <button disabled={!enabled('REJECT') || already} onClick={() => void act('REJECT')}>Technician REJECT — {labels[stageOf(op)]}</button>
          {already && <p>Lời chứng ở stage này đã có; không thể ghi đè.</p>}
          {hasRejection(op) && <p role="alert">Có REJECT. Giữ review và không tự thực hiện lại.</p>}
          {op.protocol_version === '0.2' && <>
            <button disabled={!enabled('INTENT')} onClick={() => void act('INTENT')}>Yêu cầu authorization intent</button>
            <button disabled={!enabled('ACTIVATE')} onClick={() => void act('ACTIVATE')}>Chủ động yêu cầu activation</button>
            <p>Activation cần intent và ACK hợp lệ. Service operator thực hiện qua simulator riêng. Hãy tra cứu POST receipt trước xác nhận sau action.</p>
            <button disabled={!enabled('REINSPECT')} onClick={() => void act('REINSPECT')}>Yêu cầu successor inspection chỉ đọc</button>
            <button disabled={!enabled('CLOSE_NO_EFFECT')} onClick={() => void act('CLOSE_NO_EFFECT')}>Yêu cầu đối soát no-effect closure</button>
            <p>Yêu cầu closure chưa chứng minh no-effect. Backend/simulator kiểm witness và durable revocation.</p>
          </>}
          <button disabled={!enabled('SETTLE')} onClick={() => void act('SETTLE')}>Yêu cầu Backend settlement</button>
          {op.protocol_version === '0.2' && !completeProof(op) && <p>Chưa đủ ba nguồn proof ở stage hiện tại.</p>}
        </>}
      </>}
      {role === 'CUSTOMER' && op && <>
        <p>Chỉ chính bạn xác nhận điều đã trực tiếp kiểm tra. Serial/recipient/context do Backend cung cấp.</p>
        <p>{stageOf(op) === 'POST_ACTION_RECEIPT' ? 'Sau action: xác nhận bạn đã thực sự nhận đúng vật thể trong receipt này.'
          : stageOf(op) === 'RECONCILIATION_INSPECTION' ? 'Đối soát hiện tại: xác nhận bạn đang giữ đúng vật thể được quan sát; không tạo action mới.'
          : stageOf(op) === 'PRE_ACTION_INSPECTION' ? 'Trước action: xác nhận việc trình vật thể và ngữ cảnh; chưa xác nhận đã nhận lại.'
          : 'Đối soát pin theo operation hiện hành.'}</p>
        <button disabled={!enabled('CONFIRM')} onClick={() => void act('CONFIRM')}>Customer CONFIRM — {labels[stageOf(op)]}</button>
        <button disabled={!enabled('REJECT')} onClick={() => void act('REJECT')}>Customer REJECT — {labels[stageOf(op)]}</button>
      </>}
      {role === 'ADMIN' && <p>Admin chỉ xem hồ sơ; xác nhận và đối soát thuộc Technician/Customer đúng thẩm quyền.</p>}
    </>}
  </section>;
}
