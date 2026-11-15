import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const root = path.resolve(import.meta.dirname, '..');
const output = path.join(root, '.cache', 'recovery-test-' + Date.now());
await fs.mkdir(output, { recursive: true });
for (const name of ['recoveryModel', 'Recovery']) {
  const source = await fs.readFile(path.join(root, 'src', name + (name === 'Recovery' ? '.tsx' : '.ts')), 'utf8');
  const result = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  await fs.writeFile(path.join(output, name + '.mjs'), result.replaceAll("'./recoveryModel'", "'./recoveryModel.mjs'"));
}
const model = await import(pathToFileURL(path.join(output, 'recoveryModel.mjs')));
const { RecoveryDetails } = await import(pathToFileURL(path.join(output, 'Recovery.mjs')));
const { requestFor, RecoveryClient, stageOf } = model;
const hash = 'a'.repeat(64);
function fixture(stage = 'PRE_ACTION_INSPECTION') {
  const op = { id: 'op', context_hash: hash, protocol_version: '0.2', purpose: 'RETURN_FOREIGN_OBJECT',
    customer_id: 'principal', station_id: 'S01', expected_serial: 'FOREIGN',
    expires_at: new Date(Date.now() + 120000).toISOString(), attestations: [], context: {} };
  if (stage === 'RECONCILIATION_INSPECTION') op.context.reconciliation_only = true;
  for (const source of ['SIMULATOR', 'TECHNICIAN', 'CUSTOMER']) op.attestations.push({
    id: source, operation_id: 'op', stage, source_kind: source, payload_hash: hash,
    observed_at: new Date().toISOString(), received_at: new Date().toISOString(),
    payload: { context_hash: hash, actual_serial: 'FOREIGN', result: 'OBSERVED', confirm: source === 'SIMULATOR' ? undefined : true },
  });
  return { version: 3, state: 'REVIEW_REQUIRED', old_pin_settled: false, new_pin_delivered: 'UNKNOWN', active_operation: op };
}
function request(record, action, role = 'TECHNICIAN') {
  return requestFor(record, role, action, 'Inspected', 'FOREIGN');
}
for (const stage of ['PRE_ACTION_INSPECTION','POST_ACTION_RECEIPT','RECONCILIATION_INSPECTION']) {
  test('render and exact reference at ' + stage, () => {
    const record = fixture(stage);
    const html = renderToStaticMarkup(React.createElement(RecoveryDetails, { record, role: 'TECHNICIAN' }));
    assert.match(html, new RegExp(stage)); assert.match(html, /SIMULATOR/); assert.match(html, /REVIEW_REQUIRED/);
    assert.match(html, /UNKNOWN/); assert.match(html, /Chưa giải quyết/);
    for (const action of ['CONFIRM','REJECT']) {
      const statement = request(record, action).body.statement;
      assert.equal(statement.stage, stage); assert.equal(statement.receipt_id, 'SIMULATOR');
      assert.equal(statement.receipt_hash, hash); assert.equal(statement.observation, action);
      assert.equal(statement.operation_id, 'op');
    }
  });
}
test('stage chooses post receipt over PRE, never PRE human testimony', () => {
  const record = fixture();
  record.active_operation.attestations.push(fixture('POST_ACTION_RECEIPT').active_operation.attestations[0]);
  assert.equal(stageOf(record.active_operation), 'POST_ACTION_RECEIPT');
  assert.throws(() => request(record, 'SETTLE'), /ba nguồn/);
});
for (const fault of ['missing', 'wrong-operation', 'wrong-context']) {
  test('refuses receipt ' + fault, () => {
    const record = fixture();
    if (fault === 'missing') record.active_operation.attestations = [];
    if (fault === 'wrong-operation') record.active_operation.attestations[0].operation_id = 'other';
    if (fault === 'wrong-context') record.active_operation.attestations[0].payload.context_hash = 'b'.repeat(64);
    assert.throws(() => request(record, 'CONFIRM'), /Thiếu receipt/);
  });
}
test('Admin cannot write or inherit Technician permission', () => {
  for (const action of ['CONFIRM','REJECT','BEGIN','SETTLE','INTENT','ACTIVATE','REINSPECT','CLOSE_NO_EFFECT'])
    assert.throws(() => request(fixture(), action, 'ADMIN'), /FORBIDDEN/);
});
test('Customer staged projection blocker is explicit, never downgraded to legacy', () => {
  const record = { state: 'REVIEW_REQUIRED', recovery_confirmation: { ...fixture().active_operation, attestations: undefined, protocol_version: undefined } };
  for (const action of ['CONFIRM','REJECT']) assert.throws(() => request(record, action, 'CUSTOMER'), /chưa cung cấp/);
  assert.throws(() => request(record, 'SETTLE', 'CUSTOMER'), /FORBIDDEN/);
  assert.match(renderToStaticMarkup(React.createElement(RecoveryDetails, { record, role: 'CUSTOMER' })), /chưa trả protocol/);
});
test('Customer legacy confirmations derive identity from Backend context', () => {
  const op = fixture().active_operation; delete op.protocol_version; op.purpose = 'VERIFY_OLD_POSSESSION';
  const record = { state: 'REVIEW_REQUIRED', recovery_confirmation: op };
  assert.deepEqual(request(record, 'REJECT', 'CUSTOMER').body, { operation_id: 'op', context_hash: hash, confirm: false });
});
for (const fault of ['expired','consumed','cancelled','revoked']) {
  test('closed/revoked operation refuses ' + fault, () => {
    const record = fixture('POST_ACTION_RECEIPT'); const op = record.active_operation;
    if (fault === 'expired') op.expires_at = '2000-01-01';
    if (fault === 'consumed') op.consumed_at = new Date().toISOString();
    if (fault === 'cancelled') op.cancelled_at = new Date().toISOString();
    if (fault === 'revoked') op.authorization = { revoked_at: new Date().toISOString() };
    assert.throws(() => request(record, 'SETTLE'));
  });
}
test('INTENT and ACTIVATE bind acknowledged permit, not desired state', () => {
  const record = fixture();
  assert.equal(request(record, 'INTENT').body.statement.phase, 'INTENT');
  assert.throws(() => request(record, 'ACTIVATE'));
  record.active_operation.authorization = { id: 'intent', acknowledgment_id: 'ack', transport_acknowledged: true,
    expires_at: record.active_operation.expires_at };
  assert.deepEqual(request(record, 'ACTIVATE').body.statement, {
    kind: 'AUTHORIZE_ACTION', operation_id: 'op', context_hash: hash, phase: 'ACTIVATE',
    authorization_id: 'intent', acknowledgment_id: 'ack',
  });
  assert.throws(() => request(record, 'INTENT'));
});
test('successor cannot authorize or activate another effect', () => {
  const record = fixture('RECONCILIATION_INSPECTION');
  assert.throws(() => request(record, 'INTENT')); assert.throws(() => request(record, 'ACTIVATE'));
  assert.equal(request(record, 'SETTLE').suffix, 'settle');
});
test('expiry permits only request for ER inspection/no-effect, not automatic closure', () => {
  const record = fixture(); record.active_operation.expires_at = '2000-01-01';
  assert.equal(request(record, 'CLOSE_NO_EFFECT').body.statement.kind, 'CLOSE_NO_EFFECT');
  assert.equal(request(record, 'REINSPECT').body.statement.kind, 'REINSPECT_OPERATION');
  assert.equal(record.state, 'REVIEW_REQUIRED'); assert.equal(record.old_pin_settled, false);
});
test('REJECT cannot settle or authorize', () => {
  const record = fixture(); record.active_operation.attestations[1].payload.confirm = false;
  assert.throws(() => request(record, 'INTENT')); assert.throws(() => request(record, 'SETTLE'));
});
test('mutations never supply custody, holder, Payment, actor role or terminal state', () => {
  const record = fixture('POST_ACTION_RECEIPT');
  for (const action of ['CONFIRM','REJECT','SETTLE','BEGIN']) {
    const body = JSON.stringify(request(record, action).body);
    for (const field of ['custody','holder','payment','actor_id','source_kind','provenance','recipient','state','role'])
      assert.equal(body.includes('"' + field + '"'), false, field);
  }
});
test('refresh/reload reads persisted state without posting', async () => {
  const record = fixture(); const calls = []; let displayed;
  const client = new RecoveryClient(async (...args) => { calls.push(args); return record; }, 'TECHNICIAN', value => { displayed = value; });
  await client.load('swap'); await client.load('swap');
  assert.equal(displayed, record); assert.equal(calls.length, 2); assert.ok(calls.every(c => !c[1]));
});
test('duplicate click performs exactly one POST', async () => {
  const record = fixture(); let finish; const gate = new Promise(resolve => { finish = resolve; }); const posts = [];
  const client = new RecoveryClient(async (p,m,b,k) => {
    if (m) { posts.push({b,k}); await gate; } return record;
  }, 'TECHNICIAN', () => {});
  const first = client.mutate('swap',record,'REJECT','Observed','FOREIGN','VERIFY_OLD_POSSESSION');
  assert.equal(await client.mutate('swap',record,'REJECT','Observed','FOREIGN','VERIFY_OLD_POSSESSION'), false);
  finish(); await first; assert.equal(posts.length, 1); assert.ok(posts[0].k);
});
test('receipt or context changed during preflight requires another human decision', async () => {
  const shown = fixture(); const next = structuredClone(shown); next.version++; next.active_operation.context_hash = 'b'.repeat(64);
  let posts = 0; let displayed;
  const client = new RecoveryClient(async (p,m) => { if (m) posts++; return next; }, 'TECHNICIAN', value => { displayed = value; });
  await assert.rejects(client.mutate('swap',shown,'REJECT','Note','FOREIGN','VERIFY_OLD_POSSESSION'), /đã đổi/);
  assert.equal(posts, 0); assert.equal(displayed, next);
});
for (const code of ['VERSION_CONFLICT','FORBIDDEN','SESSION_REVOKED','STATION_OFFLINE','NETWORK_UNKNOWN']) {
  test('failed mutation ' + code + ' refreshes without retry or success', async () => {
    const record = fixture(); let posts = 0;
    const client = new RecoveryClient(async (p,m) => { if (m) { posts++; throw Object.assign(new Error(code), {code}); } return record; }, 'TECHNICIAN', () => {});
    await assert.rejects(client.mutate('swap',record,'REJECT','Note','FOREIGN','VERIFY_OLD_POSSESSION'), new RegExp(code));
    assert.equal(posts, 1);
  });
}
test('same request after response loss reuses key, explicit retry only', async () => {
  const record = fixture(); const keys = [];
  const client = new RecoveryClient(async (p,m,b,k) => { if (m) { keys.push(k); throw new Error('Lost response'); } return record; }, 'TECHNICIAN', () => {});
  for (let i=0;i<2;i++) await assert.rejects(client.mutate('swap',record,'REJECT','Note','FOREIGN','VERIFY_OLD_POSSESSION'));
  assert.equal(keys.length, 2); assert.equal(keys[0], keys[1]);
});
test('stale GET response cannot replace newer identity', async () => {
  let resolve; let displayed; const wait = new Promise(r => { resolve = r; });
  const client = new RecoveryClient(async p => p.includes('old') ? wait : fixture(), 'TECHNICIAN', v => { displayed = v; });
  const first = client.load('old'); client.reset(); await client.load('new');
  const fresh = displayed; resolve({ state: 'COMPLETED' }); await first; assert.equal(displayed, fresh);
});
test('response committed while identity invalidated cannot update current screen', async () => {
  const record = fixture(); let done; const pending = new Promise(r => { done = r; }); let displayed; let started;
  const sending = new Promise(r => { started = r; });
  const client = new RecoveryClient(async (p,m) => { if (m) { started(); await pending; } return record; }, 'TECHNICIAN', v => { displayed = v; });
  const mutation = client.mutate('old',record,'REJECT','Note','FOREIGN','VERIFY_OLD_POSSESSION');
  await sending; client.reset(); done(); assert.equal(await mutation, false); assert.equal(displayed, null);
});

