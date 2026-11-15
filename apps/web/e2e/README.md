# Recovery Browser E2E

Real headless Chromium, separate authenticated contexts, real isolated PostgreSQL,
two Backend OS processes, device worker and durable simulator ledger. This suite
does not use Computer Use or attach to the user's Chrome profile.

Run from the repository root, with Docker/PostgreSQL healthy. Playwright and
Chromium are already installed locally; do not reinstall for each test.

```powershell
$scenario='post'
$label='pw_'+$scenario.Replace('-','_')+'_'+[guid]::NewGuid().ToString('N').Substring(0,10)
$env:TEST_REPORT_ROOT='PHASE8A_TESTS'
$env:P8_TEST_API_PORT='8070'
$env:P8_MANUAL_WEB_PORT='5190'
$env:PW_SCENARIO=$scenario
$env:P8_PLAYWRIGHT_SPEC=if($scenario -eq 'smoke'){'smoke.spec.ts'}elseif($scenario -eq 'roles'){'roles.spec.ts'}else{'staged.spec.ts'}
$env:PLAYWRIGHT_BROWSERS_PATH=Join-Path $PWD '.cache/ms-playwright'
$env:PW_OUTPUT_DIR=Join-Path $PWD ('docs/PHASE8A_TESTS/'+$label+'_browser')
New-Item -ItemType Directory -Path $env:PW_OUTPUT_DIR | Out-Null
.\.venv\Scripts\python.exe tools/run_phase6_fix.py $label script tools/smoke_phase8a.py --branch E --manual-browser
$runExit=$LASTEXITCODE
Set-Content -LiteralPath (Join-Path $env:PW_OUTPUT_DIR 'runner_exit.txt') -Value $runExit
```

Use an unused label and ports. Run fixtures sequentially. Existing runtimes,
schemas, private credentials and ledgers are retained; only the processes
created by the fixture are stopped on exit. The initial wrong-return review
uses real command timeout, so setup takes time before Browser starts.

Full scenario matrix (one new fixture per entry):

- `smoke`: login/logout, independent Technician/Customer, role projection, mobile.
- `post`: PRE, INTENT/ACK, activation, handover, POST, settlement and exact replay.
- `pre-reject`, `post-reject`: rejection blocks further authorization/settlement.
- `reference`, `wrong-stage`, `version`: intentional wire corruption, fail closed.
- `duplicate`, `response-loss`, `revoked`: one POST/attestation or no mutation.
- `closure`: real expiry, durable no-effect closure and retained holds.
- `successor`: real expiry, read-only current inspection and chain settlement.
- `stale-expired`: actual 15-second freshness and operation TTL, no clock edits.
- `roles`: Admin read-only/403 mutation, other Customer/404 (hidden resource), unassigned Tech/403.
- `terminal-label`: **known Minor regression**; after consume the Customer banner
  must not say EXPIRED. Keep its assertion enabled. A passing `post` run alone
  does not establish that this display regression is fixed.

Retries are zero. Do not blindly retry on the same physical operation after an
error. Refresh each role after another actor changes proof/version. Never relax
business freshness or deadlines. The operator uses only authorized tasks and
the real simulator model, without SQL custody/proof updates.

Evidence: Browser JUnit/JSON, sanitized HTTP method/path/status/code, screenshots
after login, fixture JSON with DB/custody/Payment/holds/audit/effect/fence state.
`manual.json` identifies the exact runtime and URLs; `private.json` is local only.
Raw Playwright traces/HAR/video are disabled because they may contain auth data.
The reporter redacts known fixture passwords/tokens from errors/text attachments.
Never commit runtime/private data, Browser profiles, node_modules, cache, dist,
test reports or screenshots by bulk staging. Preserve failed evidence locally.
