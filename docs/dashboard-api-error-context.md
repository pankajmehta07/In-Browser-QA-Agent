# Preserve dashboard API error context

The shared dashboard `apiRequest` helper previously converted every failed HTTP
response into a plain Error containing only its message. That discarded partial
suite results, saved run IDs, execution-state warnings and revision-conflict
metadata required by the compatibility APIs.

This PR exports `ApiRequestError extends Error` with:

- `message`: the existing server `errorMessage` string or a safe generic message.
- `status`: HTTP status when a response exists; null for a fetch/network failure.
- `body`: parsed JSON when available; null for non-JSON or malformed responses.

Existing `catch (error) { notify(error.message) }` callers keep working. Successful
JSON returns its body as before. Non-JSON responses keep their existing null
success behavior. Invalid JSON now produces a deterministic error with the HTTP
status, without returning raw response text or parser excerpts.

## Future consumers

```javascript
try {
  await apiRequest(path, options);
} catch (error) {
  if (error instanceof ApiRequestError) {
    if (error.status === 409 && error.body?.currentRevision) {
      // Reload and ask the tester to review; do not resubmit automatically.
    }
    if (error.status === 503 && error.body?.type === "selected_plan_suite") {
      // Display the available partial report; never replay the whole suite.
    }
  }
  // Keep ordinary user-facing error reporting as well.
}
```

This helper does not retry requests, create fallback execution, reinterpret a
503 as an assertion failure, or infer that a failed network request never reached
the server. Read `error.body.safeToRetry` and execution-state fields where the API
supplies them; their absence is not permission to retry a write or browser action.

Preserving the body is not automatic UI handling: current views still display
messages only. A later integration must render partial results and revision
conflicts explicitly. Error bodies are untrusted and may contain sensitive test
data; they must not be rendered as HTML, broadly logged or copied into telemetry.
The helper does not redact arbitrary backend JSON or native error details.

## Data-source boundary

No API base URL, Vite proxy, route, UI layout or backend is switched here. The
current Express stores use local JSON files; shared FastAPI uses PostgreSQL.
Mixing Python totals with an Express-backed library would report different
datasets as though they were one. A subsequent opt-in workspace/cutover must keep
the source consistent and complete acceptance checks before replacing defaults.

## Verification

`npm run test:api -w apps/dashboard` starts a temporary loopback Vite server and
loads the real API module in Chromium, intercepting all test API requests. It
checks complete 503 payload retention, 409 revision metadata, unchanged success
responses, non-JSON errors, malformed JSON, network failures and one-request POST
semantics. It never contacts a real backend or modifies project data.

The frontend CI job now runs this suite alongside the existing save/delete
regressions. No dependency, lockfile, schema or production configuration change
is required.

Local verification passed 6 API-client browser tests, all 11 existing dashboard
save/delete browser tests, 3 Node parser tests, both Vite production builds and
`git diff --check`. Environment: Windows, Node 24 and locally installed Chrome.
No Python source changed, and the Python suite was not rerun for this client-only
PR. Linux/Node 22 CI and combined Docker deployment acceptance remain unverified
locally. Temporary test servers and browsers were closed after verification.
