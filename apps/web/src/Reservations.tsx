import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import QRCode from 'qrcode';
import { Payment } from './Payment';

type Api = (path:string, method?:string, data?:unknown, key?:string)=>Promise<any>;
const closed = ['CANCELLED','COMPLETED','CLOSED_COMPENSATED'];

export function Reservations({api,role}:{api:Api;role:string}) {
  const [stations,setStations]=useState<any[]>([]),[swaps,setSwaps]=useState<any[]>([]),[users,setUsers]=useState<any[]>([]);
  const [qr,setQr]=useState<any>(null),[image,setImage]=useState(''),[now,setNow]=useState(Date.now());
  const [credentials,setCredentials]=useState<any[]>([]),[error,setError]=useState(''),[message,setMessage]=useState('');
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
  const load=useCallback(async()=>{
    async function all(path:string){let cursor:string|null=null;const items:any[]=[];do{const page=await api(path+'?limit=100'+(cursor?'&cursor='+cursor:''));items.push(...page.items);cursor=page.next_cursor;}while(cursor);return items;}
    const [s,t]=await Promise.all([all('/v1/stations'),all('/v1/swaps')]);setStations(s);setSwaps(t);
    if(t.some(x=>!closed.includes(x.state)))setQr(null);
    if(role==='ADMIN')setUsers((await all('/v1/users')).filter(x=>x.role==='CUSTOMER'&&x.state==='ACTIVE'));
  },[api,role]);
  useEffect(()=>{let cancelled=false;let timer:number;async function poll(){try{await load();if(!cancelled){setLoading(false);setError('');}}catch(e){if(!cancelled){setError((e as Error).message);setLoading(false);}}if(!cancelled)timer=window.setTimeout(poll,3000);}void poll();return()=>{cancelled=true;clearTimeout(timer);};},[load]);
  useEffect(()=>{const timer=window.setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(timer);},[]);
  useEffect(()=>{let cancelled=false;setImage('');if(qr)void QRCode.toDataURL(qr.qr_token,{width:240,margin:2}).then(value=>{if(!cancelled)setImage(value);}).catch(()=>setError('Không tạo được hình QR.'));return()=>{cancelled=true;};},[qr]);
  async function execute(task:()=>Promise<void>){setBusy(true);setError('');setMessage('');try{await task();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function createQr(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=new FormData(e.currentTarget);await execute(async()=>{const response=await api('/v1/qr-challenges','POST',{station_id:form.get('station')},crypto.randomUUID());setNow(Date.now());setQr(response);setMessage('QR một lần đã cấp. Xác thực bằng bộ đọc mô phỏng của đúng trạm.');});}
  async function change(swap:any,action:'reserve'|'cancel'){await execute(async()=>{const result=await api(`/v1/swaps/${swap.id}/${action}`,'POST',{expected_version:swap.version,...(action==='cancel'?{reason:'Khách hủy trước thanh toán'}:{})},crypto.randomUUID());setMessage(result.state==='RESERVED'?'Đã giữ pin và hai ngăn. Chưa thanh toán hoặc giao nhận pin.':`Trạng thái: ${result.state}. ${result.review_reason??''}`);await load();});}
  async function createRfid(e:FormEvent<HTMLFormElement>){e.preventDefault();const element=e.currentTarget,form=new FormData(element);await execute(async()=>{const result=await api(`/v1/users/${form.get('user')}/credentials`,'POST',{rfid_value:form.get('rfid')},crypto.randomUUID());setCredentials(old=>[result,...old]);element.reset();setMessage('Đã liên kết RFID mô phỏng. Giá trị thẻ không được trả lại hoặc lưu trong danh sách này.');});}
  async function revoke(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=new FormData(e.currentTarget);await execute(async()=>{const result=await api(`/v1/credentials/${form.get('credential')}/revoke`,'POST',undefined,crypto.randomUUID());setCredentials(old=>[result,...old.filter(x=>x.id!==result.id)]);setMessage('Đã thu hồi RFID.');});}
  const qrExpired=qr&&Date.parse(qr.expires_at)<=now;
  return <section className="station-module"><h2>QR/RFID và giữ tài nguyên</h2>
    <p className="hint">Mô phỏng tại trạm. Xác thực và giữ tài nguyên không phải bằng chứng mở cửa, thanh toán hay bàn giao pin.</p>
    {loading&&<p role="status">Đang tải phiên…</p>}{error&&<p role="alert" className="message error">{error}</p>}{message&&<p role="status" className="message">{message}</p>}
    {role==='CUSTOMER'&&<section className="card"><h3>QR xác thực một lần</h3><form onSubmit={createQr}><label>Trạm xác thực<select name="station" required>{stations.map(s=><option key={s.station_id} value={s.station_id}>{s.name} · {s.operational_state}</option>)}</select></label><button disabled={busy||loading||swaps.some(s=>!closed.includes(s.state))}>Cấp QR một lần</button></form>
      {qr&&!qrExpired&&<><p>Hiệu lực còn {Math.max(0,Math.ceil((Date.parse(qr.expires_at)-now)/1000))} giây; Backend xác nhận hiệu lực khi quét.</p>{image&&<img src={image} width="240" height="240" alt="QR xác thực một lần"/>}<button onClick={()=>void execute(async()=>{await navigator.clipboard.writeText(qr.qr_token);setMessage('Đã sao chép mã cho bộ đọc mô phỏng local. Không chia sẻ mã.');})}>Sao chép mã cho bộ đọc mô phỏng</button></>}
      {qrExpired&&<p role="status">QR đã hết hạn. Cấp QR mới để tiếp tục.</p>}<p className="hint">QR và token chỉ trong bộ nhớ tab. Device-Key thuộc adapter thiết bị, không nhập vào Frontend.</p></section>}
    {role==='ADMIN'&&<section className="card"><h3>Liên kết RFID mô phỏng</h3><form onSubmit={createRfid}><label>Khách hàng<select name="user" required>{users.map(u=><option key={u.id} value={u.id}>{u.username}</option>)}</select></label><label>Giá trị RFID mô phỏng<input name="rfid" type="password" required minLength={1} maxLength={200} autoComplete="off"/></label><button disabled={busy||!users.length}>Liên kết RFID</button></form><form onSubmit={revoke}><label>ID credential cần thu hồi<input name="credential" required/></label><button disabled={busy}>Thu hồi RFID</button></form>{credentials.map(c=><p key={c.id}>Credential {c.id} · {c.revoked?'Đã thu hồi':'Còn hiệu lực'}</p>)}<p className="hint">RFID có thể dùng lại sau khi phiên trước đã kết thúc. Đọc lặp không tự giữ thêm tài nguyên.</p></section>}
    <h3>Phiên xác thực và reservation</h3>{!loading&&!swaps.length&&<p>Chưa có phiên trong phạm vi truy cập.</p>}
    {swaps.map(s=><article key={s.id} className="card"><h3>{s.state} · {s.verified_via}</h3><p>Phiên: {s.id}</p><p>Trạm: {stations.find(t=>t.station_id===s.station_id)?.name??s.station_id}</p><p>Phiên bản: {s.version} · Phí: {s.amount_minor??'Chưa chốt'} {s.currency}</p>
      {s.reservation_expires_at&&<p>Hạn giữ: {new Date(s.reservation_expires_at).toLocaleString('vi-VN')}. {s.state==='RESERVED'&&Date.parse(s.reservation_expires_at)<=now?'Đã đến hạn, chờ Backend xác nhận kết thúc.':''}</p>}
      {s.review_reason&&<p>{s.review_reason}</p>}{s.new_battery_id&&<p>Pin cấp: {s.new_battery_id} · Ngăn nhận: {s.return_compartment_id} · Ngăn cấp: {s.supply_compartment_id}</p>}
      {role==='CUSTOMER'&&s.state==='VERIFIED'&&<button disabled={busy} onClick={()=>void change(s,'reserve')}>Giữ pin và hai ngăn</button>}
      {role==='CUSTOMER'&&['VERIFIED','RESERVED'].includes(s.state)&&<button disabled={busy} onClick={()=>void change(s,'cancel')}>Hủy trước thanh toán</button>}
      {(s.state==='RESERVED'||s.consented_at)&&<Payment api={api} role={role} swap={s}/>}
    </article>)}
  </section>;
}
