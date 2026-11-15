import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import RedactReporter from '../e2e/redact-reporter.ts';

test('Browser reporter redacts errors and text attachments without raw auth traces',()=>{
  const directory=fs.mkdtempSync(path.resolve('../../.cache/pw-redaction-test-'));
  const syntheticPassword='Synthetic-Redaction-Only-Not-A-Credential';
  const syntheticToken='eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxOTk5OTk5OTk5fQ.syntheticSigOnlyNeverARealToken';
  fs.writeFileSync(path.join(directory,'private.json'),JSON.stringify({passwords:{technician:syntheticPassword}}));
  const attachment=path.join(directory,'error-context.md');
  const raw=`${syntheticPassword} Bearer ${syntheticToken} ${syntheticToken}`;
  fs.writeFileSync(attachment,raw);
  const previous=process.env.PW_RUNTIME;
  process.env.PW_RUNTIME=directory;
  try {
    const result={errors:[{message:raw,stack:raw,snippet:raw}],
      attachments:[{path:attachment,contentType:'text/markdown',name:'error-context'}]};
    new RedactReporter().onTestEnd({},result);
    for(const value of [...Object.values(result.errors[0]),fs.readFileSync(attachment,'utf8')]) {
      assert.ok(!value.includes(syntheticPassword));
      assert.ok(!value.includes(syntheticToken));
      assert.match(value,/REDACTED/);
    }
  } finally {
    if(previous===undefined)delete process.env.PW_RUNTIME;else process.env.PW_RUNTIME=previous;
  }
  // Retain the isolated unit-test files; no removal of user runtime/evidence.
});
