import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';

type Api = (path: string, method?: string, data?: unknown, key?: string) => Promise<any>;
type Battery = { id: string; serial: string; family: string; lifecycle: string; location_kind: string; compartment_id: string | null; holder_user_id: string | null; version: number };
type Reading = { id: string; soc: number | null; soh: number | null; temperature_c: number | null; fault_codes: string[]; quality_ok: boolean; measured_at: string; received_at: string };

export function Batteries({ api, role }: { api: Api; role: string }) {
  const [pins, setPins] = useState<Battery[]>([]);
  const [selected, setSelected] = useState('');
  const [readings, setReadings] = useState<Reading[]>([]);
  const [assessment, setAssessment] = useState<{ available: boolean; at: string; limits: number[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const pending = useRef(new Map<string, string>());
  const pin = pins.find(p => p.id === selected);
  const load = useCallback(async () => {
    const items: Battery[] = []; let cursor: string | null = null;
    do { const page = await api('/v1/batteries?limit=100' + (cursor ? `&cursor=${cursor}` : '')); items.push(...page.items); cursor = page.next_cursor; } while (cursor);
    return items;
  }, [api]);
  useEffect(() => { let cancelled = false; setLoading(true); load().then(items => { if (!cancelled) setPins(items); }).catch(e => { if (!cancelled) setError(e.message); }).finally(() => { if (!cancelled) setLoading(false); }); return () => { cancelled = true; }; }, [load]);
  const detail = useCallback(async (id: string) => api(`/v1/batteries/${id}/telemetry?limit=100`), [api]);
  function applyDetail(result: any) { setReadings(result.items); setAssessment(result.assessment); }
  useEffect(() => { let cancelled = false; setReadings([]); setAssessment(null); setError(''); if (selected) { setLoading(true); detail(selected).then(result => { if (!cancelled) applyDetail(result); }).catch(e => { if (!cancelled) setError(e.message); }).finally(() => { if (!cancelled) setLoading(false); }); } return () => { cancelled = true; }; }, [selected, detail]);
  async function mutate(path: string, body: unknown) {
    const fingerprint = JSON.stringify([path, body]);
    const key = pending.current.get(fingerprint) ?? crypto.randomUUID(); pending.current.set(fingerprint, key);
    const result = await api(path, 'POST', body, key); pending.current.delete(fingerprint); return result;
  }
  async function perform(action: () => Promise<unknown>) {
    setBusy(true); setError(''); setNotice(''); setAssessment(null);
    try { await action(); setPins(await load()); if (selected) applyDetail(await detail(selected)); setNotice('Đã cập nhật hồ sơ pin.'); }
    catch (e) { setError((e as Error).message); setPins(await load().catch(() => pins)); }
    finally { setBusy(false); }
  }
  function submit(e: FormEvent<HTMLFormElement>, action: (f: FormData) => Promise<unknown>) { e.preventDefault(); const form = new FormData(e.currentTarget); void perform(() => action(form)); }
  const latest = readings[0];
  const stale = !latest || !assessment || now - Date.parse(latest.received_at) > assessment.limits[3] * 1000;
  const freshAssessment = assessment && now - Date.parse(assessment.at) < assessment.limits[3] * 1000;
  const actions = pin?.lifecycle === 'RETIRED' ? [] : role === 'ADMIN' ? ['RETIRE'] :
    pin?.lifecycle === 'REGISTERED' ? ['ACTIVATE', 'QUARANTINE'] : pin?.lifecycle === 'IN_SERVICE' ? ['QUARANTINE'] : ['RESTORE'];
  const labels: Record<string, string> = { RETIRE: 'Ngừng sử dụng', ACTIVATE: 'Xác nhận đưa vào phục vụ', QUARANTINE: 'Cách ly', RESTORE: 'Phục hồi sau kiểm tra' };
  return <section className="station-module"><div className="section-heading"><h2>Pin và BMS</h2><button disabled={busy || loading} onClick={() => void perform(async () => {})}>Tải lại</button></div>
    <p className="hint">Dữ liệu mô phỏng phần mềm. SOC/SOH/nhiệt độ không thay thế bằng chứng thiết bị. Admin quản lý hồ sơ/ngừng pin; Technician được phân công xác minh/cách ly/phục hồi.</p>
    {loading && <p role="status">Đang tải dữ liệu pin…</p>}{error && <p className="message error" role="alert">{error}</p>}{notice && <p className="message success" role="status">{notice}</p>}
    {!loading && !pins.length && !error && <p>Không có pin trong phạm vi truy cập.</p>}
    <div className="station-grid">{pins.map(p => <article className="card" key={p.id}><h3>{p.serial}</h3><p>{p.family} · <strong>{p.lifecycle}</strong></p><p>Vị trí: {p.location_kind}</p><button disabled={busy} onClick={() => setSelected(p.id)}>Xem hồ sơ và BMS</button></article>)}</div>
    {role === 'ADMIN' && <details className="card"><summary>Đăng ký pin</summary><form onSubmit={e => submit(e, f => mutate('/v1/batteries', { serial: f.get('serial'), family: f.get('family'), location_kind: f.get('location_kind'), ...(f.get('compartment_id') ? { compartment_id: f.get('compartment_id') } : {}), ...(f.get('holder_user_id') ? { holder_user_id: f.get('holder_user_id') } : {}) }))}><label>Serial<input name="serial" required/></label><label>Họ pin<input name="family" defaultValue="DEMO_FAMILY_A" required/></label><label>Vị trí ban đầu<select name="location_kind"><option>UNKNOWN</option><option>COMPARTMENT</option><option>CUSTOMER</option></select></label><label>ID ngăn (COMPARTMENT)<input name="compartment_id"/></label><label>ID khách (CUSTOMER)<input name="holder_user_id"/></label><button disabled={busy}>Đăng ký</button></form></details>}
    {pin && <section className="card" key={pin.id}><h2>Hồ sơ {pin.serial}</h2><p>ID: {pin.id}</p><p>Vòng đời: {pin.lifecycle} · Phiên bản {pin.version}</p><p>Ngăn: {pin.compartment_id ?? '—'} · Khách giữ: {pin.holder_user_id ?? '—'}</p>
      <p className={assessment?.available && freshAssessment ? 'message success' : 'message'}>{assessment?.available && freshAssessment ? 'Backend xác nhận đủ điều kiện cấp tại thời điểm đánh giá.' : 'Chưa được xác nhận đủ điều kiện cấp.'} {assessment && `Đánh giá: ${new Date(assessment.at).toLocaleString('vi-VN')}`}</p>
      {assessment && <p className="hint">Ngưỡng demo: SOC ≥ {assessment.limits[0]}%, SOH ≥ {assessment.limits[1]}%, nhiệt độ ≤ {assessment.limits[2]}°C; độ mới {assessment.limits[3]} giây. Đây là giả định mô phỏng.</p>}
      {!readings.length ? <p>Chưa có bằng chứng BMS.</p> : <><p className="message">{stale || !latest.quality_ok ? 'BMS thiếu, cũ hoặc chưa được xác minh; không coi là an toàn.' : 'Có mẫu BMS; khả dụng vẫn phụ thuộc các ràng buộc Backend.'}</p><div className="table-scroll"><table><thead><tr><th>SOC %</th><th>SOH %</th><th>Nhiệt độ °C</th><th>Cờ lỗi</th><th>Quality</th><th>Thời điểm đo</th></tr></thead><tbody>{readings.map(r => <tr key={r.id}><td>{r.soc ?? 'Thiếu'}</td><td>{r.soh ?? 'Thiếu'}</td><td>{r.temperature_c ?? 'Thiếu'}</td><td>{r.fault_codes.join(', ') || '—'}</td><td>{r.quality_ok ? 'Có' : 'Chưa xác minh'}</td><td>{new Date(r.measured_at).toLocaleString('vi-VN')}</td></tr>)}</tbody></table></div>{readings.length === 100 && <p className="hint">Hiển thị tối đa 100 mẫu mới nhất; API hỗ trợ phân trang lịch sử.</p>}</>}
      {actions.length > 0 && <form key={pin.version} onSubmit={e => submit(e, f => mutate(`/v1/batteries/${pin.id}/actions`, { expected_version: pin.version, action: f.get('action'), reason: f.get('reason'), ...(f.get('evidence') ? { evidence_event_id: f.get('evidence') } : {}), ...(f.get('alerts') ? { resolve_alert_ids: String(f.get('alerts')).split(',').map(s => s.trim()) } : {}) }))}><label>Thao tác<select name="action">{actions.map(a => <option key={a} value={a}>{labels[a]}</option>)}</select></label><label>Lý do kiểm tra<input name="reason" required/></label>{role === 'TECHNICIAN' && <><label>ID SNAPSHOT hợp lệ (kích hoạt/phục hồi)<input name="evidence"/></label><label>ID cảnh báo cần resolve khi phục hồi, cách nhau dấu phẩy<input name="alerts"/></label></>}<button disabled={busy || loading}>Thực hiện</button></form>}
    </section>}
  </section>;
}
