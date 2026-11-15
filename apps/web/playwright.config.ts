import { defineConfig } from '@playwright/test';
import path from 'node:path';
const output=process.env.PW_OUTPUT_DIR ?? path.resolve('../../.cache/playwright-results');
export default defineConfig({
  testDir:'./e2e', fullyParallel:false, workers:1, retries:0, timeout:180_000,
  outputDir:path.join(output,'artifacts'),
  reporter:[['./e2e/redact-reporter.ts'],['line'],
    ['junit',{outputFile:path.join(output,'results.xml')}],
    ['json',{outputFile:path.join(output,'results.json')}]],
  use:{headless:true,trace:'off',screenshot:'off',video:'off'},
  projects:[{name:'chromium',use:{browserName:'chromium'}}],
});
