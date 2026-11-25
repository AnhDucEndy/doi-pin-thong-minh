import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {login,recovery,refresh,mutation,safeHttp,flushHttp,runtime} from './support';

function state(){return JSON.parse(fs.readFileSync(path.join(runtime,'state.json'),'utf8'));}
test('legacy 0.1 Browser old-pin handover and settlement',async({browser},info)=>{
  const contexts=await Promise.all([browser.newContext(),browser.newContext()]);
  const [t,c]=await Promise.all(contexts.map(ctx=>ctx.newPage()));const events:any[]=[];
  safeHttp(t,events);safeHttp(c,events);
  try {
    await Promise.all([login(t,'technician'),login(c,'customer')]);
    await Promise.all([recovery(t),recovery(c)]);
    await t.getByLabel('Ghi chú',{exact:true}).fill('Browser actual old-pin handover, legacy contract');
    await t.getByRole('combobox').selectOption('RETURN_OLD_TO_CUSTOMER');
    const begun=await mutation(t,'Tạo operation',200);const op=(await begun.json()).active_operation;
    expect(op.protocol_version).toBeNull();expect(op.purpose).toBe('RETURN_OLD_TO_CUSTOMER');
    const root=path.resolve('../..');
    const request=execFileSync(path.join(root,'.venv/Scripts/python.exe'),[
      path.join(root,'tools/phase8a_manual_operator.py'),'--request',runtime,'--action','HANDOVER','--operation',op.id],
      {encoding:'utf8',windowsHide:true}).trim();
    const result=request.replace(/\.json$/,'.result.json');
    await expect.poll(()=>fs.existsSync(result),{timeout:20_000,intervals:[100]}).toBe(true);
    expect(JSON.parse(fs.readFileSync(result,'utf8'))).toEqual({completed:true,service_state:'OBSERVED'});
    await expect.poll(()=>state().active_operation?.attestations.some((p:any)=>p.source_kind==='SIMULATOR'),
      {timeout:15_000,intervals:[100]}).toBe(true);
    const proof=state().active_operation.attestations.find((p:any)=>p.source_kind==='SIMULATOR');
    expect(proof.payload.result).toBe('OBSERVED');expect(proof.payload.actual_serial).toBe(op.expected_serial);
    await Promise.all([refresh(t),refresh(c)]);
    await t.getByLabel('Serial thực tế Technician đã kiểm tra').fill(proof.payload.actual_serial);
    await mutation(t,'Technician CONFIRM — Đối soát 0.1',200);
    const current=await refresh(c);const projection=(await current.json()).recovery_confirmation;
    expect(projection.operation_id).toBe(op.id);expect(projection.context_hash).toBe(op.context_hash);
    expect(projection.protocol_version??null).toBeNull();
    await mutation(c,'Customer CONFIRM — Đối soát 0.1',201);
    await refresh(t);
    const settled=await mutation(t,'Yêu cầu Backend settlement',200);const actual=await settled.json();
    expect(actual.old_pin_settled).toBe(true);expect(actual.new_pin_delivered).toBe('NO');
    expect(actual.active_operation.consumed_at).toBeTruthy();
    const requestData=settled.request();
    const replay=await t.evaluate(async d=>{const r=await fetch(d.url,{method:'POST',headers:d.headers,body:d.body});
      return {status:r.status,body:await r.json()};},{url:requestData.url(),headers:requestData.headers(),body:requestData.postData()});
    expect(replay.status).toBe(200);expect(replay.body).toEqual(actual);
    await expect(t.getByText('Operation đã consumed',{exact:true})).toBeVisible();
    await refresh(c);await expect(c.getByRole('button',{name:'Customer CONFIRM — Đối soát 0.1'})).toBeDisabled();
    await t.screenshot({path:info.outputPath('legacy-technician-final.png'),fullPage:true});
    await c.screenshot({path:info.outputPath('legacy-customer-final.png'),fullPage:true});
    fs.writeFileSync(path.join(process.env.PW_OUTPUT_DIR!,'legacy-facts.json'),JSON.stringify({operation_id:op.id,
      context_hash:op.context_hash,simulator_receipt_id:proof.id,settled:actual,replay_identical:true},null,2));
  } finally {
    await flushHttp();fs.writeFileSync(path.join(process.env.PW_OUTPUT_DIR!,'safe-http-legacy.json'),JSON.stringify(events,null,2));
    for(const context of contexts)await context.close().catch(()=>{});
  }
});
