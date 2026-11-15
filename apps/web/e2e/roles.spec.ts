import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {login,recovery,meta,runtime,safeHttp,flushHttp} from './support';

test('Browser Admin read-only and cross-customer denial',async({browser},info)=>{
  const contexts=await Promise.all([browser.newContext(),browser.newContext(),browser.newContext(),browser.newContext()]);
  const [admin,owner,other,outsider]=await Promise.all(contexts.map(c=>c.newPage()));
  const events:any[]=[];
  for(const page of [admin,owner,other,outsider])safeHttp(page,events);
  try {
    const token=await login(admin,'admin');
    await recovery(admin);
    await expect(admin.getByRole('button',{name:'Tạo operation',exact:true})).toHaveCount(0);
    const forbiddenMutation=await admin.evaluate(async data=>{
      const response=await fetch('/v1/swaps/'+data.swap+'/recovery/evidence',{method:'POST',
        headers:{'Content-Type':'application/json',Authorization:'Bearer '+data.token,'Idempotency-Key':crypto.randomUUID()},
        body:JSON.stringify({expected_version:1,note:'Forbidden Admin action must have no effect',
          statement:{kind:'BEGIN_OPERATION',purpose:'RETURN_FOREIGN_OBJECT'}})});
      return response.status;
    },{token,swap:meta.swap_id});
    expect(forbiddenMutation).toBe(403); // Supplemental HTTP guard, beyond hidden controls.
    // Approved Admin API only creates an unrelated principal, never physical evidence.
    const password=JSON.parse(fs.readFileSync(path.join(runtime,'private.json'),'utf8')).passwords.customer;
    const created=await admin.evaluate(async data=>{
      const response=await fetch('/v1/users',{method:'POST',headers:{'Content-Type':'application/json',
        Authorization:'Bearer '+data.token,'Idempotency-Key':crypto.randomUUID()},
        body:JSON.stringify({username:'browser-other',password:data.password,role:'CUSTOMER'})});
      return response.status;
    },{token,password});
    expect(created).toBe(201);
    const technicianPassword=JSON.parse(fs.readFileSync(path.join(runtime,'private.json'),'utf8')).passwords.technician;
    const technicianCreated=await admin.evaluate(async data=>{
      const response=await fetch('/v1/users',{method:'POST',headers:{'Content-Type':'application/json',
        Authorization:'Bearer '+data.token,'Idempotency-Key':crypto.randomUUID()},
        body:JSON.stringify({username:'browser-outsider',password:data.password,role:'TECHNICIAN'})});
      return response.status;
    },{token,password:technicianPassword});
    expect(technicianCreated).toBe(201);
    await Promise.all([login(owner,'customer'),login(other,'customer','browser-other')]);
    await recovery(owner);
    await other.getByRole('button',{name:'Recovery',exact:true}).click();
    await other.getByLabel('ID phiên',{exact:true}).fill(meta.swap_id);
    const denied=other.waitForResponse(r=>r.url().includes('/v1/swaps/')&&r.request().method()==='GET');
    await other.getByRole('button',{name:'Tra cứu trạng thái Backend'}).click();
    // Baseline getSwap hides another Customer's resource with 404 (not 403).
    expect((await denied).status()).toBe(404);
    await expect(other.getByRole('alert')).toBeVisible();
    await expect(other.getByText('Context hash:',{exact:false})).toHaveCount(0);
    await expect(owner.getByRole('button',{name:'Tạo operation',exact:true})).toHaveCount(0);
    await login(outsider,'technician','browser-outsider');
    await outsider.getByRole('button',{name:'Recovery',exact:true}).click();
    await outsider.getByLabel('ID phiên',{exact:true}).fill(meta.swap_id);
    const stationDenied=outsider.waitForResponse(r=>r.url().includes('/recovery')&&r.request().method()==='GET');
    await outsider.getByRole('button',{name:'Tra cứu trạng thái Backend'}).click();
    expect((await stationDenied).status()).toBe(403);
    await expect(outsider.getByRole('alert')).toBeVisible();
    await expect(outsider.getByRole('button',{name:'Tạo operation',exact:true})).toHaveCount(0);
    await admin.screenshot({path:info.outputPath('admin-readonly.png'),fullPage:true});
    await other.screenshot({path:info.outputPath('cross-customer-denied.png'),fullPage:true});
    const logout=admin.waitForResponse(r=>r.url().endsWith('/v1/auth/logout'));
    await admin.getByRole('button',{name:'Đăng xuất',exact:true}).click();
    expect((await logout).status()).toBe(200);
    await login(admin,'customer');
    await recovery(admin);
    await expect(admin.getByText('Admin chỉ xem hồ sơ; xác nhận và đối soát thuộc Technician/Customer đúng thẩm quyền.')).toHaveCount(0);
    await expect(admin.getByRole('button',{name:'Tạo operation',exact:true})).toHaveCount(0);
  } finally {
    await flushHttp();
    fs.writeFileSync(path.join(process.env.PW_OUTPUT_DIR!,'safe-http-roles.json'),JSON.stringify({events},null,2));
    for(const context of contexts)await context.close().catch(()=>{});
  }
});
