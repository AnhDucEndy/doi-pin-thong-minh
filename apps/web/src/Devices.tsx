import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';

type Api = (path:string, method?:string, data?:unknown, key?:string)=>Promise<any>;

export function Devices({api,role}:{api:Api;role:string}) {
  const [devices,setDevices]=useState<any[]>([]);
  const [stations,setStations]=useState<any[]>([]);
  const [alerts,setAlerts]=useState<any[]>([]);
  const [summary,setSummary]=useState<any>(null);
  const [error,setError]=useState('');const [loading,setLoading]=useState(true);const [busy,setBusy]=useState(false);
  const [updated,setUpdated]=useState('');
  const load=useCallback(async()=>{
    async function all(path:string) {let cursor:string|null=null;const items:any[]=[];let poll=3;do {
      const page=await api(path+'?limit=100'+(cursor?`&cursor=${cursor}`:''));items.push(...page.items);cursor=page.next_cursor;
      if(page.poll_interval_seconds)poll=page.poll_interval_seconds;
    }while(cursor);return{items,poll};}
    const [d,s,a,summary]=await Promise.all([all('/v1/devices'),all('/v1/stations'),all('/v1/alerts'),api('/v1/dashboard')]);
    return{devices:d.items,stations:s.items,alerts:a.items,summary,poll:d.poll};
  },[api]);
  useEffect(()=>{let cancelled=false;let timer:number;async function refresh(){try{const data=await load();if(cancelled)return;
    setDevices(data.devices);setStations(data.stations);setAlerts(data.alerts);setSummary(data.summary);setUpdated(new Date().toLocaleString('vi-VN'));setError('');setLoading(false);
    timer=window.setTimeout(refresh,data.poll*1000);
  }catch(e){if(!cancelled){setError((e as Error).message);setLoading(false);timer=window.setTimeout(refresh,3000);}}}
  void refresh();return()=>{cancelled=true;window.clearTimeout(timer);};},[load]);
  async function action(e:FormEvent<HTMLFormElement>,alert:any){e.preventDefault();const f=new FormData(e.currentTarget);setBusy(true);setError('');
    try{const resolve=f.get('action')==='resolve';await api(`/v1/alerts/${alert.id}/${resolve?'resolve':'acknowledge'}`,'POST',{
      expected_version:alert.version,...(resolve?{evidence_event_id:f.get('evidence'),resolution_note:f.get('note')}:{}),
    },crypto.randomUUID());const data=await load();setAlerts(data.alerts);setDevices(data.devices);setStations(data.stations);}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <section className="station-module"><h2>Thiết bị và IoT</h2><p className="hint">Thiết bị mô phỏng · cập nhật gần nhất: {updated||'—'}. Heartbeat không thay thế dữ liệu cảm biến hoặc bằng chứng bàn giao pin.</p>
    {loading&&<p role="status">Đang tải thiết bị…</p>}{error&&<p role="alert" className="message error">{error} Dữ liệu hiển thị có thể đã cũ.</p>}
    {summary&&<p className="message">Trạm online: {summary.online_stations} · Offline: {summary.offline_stations} · Cảnh báo chưa đóng: {summary.open_alerts} · Giao dịch chờ đối soát: {summary.review_swaps}. Đánh giá: {new Date(summary.as_of).toLocaleString('vi-VN')}</p>}
    {!loading&&!devices.length&&<p>Không có thiết bị trong phạm vi được phân công.</p>}
    <div className="station-grid">{devices.map(d=>{const s=stations.find(s=>s.station_id===d.station_id);return <article key={d.id} className="card"><h3>{d.serial}</h3><p>{s?.name??d.station_id}</p><p>Vận hành: <strong>{s?.operational_state??'Chưa xác định'}</strong></p><p>Danh tính: {d.enabled?'Đã kích hoạt':'Vô hiệu hóa'}</p><p>Liên lạc được chấp nhận gần nhất: {d.last_received_at?new Date(d.last_received_at).toLocaleString('vi-VN'):'Chưa có heartbeat hợp lệ / đã mất kết nối'}</p><p>Sequence: {d.last_seq}</p></article>;})}</div>
    <h3>Cảnh báo</h3>{!alerts.length&&<p>Không có cảnh báo trong phạm vi truy cập.</p>}
    {alerts.map(a=><article key={a.id} className="card"><h3>{a.code}</h3><p>{a.state} · Số lần: {a.occurrences} · Phiên bản: {a.version}</p><p>Trạm: {stations.find(s=>s.station_id===a.station_id)?.name??a.station_id}</p><p>Ngăn: {a.compartment_id??'Toàn trạm'} · Pin: {a.battery_id??'—'}</p>
      {a.state!=='RESOLVED'&&role==='TECHNICIAN'&&<form onSubmit={e=>void action(e,a)}><label>Thao tác<select name="action"><option value="acknowledge">Xác nhận đã đọc</option><option value="resolve">Đóng cảnh báo có bằng chứng</option></select></label><label>ID SNAPSHOT khi đóng cảnh báo<input name="evidence"/></label><label>Ghi nhận kiểm tra<input name="note"/></label><button disabled={busy}>Thực hiện</button><p className="hint">Xác nhận đã đọc không khôi phục pin/ngăn. Phục hồi pin tại mục Pin và BMS.</p></form>}
    </article>)}
  </section>;
}
