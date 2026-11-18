export type Api = (path: string, method?: string, data?: unknown, key?: string) => Promise<any>;
export type Stage = 'LEGACY' | 'PRE_ACTION_INSPECTION' | 'POST_ACTION_RECEIPT' | 'RECONCILIATION_INSPECTION';
export type Proof = { id: string; operation_id: string; stage?: Stage; source_kind: string;
  payload_hash: string; observed_at: string; received_at: string;
  payload: { confirm?: boolean; result?: string; actual_serial?: string; recipient_id?: string; context_hash?: string } };
export type Operation = { id?: string; operation_id?: string; protocol_version?: '0.2' | null;
  stage?: Stage; receipt_id?: string | null; receipt_hash?: string | null;
  receipt_observed_at?: string | null; case_version?: number; confirmation_status?: string;
  purpose: string; expected_serial: string; customer_id: string; station_id: string;
  context_hash: string; expires_at: string; consumed_at?: string | null; cancelled_at?: string | null;
  context?: { reconciliation_only?: boolean; predecessor_id?: string };
  attestations?: Proof[]; authorization?: { id: string; acknowledgment_id?: string;
    transport_acknowledged: boolean; revoked_at?: string | null; expires_at: string } | null };
export type Case = { state: string; version: number; active_operation?: Operation;
  recovery_confirmation?: Operation; old_pin_settled?: boolean; new_pin_delivered?: string };
export const purposes = ['VERIFY_OLD_POSSESSION', 'RETURN_OLD_TO_CUSTOMER', 'VERIFY_NEW_DELIVERY', 'RETURN_FOREIGN_OBJECT', 'RESUME_SWAP'];
export function operationOf(record: Case, role: string) {
  return role === 'CUSTOMER' ? record.recovery_confirmation : record.active_operation;
}
export function operationId(op: Operation) { return op.id ?? op.operation_id; }
export function closed(op: Operation, now = Date.now()) {
  return Boolean(op.consumed_at || op.cancelled_at
    || ['EXPIRED', 'CONSUMED', 'CANCELLED', 'REVOKED'].includes(op.confirmation_status ?? '')
    || Date.parse(op.expires_at) <= now || !Number.isFinite(Date.parse(op.expires_at)));
}
export function stageOf(op: Operation): Stage {
  if (op.stage) return op.stage;
  if (op.context?.reconciliation_only) return 'RECONCILIATION_INSPECTION';
  if (op.protocol_version !== '0.2') return 'LEGACY';
  return op.attestations?.some(p => p.stage === 'POST_ACTION_RECEIPT' && p.source_kind === 'SIMULATOR')
    ? 'POST_ACTION_RECEIPT' : 'PRE_ACTION_INSPECTION';
}
export function receiptOf(op: Operation) {
  const stage = stageOf(op);
  return op.attestations?.find(p => p.source_kind === 'SIMULATOR' && p.stage === stage
    && p.operation_id === operationId(op) && p.payload.context_hash === op.context_hash);
}
export function reference(op: Operation) {
  const base = { operation_id: operationId(op), context_hash: op.context_hash };
  if (!base.operation_id || !/^[a-f0-9]{64}$/.test(base.context_hash)) throw new Error('Thiếu operation/context hợp lệ.');
  if (stageOf(op) === 'LEGACY') return base;
  if (op.stage && op.receipt_id && op.receipt_hash && /^[a-f0-9]{64}$/.test(op.receipt_hash))
    return { ...base, stage: op.stage, receipt_id: op.receipt_id, receipt_hash: op.receipt_hash };
  const proof = receiptOf(op);
  if (!proof || !/^[a-f0-9]{64}$/.test(proof.payload_hash)) throw new Error('Thiếu receipt đúng operation và stage.');
  return { ...base, stage: stageOf(op), receipt_id: proof.id, receipt_hash: proof.payload_hash };
}
export function sources(op: Operation, stage = stageOf(op)) {
  return (op.attestations ?? []).filter(p => p.operation_id === operationId(op)
    && (p.stage ?? 'LEGACY') === stage);
}
export function completeProof(op: Operation, stage = stageOf(op)) {
  const entries = sources(op, stage);
  return ['SIMULATOR', 'TECHNICIAN', 'CUSTOMER'].every(source => entries.some(p =>
    p.source_kind === source && (source === 'SIMULATOR' ? p.payload.result === 'OBSERVED' : p.payload.confirm === true)));
}
export function hasRejection(op: Operation) {
  return op.attestations?.some(p => p.payload.confirm === false || p.payload.result === 'REJECTED') ?? false;
}
export type Action = 'CONFIRM' | 'REJECT' | 'BEGIN' | 'INTENT' | 'ACTIVATE' | 'SETTLE' | 'REINSPECT' | 'CLOSE_NO_EFFECT';
export function requestFor(record: Case, role: string, action: Action, note: string, serial = '', purpose = purposes[0]) {
  const op = operationOf(record, role);
  const customer = role === 'CUSTOMER';
  if (role !== 'TECHNICIAN' && !(customer && ['CONFIRM', 'REJECT'].includes(action))) throw new Error('FORBIDDEN');
  if (record.state === 'RESOLVED') throw new Error('Recovery đã đóng.');
  if (customer) {
    if (!op || (op.purpose === 'RETURN_FOREIGN_OBJECT' && op.protocol_version !== '0.2'))
      throw new Error('API Customer chưa cung cấp stage và receipt reference cho operation này.');
    if (op.confirmation_status && op.confirmation_status !== 'AVAILABLE')
      throw new Error('Chưa thể xác nhận: ' + op.confirmation_status);
    if (op.protocol_version === '0.2' && (!op.stage || op.stage === 'LEGACY'))
      throw new Error('Thiếu stage của Backend.');
    if (closed(op)) throw new Error('Operation đã hết hạn hoặc đóng.');
    return { suffix: 'confirmations', body: { ...reference(op), confirm: action === 'CONFIRM' } };
  }
  if (!note.trim()) throw new Error('Cần ghi chú kiểm tra.');
  const version = { expected_version: record.version };
  if (action === 'BEGIN') {
    if (!purposes.includes(purpose)) throw new Error('Purpose không hợp lệ.');
    return { suffix: 'evidence', body: { ...version, note, statement: { kind: 'BEGIN_OPERATION', purpose } } };
  }
  if (!op) throw new Error('Chưa có operation.');
  const id = operationId(op);
  const binding = { operation_id: id, context_hash: op.context_hash };
  if (action === 'REINSPECT' || action === 'CLOSE_NO_EFFECT') {
    if (op.protocol_version !== '0.2' || op.context?.reconciliation_only || op.cancelled_at || op.consumed_at || Date.parse(op.expires_at) > Date.now())
      throw new Error('Chỉ gửi đối soát cho predecessor 0.2 đã hết hạn và chưa đóng.');
    return { suffix: 'evidence', body: { ...version, note, statement: { ...binding, kind: action === 'REINSPECT' ? 'REINSPECT_OPERATION' : 'CLOSE_NO_EFFECT' } } };
  }
  if (closed(op) || op.authorization?.revoked_at) throw new Error('Operation/authorization đã hết hạn, đóng hoặc thu hồi.');
  if (['CONFIRM', 'REJECT'].includes(action)) {
    if (!serial.trim()) throw new Error('Cần nhập serial thực tế đã kiểm tra.');
    return { suffix: 'evidence', body: { ...version, note, statement: { ...reference(op), kind: 'TECHNICIAN_ATTEST', actual_serial: serial, observation: action } } };
  }
  if (hasRejection(op)) throw new Error('Có lời chứng REJECT. Cần tiếp tục review.');
  if (action === 'INTENT' || action === 'ACTIVATE') {
    if (op.protocol_version !== '0.2' || op.context?.reconciliation_only || !completeProof(op, 'PRE_ACTION_INSPECTION') || stageOf(op) !== 'PRE_ACTION_INSPECTION')
      throw new Error('Chưa đủ PRE proof để xin phép.');
    reference(op);
    if (action === 'INTENT' && op.authorization) throw new Error('Intent đã tồn tại. Hãy tra cứu.');
    const permit = op.authorization;
    if (action === 'ACTIVATE' && (!permit?.transport_acknowledged || !permit.acknowledgment_id || Date.parse(permit.expires_at) <= Date.now()))
      throw new Error('Chưa có ACK intent hợp lệ.');
    return { suffix: 'evidence', body: { ...version, note, statement: { ...binding, kind: 'AUTHORIZE_ACTION',
      phase: action === 'ACTIVATE' ? 'ACTIVATE' : 'INTENT',
      ...(action === 'ACTIVATE' ? { authorization_id: permit!.id, acknowledgment_id: permit!.acknowledgment_id } : {}) } } };
  }
  if (op.protocol_version === '0.2' && (stageOf(op) === 'PRE_ACTION_INSPECTION' || !completeProof(op))) throw new Error('Chưa đủ ba nguồn proof sau action/đối soát.');
  if (op.protocol_version === '0.2') reference(op);
  return { suffix: 'settle', body: { ...version, operation_id: id, resolution_note: note } };
}

