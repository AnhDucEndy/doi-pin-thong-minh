import type { Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import fs from 'node:fs';
import path from 'node:path';
export default class RedactReporter implements Reporter {
  onTestEnd(_test: TestCase,result: TestResult) {
    const privatePath=path.join(process.env.PW_RUNTIME!,'private.json');
    const secrets=Object.values(JSON.parse(fs.readFileSync(privatePath,'utf8')).passwords) as string[];
    const redact=(value:string)=>{
      for(const secret of secrets)value=value.split(secret).join('[REDACTED]');
      return value.replace(/Bearer\s+[A-Za-z0-9._~+/-]+/gi,'Bearer [REDACTED]')
        .replace(/eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}/g,'[REDACTED TOKEN]');
    };
    for(const error of result.errors) {
      for(const field of ['message','stack','snippet'] as const) {
        if(error[field]) {
          error[field]=redact(error[field]!);
        }
      }
    }
    for(const attachment of result.attachments) {
      if(attachment.path&&attachment.contentType.startsWith('text/')) {
        const content=fs.readFileSync(attachment.path,'utf8');
        const clean=redact(content);
        if(clean!==content)fs.writeFileSync(attachment.path,clean);
      }
    }
  }
}
