import { test,expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {login,recovery,refresh,mutation,safeHttp,flushHttp,runtime} from './support';
const scenario=process.env.PW_SCENARIO ?? 'post';
const root=path.resolve('../..');
function state() {return JSON.parse(fs.readFileSync(path.join(runtime,'state.json'),'utf8'));}
async function operator(action:string,id:string) {
  const output=execFileSync(path.join(root,'.venv/Scripts/python.exe'),[
    path.join(root,'tools/phase8a_manual_operator.py'),'--request',runtime,'--action',action,'--operation',id],
    {encoding:'utf8',windowsHide:true}).trim();
  const result=output.replace(/\.json$/,'.result.json');
  await expect.poll(()=>fs.existsSync(result),{timeout:20_000,intervals:[100]}).toBe(true);
  const outcome=JSON.parse(fs.readFileSync(result,'utf8'));
  expect(outcome.completed,action).toBe(true);
  return outcome;
}
test(`staged Browser ${scenario}`,async({browser},info)=>{
  const events:any[]=[];const contexts=await Promise.all([browser.newContext(),browser.newContext()]);
  const [t,c]=await Promise.all(contexts.map(ctx=>ctx.newPage()));
  safeHttp(t,events);safeHttp(c,events);
  try {
    const [,customerToken]=await Promise.all([login(t,'technician'),login(c,'customer')]);
    await Promise.all([recovery(t),recovery(c)]);
    await t.getByLabel('Ghi chú',{exact:true}).fill('Browser verified simulated foreign object');
    await t.getByRole('combobox').selectOption('RETURN_FOREIGN_OBJECT');
    const begin=await mutation(t,'Tạo operation',200);
    let op=(await begin.json()).active_operation;
    await operator('INSPECT',op.id);
    await expect.poll(()=>state().active_operation?.attestations.some((p:any)=>p.stage==='PRE_ACTION_INSPECTION'),
      {timeout:12_000,intervals:[100]}).toBe(true);
    const [,customerRead]=await Promise.all([refresh(t),refresh(c)]);
    const projection=(await customerRead.json()).recovery_confirmation;
    const accepted=state().active_operation.attestations.find((p:any)=>p.stage==='PRE_ACTION_INSPECTION'&&p.source_kind==='SIMULATOR');
    expect(projection.protocol_version).toBe('0.2');
    expect(projection.receipt_id).toBe(accepted.id);
    expect(projection.receipt_hash).toBe(accepted.payload_hash);
    for(const internal of ['attestations','authorization','ledger'])expect(projection).not.toHaveProperty(internal);
    await expect(c.locator('input')).toHaveCount(1); // Only the swap lookup is editable.
    await expect(c.locator('select')).toHaveCount(0);
    await expect(c.getByText(/Stage: PRE_ACTION_INSPECTION/)).toBeVisible();
    await t.getByLabel('Serial thực tế Technician đã kiểm tra').fill('SIMULATED-WRONG-BATTERY');
    if(scenario==='old-boot') {
      const before=state();
      const reboot=await operator('REBOOT',op.id);
      expect(reboot.new_boot).not.toBe(reboot.old_boot);
      expect(accepted.source_boot).toBe(reboot.old_boot);
      await expect.poll(async()=>{
        await refresh(c);
        return c.getByText('Trạng thái xác nhận: UNAVAILABLE',{exact:true}).isVisible();
      },{timeout:12_000,intervals:[100,300]}).toBe(true);
      expect(Date.now()-Date.parse(accepted.observed_at)).toBeLessThan(15_000);
      await expect(c.getByRole('button',{name:'Customer CONFIRM — PRE_ACTION_INSPECTION'})).toBeDisabled();
      await refresh(t);
      await mutation(t,'Technician CONFIRM — PRE_ACTION_INSPECTION',409);
      await expect(t.getByRole('alert')).toContainText('RECONCILIATION_REQUIRED');
      expect(state().version).toBe(before.version);
      expect(state().active_operation.attestations).toEqual(before.active_operation.attestations);
      await t.screenshot({path:info.outputPath('old-boot-refused.png'),fullPage:true});
      return;
    }
    if(scenario==='stale-expired') {
      const proof=state().active_operation.attestations.find((p:any)=>p.source_kind==='SIMULATOR');
      await expect.poll(()=>Date.now()-Date.parse(proof.observed_at)>15_000,
        {timeout:20_000,intervals:[100]}).toBe(true);
      await refresh(c);
      await expect(c.getByText('Trạng thái xác nhận: UNAVAILABLE',{exact:true})).toBeVisible();
      await expect(c.getByRole('button',{name:'Customer CONFIRM — PRE_ACTION_INSPECTION'})).toBeDisabled();
      await expect.poll(()=>Date.now()>=Date.parse(op.expires_at),{timeout:135_000,intervals:[500]}).toBe(true);
      await Promise.all([refresh(c),refresh(t)]);
      await expect(c.getByText('Trạng thái xác nhận: EXPIRED',{exact:true})).toBeVisible();
      await expect(t.getByRole('button',{name:'Yêu cầu authorization intent'})).toBeDisabled();
      await c.screenshot({path:info.outputPath('stale-expired.png'),fullPage:true});
      return;
    }
    if(['reference','wrong-stage','version','response-loss','duplicate','revoked'].includes(scenario)) {
      if(scenario==='reference'||scenario==='wrong-stage') {
        await c.route('**/recovery/confirmations',async route=>{
          const body=route.request().postDataJSON();
          if(scenario==='reference')body.receipt_hash='0'.repeat(64);
          else body.stage='POST_ACTION_RECEIPT';
          await route.continue({postData:JSON.stringify(body)});
        });
        await mutation(c,'Customer CONFIRM — PRE_ACTION_INSPECTION',409);
        await expect(c.getByRole('alert')).toContainText('RECOVERY_STAGE_CONFLICT');
      } else if(scenario==='version') {
        let requests=0;
        await t.route('**/recovery/evidence',async route=>{
          requests++;const body=route.request().postDataJSON();body.expected_version++;
          await route.continue({postData:JSON.stringify(body)});
        });
        await mutation(t,'Technician CONFIRM — PRE_ACTION_INSPECTION',409);
        await expect(t.getByRole('alert')).toContainText('VERSION_CONFLICT');
        expect(requests).toBe(1);
      } else if(scenario==='revoked') {
        const response=await c.request.post(metaBackend()+'/v1/auth/logout',
          {headers:{Authorization:'Bearer '+customerToken,'Idempotency-Key':crypto.randomUUID()}});
        expect(response.status()).toBe(200);
        // RecoveryClient re-reads ownership/session before POST. A revoked session
        // must fail at that GET without sending a confirmation at all.
        const pending=c.waitForResponse(r=>r.request().method()==='GET'&&r.url().includes('/v1/swaps/')&&r.status()===401);
        await c.getByRole('button',{name:'Customer CONFIRM — PRE_ACTION_INSPECTION'}).click();
        expect((await pending).status()).toBe(401);
        await expect(c.getByRole('button',{name:'Đăng nhập →'})).toBeVisible();
        expect(events.filter(e=>e.method==='POST'&&e.path.endsWith('/confirmations'))).toHaveLength(0);
      } else {
        let requests=0;
        c.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/recovery/confirmations'))requests++;});
        if(scenario==='response-loss') {
          await c.route('**/recovery/confirmations',async route=>{
            await route.fetch();await route.abort('failed');
          });
          await c.getByRole('button',{name:'Customer CONFIRM — PRE_ACTION_INSPECTION'}).click();
          await expect(c.getByRole('alert')).toBeVisible();
        } else {
          await c.getByRole('button',{name:'Customer CONFIRM — PRE_ACTION_INSPECTION'}).click({clickCount:2});
        }
        await expect.poll(()=>state().active_operation.attestations.filter((p:any)=>p.source_kind==='CUSTOMER').length).toBe(1);
        expect(requests).toBe(1);
      }
      await t.screenshot({path:info.outputPath('negative-technician.png'),fullPage:true});
      return;
    }
    await mutation(t,'Technician CONFIRM — PRE_ACTION_INSPECTION',200);
    await refresh(c); // The Technician proof changes the immutable displayed snapshot.
    await mutation(c,scenario==='pre-reject'?'Customer REJECT — PRE_ACTION_INSPECTION':'Customer CONFIRM — PRE_ACTION_INSPECTION',201);
    if(scenario==='pre-reject') {
      await refresh(t);
      await expect(t.getByText('Có REJECT. Giữ review và không tự thực hiện lại.')).toBeVisible();
      await expect(t.getByRole('button',{name:'Yêu cầu authorization intent'})).toBeDisabled();
      return;
    }
    await refresh(t);
    await mutation(t,'Yêu cầu authorization intent',200);
    await operator('ACK',op.id);
    await refresh(t);
    if(scenario==='closure') {
      await expect.poll(()=>Date.now()>=Date.parse(op.expires_at),{timeout:135_000,intervals:[500]}).toBe(true);
      await refresh(t);
      await mutation(t,'Yêu cầu đối soát no-effect closure',200);
      await operator('CLOSE',op.id);
      await operator('ACK_CLOSURE',op.id);
      await refresh(t);
      await expect(t.getByText('Operation đã đóng',{exact:true})).toBeVisible();
      return;
    }
    await mutation(t,'Chủ động yêu cầu activation',200);
    await operator('HANDOVER',op.id);
    await expect.poll(()=>state().active_operation.attestations.some((p:any)=>p.stage==='POST_ACTION_RECEIPT'),
      {timeout:15_000,intervals:[100]}).toBe(true);
    await Promise.all([refresh(t),refresh(c)]);
    await expect(c.getByText(/Stage: POST_ACTION_RECEIPT/)).toBeVisible();
    if(scenario==='successor') {
      // Neither original receipt timestamps nor deadlines are edited.
      await expect.poll(()=>Date.now()>=Date.parse(op.expires_at),{timeout:135_000,intervals:[500]}).toBe(true);
      await refresh(t);
      const response=await mutation(t,'Yêu cầu successor inspection chỉ đọc',200);
      op=(await response.json()).active_operation;
      await operator('REINSPECT',op.id);
      await Promise.all([refresh(t),refresh(c)]);
      await expect(c.getByText(/Stage: RECONCILIATION_INSPECTION/)).toBeVisible();
    }
    const stage=scenario==='successor'?'RECONCILIATION_INSPECTION':'POST_ACTION_RECEIPT';
    await t.getByLabel('Serial thực tế Technician đã kiểm tra').fill('SIMULATED-WRONG-BATTERY');
    await mutation(t,`Technician CONFIRM — ${stage}`,200);
    await refresh(c);
    await mutation(c,`Customer ${scenario==='post-reject'?'REJECT':'CONFIRM'} — ${stage}`,201);
    await refresh(t);
    if(scenario==='post-reject') {
      await expect(t.getByRole('button',{name:'Yêu cầu Backend settlement'})).toBeDisabled();
    } else {
      const response=await mutation(t,'Yêu cầu Backend settlement',200);
      const original=await response.json();
      const request=response.request();
      const replay=await t.evaluate(async data=>{
        const result=await fetch(data.url,{method:'POST',headers:data.headers,body:data.body});
        return {status:result.status,result:await result.json()};
      },{url:request.url(),headers:request.headers(),body:request.postData()});
      expect(replay.status).toBe(200);expect(replay.result).toEqual(original);
      await expect(t.getByText('Operation đã consumed',{exact:true})).toBeVisible();
      await refresh(c);
      await expect(c.getByText('Trạng thái xác nhận: CONSUMED',{exact:true})).toBeVisible();
      await expect(c.getByRole('button',{name:`Customer CONFIRM — ${stage}`})).toBeDisabled();
      if(scenario==='terminal-label') {
        await c.screenshot({path:info.outputPath('consumed-label.png'),fullPage:true});
        await expect(c.getByText('EXPIRED — tiếp tục review; chưa chứng minh no-effect',{exact:true})).toHaveCount(0);
      }
    }
    await t.screenshot({path:info.outputPath('technician-final.png'),fullPage:true});
    await c.screenshot({path:info.outputPath('customer-final.png'),fullPage:true});
  } finally {
    await flushHttp();
    fs.writeFileSync(path.join(process.env.PW_OUTPUT_DIR!,'safe-http-staged.json'),JSON.stringify({scenario,events},null,2));
    for(const context of contexts)await context.close().catch(()=>{});
  }
});
function metaBackend() {return JSON.parse(fs.readFileSync(path.join(runtime,'manual.json'),'utf8')).backend;}