for (const stage of ['PRE_ACTION_INSPECTION','POST_ACTION_RECEIPT','RECONCILIATION_INSPECTION']) {
  test('Customer uses minimal Backend projection '+stage, () => {
    const op = { ...fixture(stage).active_operation, attestations: undefined, context: undefined,
      stage, receipt_id: 'accepted', receipt_hash: hash, confirmation_status: 'AVAILABLE', case_version: 4 };
    const record = {state:'REVIEW_REQUIRED', recovery_confirmation:op};
    for (const confirm of [true,false]) {
      const body = request(record,confirm ? 'CONFIRM' : 'REJECT','CUSTOMER').body;
      assert.deepEqual(body,{operation_id:'op',context_hash:hash,stage,receipt_id:'accepted',receipt_hash:hash,confirm});
    }
    assert.match(renderToStaticMarkup(React.createElement(RecoveryDetails,{record,role:'CUSTOMER'})),new RegExp(stage));
    for (const status of ['UNAVAILABLE','WAITING_RECEIPT','CONFIRMED','REJECTED','EXPIRED','REVOKED','CONSUMED','CANCELLED']) {
      op.confirmation_status=status;
      assert.throws(()=>request(record,'CONFIRM','CUSTOMER'));
    }
    op.confirmation_status='AVAILABLE';op.receipt_id=null;
    assert.throws(()=>request(record,'CONFIRM','CUSTOMER'));
  });
}

