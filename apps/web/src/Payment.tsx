import { useEffect, useRef, useState } from 'react';

type Api=(path:string,method?:string,data?:unknown,key?:string)=>Promise<any>;

export function Payment({api,role,swap}:{api:Api;role:string;swap:any}) {
  const [payment,setPayment]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const intent=useRef<{key:string;body:unknown}|null>(null);
  useEffect(()=>{if(!swap.consented_at)return;let stopped=false;let timer:number;
    async function poll(){try{const p=await api(`/v1/swaps/${swap.id}/payment`);if(!stopped){setPayment(p);setError('');}}
      catch(e){if(!stopped)setError((e as Error).message);}if(!stopped)timer=window.setTimeout(poll,3000);}
    void poll();return()=>{stopped=true;clearTimeout(timer);};
  },[api,swap.id,swap.consented_at]);
  async function pay(){if(busy)return;setBusy(true);setError('');
    if(!intent.current)intent.current={key:crypto.randomUUID(),body:{expected_version:swap.version,quoted_amount_minor:swap.amount_minor,currency:swap.currency,accept:true}};
    try{await api(`/v1/swaps/${swap.id}/consent`,'POST',intent.current.body,intent.current.key);
      setPayment(await api(`/v1/swaps/${swap.id}/payment`));}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function reconcile(){setBusy(true);setError('');try{setPayment(await api(`/v1/payments/${payment.id}/reconcile`,'POST',
      {expected_version:payment.version,reason:'Admin yêu cầu query cùng intent mô phỏng'},crypto.randomUUID()));}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <section aria-label="Thanh toán mô phỏng"><h4>Thanh toán mô phỏng · không dùng tiền thật</h4>
    <p>Phí do Backend chốt: {swap.amount_minor?.toLocaleString('vi-VN')??'Chưa có quote'} {swap.currency}</p>
    {error&&<p role="alert">{error}</p>}{busy&&<p role="status">Đang gửi yêu cầu…</p>}
    {role==='CUSTOMER'&&swap.state==='RESERVED'&&<button disabled={busy} onClick={()=>void pay()}>
      {intent.current?'Gửi lại xác nhận với cùng mã yêu cầu':'Đồng ý phí và thanh toán mô phỏng'}</button>}
    {swap.consented_at&&!payment&&!error&&<p role="status">Đang tải khoản thu…</p>}
    {payment&&<><p>Payment: {payment.id} · {payment.state}</p><p>Receipt: {payment.provider_reference??'Chưa có kết quả xác minh'}</p>
      {['CREATED','PENDING'].includes(payment.state)&&<p>Đang chờ mock provider. Không tạo khoản thu khác.</p>}
      {payment.state==='UNKNOWN'&&<p>Chưa rõ kết quả. Giữ tài nguyên, chờ Admin đối soát cùng khoản thu.</p>}
      {payment.state==='FAILED'&&<p>Thanh toán bị từ chối. Backend quyết định trạng thái phiên và việc giải phóng tài nguyên.</p>}
      {payment.state==='SUCCEEDED'&&<p>Đã xác minh thu phí. Chưa mở cửa, bàn giao pin hoặc hoàn tất đổi pin.</p>}
      {role==='ADMIN'&&['PENDING','UNKNOWN'].includes(payment.state)&&<button disabled={busy} onClick={()=>void reconcile()}>Đối soát cùng khoản thu</button>}</>}
    {swap.state==='CANCELLED'&&!payment&&<p>Phiên đã kết thúc; không được tạo khoản thu mới.</p>}
  </section>;
}
