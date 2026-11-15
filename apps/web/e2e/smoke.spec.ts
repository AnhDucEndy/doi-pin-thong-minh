import { test,expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { login,recovery,meta,safeHttp,flushHttp } from './support';
test('real Browser smoke, isolated roles, projection, logout and responsive',async({browser},info)=>{
  const events:any[]=[];
  const tech=await browser.newContext({viewport:{width:1365,height:900}});
  const customer=await browser.newContext({viewport:{width:390,height:844}});
  try {
    const t=await tech.newPage();const c=await customer.newPage();
    safeHttp(t,events);safeHttp(c,events);
    await login(t,'technician');await login(c,'customer');
    await recovery(t);await recovery(c);
    await expect(t.getByText('Trạng thái Backend:',{exact:false})).toBeVisible();
    await expect(c.getByText('Trạng thái Backend:',{exact:false})).toBeVisible();
    await expect(t.getByRole('button',{name:'Tạo operation',exact:true})).toBeVisible();
    await expect(c.getByRole('button',{name:'Tạo operation',exact:true})).toHaveCount(0);
    expect(await c.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await t.screenshot({path:info.outputPath('technician-desktop.png'),fullPage:true});
    await c.screenshot({path:info.outputPath('customer-mobile.png'),fullPage:true});
    const logout=t.waitForResponse(r=>r.url().endsWith('/v1/auth/logout'));
    await t.getByRole('button',{name:'Đăng xuất',exact:true}).click();
    expect((await logout).status()).toBe(200);
    await expect(t.getByRole('button',{name:'Đăng nhập →'})).toBeVisible();
    await expect(c.getByRole('button',{name:'Làm mới trước thao tác'})).toBeVisible();
  } finally {
    await flushHttp();
    fs.writeFileSync(path.join(process.env.PW_OUTPUT_DIR!,'safe-http-smoke.json'),JSON.stringify({fixture:meta.swap_id,events},null,2));
    await tech.close();await customer.close();
  }
});