for (const [status,label] of [['CONSUMED','Operation đã consumed'],['CANCELLED','Operation đã đóng'],['REVOKED','REVOKED — operation đã bị thu hồi'],['EXPIRED','EXPIRED — tiếp tục review; chưa chứng minh no-effect'],['AVAILABLE','Operation còn hạn']]) {
  test('Customer terminal banner follows Backend '+status,()=>{
    const op={...fixture().active_operation,stage:'PRE_ACTION_INSPECTION',receipt_id:'accepted',receipt_hash:hash,confirmation_status:status};
    const record={state:'REVIEW_REQUIRED',recovery_confirmation:op};
    const html=renderToStaticMarkup(React.createElement(RecoveryDetails,{record,role:'CUSTOMER'}));
    assert.ok(html.includes(label));
    if(status!=='EXPIRED')assert.ok(!html.includes('EXPIRED —'));
    if(status!=='AVAILABLE')for(const action of ['CONFIRM','REJECT'])assert.throws(()=>request(record,action,'CUSTOMER'));
  });
}
test('Consumed Backend status wins over elapsed TTL; real elapsed TTL still expires active operation',()=>{
  const op={...fixture().active_operation,expires_at:new Date(Date.now()-1000).toISOString(),confirmation_status:'CONSUMED'};
  const record={state:'REVIEW_REQUIRED',recovery_confirmation:op};
  const render=()=>renderToStaticMarkup(React.createElement(RecoveryDetails,{record,role:'CUSTOMER'}));
  assert.ok(render().includes('Operation đã consumed'));assert.ok(!render().includes('EXPIRED —'));
  op.confirmation_status='AVAILABLE';assert.ok(render().includes('EXPIRED —'));
});
