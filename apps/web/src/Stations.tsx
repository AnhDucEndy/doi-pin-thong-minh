import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';

type Api = (path: string, method?: string, data?: unknown, key?: string) => Promise<any>;
type Station = { id: string; name: string; address: string; state: string; version: number };
type Slot = { id: string; slot_no: number; service_state: string; door_state: string; observed_present: boolean | null; observed_serial: string | null; version: number };
type Device = { id: string; station_id: string; serial: string; enabled: boolean; version: number };
type Available = { station_id: string; name: string; address: string; operational_state: string; available_count: number };

export function Stations({ api, role }: { api: Api; role: string }) {
  const [stations, setStations] = useState<Available[]>([]);
  const [selected, setSelected] = useState('');
  const [station, setStation] = useState<Station | null>(null);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [secret, setSecret] = useState('');
  const pendingKeys = useRef(new Map<string, string>());
  async function all(path: string) {
    let cursor: string | null = null; const items: any[] = [];
    do { const page = await api(path + '?limit=100' + (cursor ? `&cursor=${cursor}` : '')); items.push(...page.items); cursor = page.next_cursor; } while (cursor);
    return items;
  }
  async function details(id: string) {
    const [s, c, d] = await Promise.all([api(`/v1/stations/${id}`), all(`/v1/stations/${id}/compartments`), all('/v1/devices')]);
    return { s, c, d: d.filter((device: Device) => device.station_id === id) };
  }
  useEffect(() => { let cancelled = false; all('/v1/stations').then(items => { if (!cancelled) setStations(items); }).catch(e => { if (!cancelled) setError(e.message); }); return () => { cancelled = true; }; }, [api]);
  useEffect(() => {
    let cancelled = false; setStation(null); setSlots([]); setDevices([]); setSecret(''); setError('');
    if (selected) details(selected).then(({ s, c, d }) => { if (!cancelled) { setStation(s); setSlots(c); setDevices(d); } }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [selected, api]);
  async function perform(action: () => Promise<unknown>) {
    setBusy(true); setError(''); setNotice('');
    try { await action(); setStations(await all('/v1/stations')); if (selected) { const { s, c, d } = await details(selected); setStation(s); setSlots(c); setDevices(d); } setNotice('Đã cập nhật.'); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>, action: (data: FormData) => Promise<unknown>) { event.preventDefault(); const data = new FormData(event.currentTarget); void perform(() => action(data)); }
  const mutate = async (path: string, method: string, body: unknown) => {
    const fingerprint = JSON.stringify([path, method, body]);
    const key = pendingKeys.current.get(fingerprint) ?? crypto.randomUUID();
    pendingKeys.current.set(fingerprint, key);
    const result = await api(path, method, body, key);
    pendingKeys.current.delete(fingerprint);
    return result;
  };
  return <section className="station-module">
    <div className="section-heading"><h2>Mạng lưới trạm</h2><button disabled={busy} onClick={() => void perform(async () => {})}>Tải lại</button></div>
    {error && <p className="message error" role="alert">{error}</p>}{notice && <p className="message success" role="status">{notice}</p>}
    <div className="station-grid">{stations.map(s => <article className="card" key={s.station_id}><h3>{s.name}</h3><p>{s.address}</p><p><span className="badge">{s.operational_state}</span> · {s.available_count} pin đủ điều kiện</p>{role !== 'CUSTOMER' && <button onClick={() => setSelected(s.station_id)}>Xem trạm và ngăn</button>}</article>)}</div>
    {role === 'ADMIN' && <details className="card"><summary>Tạo trạm</summary><form onSubmit={e => submit(e, f => mutate('/v1/stations', 'POST', Object.fromEntries(f)))}><label>Mã trạm<input name="code" required/></label><label>Tên trạm<input name="name" required/></label><label>Địa chỉ<input name="address" required/></label><button disabled={busy}>Tạo trạm</button></form></details>}
    {station && <section className="card" key={station.id}><h2>{station.name}</h2><p>{station.address} · {station.state}</p>
      {role === 'ADMIN' && <form key={station.version} onSubmit={e => submit(e, f => mutate(`/v1/stations/${station.id}`, 'PATCH', { ...Object.fromEntries(f), expected_version: station.version }))}><label>Tên trạm<input name="name" defaultValue={station.name} required/></label><label>Địa chỉ<input name="address" defaultValue={station.address} required/></label><label>Phục vụ<select name="state" defaultValue={station.state}>{['ACTIVE', 'MAINTENANCE', 'INACTIVE'].map(s => <option key={s}>{s}</option>)}</select></label><button disabled={busy}>Lưu trạm</button></form>}
      <h3>Thiết bị điều khiển</h3>{devices.map(d => <p key={d.id}>{d.serial} · {d.enabled ? 'Đã kích hoạt' : 'Đã vô hiệu hóa'} {role === 'ADMIN' && <button disabled={busy} onClick={() => { if (confirm('Thay đổi trạng thái thiết bị? Giao dịch liên quan có thể cần đối soát.')) void perform(() => mutate(`/v1/devices/${d.id}`, 'PATCH', { expected_version: d.version, enabled: !d.enabled })); }}>{d.enabled ? 'Vô hiệu hóa' : 'Kích hoạt'}</button>}</p>)}
      {role === 'ADMIN' && devices.length === 0 && <form onSubmit={e => submit(e, async f => { const result = await mutate('/v1/devices', 'POST', { station_id: station.id, serial: f.get('serial') }); setSecret(result.device_key_once); })}><label>Serial thiết bị<input name="serial" required/></label><button disabled={busy}>Đăng ký thiết bị</button></form>}
      {secret && <div className="message" role="status">Khóa thiết bị — lưu an toàn trước khi đóng: <code>{secret}</code> <button onClick={() => setSecret('')}>Ẩn khóa</button></div>}
      <h3>Ngăn tủ</h3><p className="hint">Trạng thái phục vụ và cửa được quản lý độc lập. Khôi phục cần ID sự kiện SNAPSHOT hợp lệ.</p>
      <div className="compartment-grid">{slots.sort((a, b) => a.slot_no - b.slot_no).map(slot => <article className="card" key={slot.id}><h3>Ngăn {slot.slot_no}</h3><p>Phục vụ: <strong>{slot.service_state}</strong></p><p>Cửa: <strong>{slot.door_state}</strong></p><p>Pin: {slot.observed_present === null ? 'Chưa xác định' : slot.observed_present ? slot.observed_serial || 'Có pin, chưa rõ serial' : 'Trống'}</p>{slot.service_state !== 'RETIRED' && <form onSubmit={e => submit(e, f => mutate(`/v1/compartments/${slot.id}/actions`, 'POST', { expected_version: slot.version, action: f.get('action'), reason: f.get('reason'), ...(f.get('evidence') ? { evidence_event_id: f.get('evidence') } : {}) }))}><label>Thao tác<select name="action">{['ACTIVE', 'BLOCKED'].includes(slot.service_state) && <option value="SET_MAINTENANCE">Bảo trì</option>}{['BLOCKED', 'MAINTENANCE'].includes(slot.service_state) && <option value="RESTORE">Khôi phục phục vụ</option>}{role === 'ADMIN' && slot.service_state === 'MAINTENANCE' && <option value="RETIRE">Ngừng sử dụng vĩnh viễn</option>}</select></label><label>Lý do<input name="reason" required/></label><label>ID SNAPSHOT (khi khôi phục)<input name="evidence"/></label><button disabled={busy}>Thực hiện</button></form>}</article>)}</div>
      {role === 'ADMIN' && <form onSubmit={e => submit(e, f => mutate(`/v1/stations/${station.id}/compartments`, 'POST', { slot_no: Number(f.get('slot_no')) }))}><label>Số ngăn mới<input type="number" min="1" name="slot_no" required/></label><button disabled={busy}>Thêm ngăn</button></form>}
    </section>}
  </section>;
}
