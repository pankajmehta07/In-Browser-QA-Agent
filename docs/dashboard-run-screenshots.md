# Opt-in run-linked screenshot access

`GET /compat/runs/{run_id}/screenshot` reads an existing saved run's
`screenshot_path`. The URL accepts a UUID, never a client-selected filename.
This is a limited evidence-read adapter, not a public static-file server or a
complete artifact authorization system.

## Operator configuration

Access is disabled by default. Explicitly set both:

- `ENABLE_RUN_SCREENSHOTS=true`
- `RUN_SCREENSHOT_ROOT` to the absolute directory containing approved failure PNGs

The directory must already exist and be visible to the FastAPI process. Use the
server/container filesystem path, not a dashboard URL or an unrelated host path.
The stored reference must resolve inside that root. Legacy relative references
are resolved against the API process working directory, matching the existing
runner's relative-path convention. Moving the process or files does not migrate
old references automatically.

These variables are NOT enabled in Compose or committed environment files by this
PR. Only enable access on a trusted local/development service behind appropriate
network or application access controls. Screenshots can contain credentials,
personal information and other sensitive page data. This flag is not user
authorization. Do not enable it on a publicly reachable unauthenticated API.

## File handling and responses

- Look up the saved run before reading its recorded screenshot reference.
- Resolve the configured root and reference, including symlinks; reject paths
  outside the root and files without a `.png` suffix.
- Require a regular file, a PNG signature and a maximum size of 5 MiB. Reads are
  bounded and run off the asynchronous request loop in a worker thread.
- Return `image/png`, `Cache-Control: no-store`, `nosniff`, a restrictive content
  security policy, and an inline filename derived only from the run UUID.
- Do not expose filesystem paths, directory listings or the private exception.

The signature check is not full image decoding, content sanitization or PII
redaction. The root and its contents must be operator-controlled, with no
untrusted local users able to replace paths during a read; resolving paths is not
a filesystem sandbox against concurrent adversarial mutation.

Disabled access returns 403. Missing configuration or an unavailable root returns
503. Missing runs/files, invalid signatures, oversized files and out-of-root
references return a generic 404. Invalid run IDs return 422. Unexpected database
failures use the sanitized compatibility 503 response.

## Integration boundaries

No screenshot capture, trace downloads, retention policy, file migration or schema
change is introduced. The legacy runner can already persist `screenshot_path`;
the newer saved-plan executor only captures when the separate opt-in feature in
`saved-plan-failure-screenshots.md` is enabled. Without it, those runs usually have
no image to serve. Missing evidence does not cause a test rerun.

The dashboard and run DTOs are not rewired here. Their existing
`artifactAvailability: not_exposed` marker remains unchanged; it indicates no
embedded artifact link is exposed by that DTO, even when this separate opt-in
endpoint is enabled. A future UI integration must handle disabled, unavailable
and expired evidence and enforce access control before linking sensitive images.

Native APIs, Express, proxy settings, execution actions and LLM behavior are
unchanged. Trace serving and production origin/team ownership remain separate
gates before a dashboard cutover.

## Verification

ASGI tests use temporary local files and a mocked run-store boundary to exercise
real path resolution, bounded file reads, response headers, configuration gates,
relative legacy paths, invalid signatures, oversize rejection and sanitized
errors. Symlink escape is tested where the platform permits creating symlinks.
A PostgreSQL test verifies the real stored reference round trip and that removing
an image does not remove run history. No actual project screenshots are read.

Local verification passed all 170 Python tests (including 22 PostgreSQL and 4
Chromium tests), 3 Node parser tests and `git diff --check`. The symlink-escape
test also ran successfully on this Windows environment. Python 3.11 and an
isolated PostgreSQL 17 cluster were used. The existing Starlette/httpx deprecation
warning remains. Linux CI, PostgreSQL 18 and full Docker deployment acceptance
remain unverified locally.
