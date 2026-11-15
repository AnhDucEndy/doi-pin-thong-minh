import { expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
export const runtime=process.env.PW_RUNTIME!;
export const meta=JSON.parse(fs.readFileSync(path.join(runtime,'manual.json'),'utf8'));
const credentials=JSON.parse(fs.readFileSync(path.join(runtime,'private.json'),'utf8')).passwords;
const pendingResponses=new Set<Promise<void>>();
export async function login(page:Page,role:string,username=role) {
  await page.goto(meta.frontend);
  await page.getByLabel('Tên tài khoản').fill(username);
  await page.getByLabel('Mật khẩu',{exact:true}).fill(credentials[role]);
  const response=page.waitForResponse(r=>r.url().endsWith('/v1/auth/login')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Đăng nhập →'}).click();
  const status=(await response).status();
  expect(status,'Login must succeed once; never brute force').toBe(200);
  await expect(page.getByRole('button',{name:'Recovery',exact:true})).toBeVisible();
  return (await (await response).json()).access_token as string;
}
export async function recovery(page:Page) {
  await page.getByRole('button',{name:'Recovery',exact:true}).click();
  await page.getByLabel('ID phiên',{exact:true}).fill(meta.swap_id);
  await page.getByRole('button',{name:'Tra cứu trạng thái Backend'}).click();
  await expect(page.getByRole('button',{name:'Làm mới trước thao tác'})).toBeVisible();
}
export async function refresh(page:Page) {
  const response=page.waitForResponse(r=>r.request().method()==='GET'&&r.url().includes('/v1/swaps/'));
  await page.getByRole('button',{name:'Làm mới trước thao tác'}).click();
  await response;
  await expect(page.getByRole('status')).toHaveCount(0);
  return await response;
}
export function safeHttp(page:Page,events:any[]) {
  page.on('response',response=>{
    const url=new URL(response.url());
    if(!url.pathname.startsWith('/v1/'))return;
    const entry={at:new Date().toISOString(),method:response.request().method(),path:url.pathname,status:response.status(),code:undefined as string|undefined};
    events.push(entry);
    const work=(async()=>{
      if(response.status()>=400) {try {entry.code=(await response.json()).code;} catch {}}
    })();
    pendingResponses.add(work);
    void work.finally(()=>pendingResponses.delete(work));
  });
}
export async function flushHttp() {await Promise.all([...pendingResponses]);}
export async function mutation(page:Page,button:string,status:number) {
  const pending=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes('/recovery/'),{timeout:15_000});
  await page.getByRole('button',{name:button}).click();
  const response=await pending;
  expect(response.status()).toBe(status);
  await expect(page.getByRole('button',{name:'Làm mới trước thao tác'})).toBeEnabled();
  return response;
}