export class RecoveryClient {
  busy = false;
  generation = 0;
  keys = new Map<string, string>();
  constructor(public api: Api, public role: string, public publish: (value: Case | null) => void) {}
  reset() { this.generation++; this.publish(null); }
  path(id: string) { return '/v1/swaps/' + encodeURIComponent(id) + (this.role === 'CUSTOMER' ? '' : '/recovery'); }
  async load(id: string) {
    const generation = ++this.generation;
    const value: Case = await this.api(this.path(id));
    if (generation === this.generation) this.publish(value);
  }
  async mutate(id: string, shown: Case, action: Action, note: string, serial: string, purpose: string) {
    if (this.busy) return false;
    this.busy = true;
    const generation = this.generation;
    try {
      const current: Case = await this.api(this.path(id));
      if (generation !== this.generation) return false;
      if (JSON.stringify(current) !== JSON.stringify(shown)) {
        this.publish(current);
        throw new Error('Dữ liệu/receipt đã đổi. Kiểm tra bản mới trước khi thao tác.');
      }
      const request = requestFor(current, this.role, action, note, serial, purpose);
      const path = '/v1/swaps/' + encodeURIComponent(id) + '/recovery/' + request.suffix;
      const signature = path + JSON.stringify(request.body);
      let key = this.keys.get(signature);
      if (!key) { key = crypto.randomUUID(); this.keys.set(signature, key); }
      await this.api(path, 'POST', request.body, key);
      if (generation !== this.generation) return false;
      await this.load(id);
      return true;
    } catch (error) {
      // A mutation may already have committed. Refresh state, never resend it.
      if (generation === this.generation) {
        try { await this.load(id); } catch { this.publish(null); }
      }
      throw error;
    } finally { this.busy = false; }
  }
}
