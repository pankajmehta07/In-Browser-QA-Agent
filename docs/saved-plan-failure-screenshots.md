# Optional failure evidence for saved plans

This PR allows the shared saved-plan executor to capture a viewport PNG after a
failed run, before its browser closes. Single saved runs and selected suites both
use that executor. Passing runs are not captured.

## Configuration

- `ENABLE_RUN_SCREENSHOT_CAPTURE=true` explicitly enables writing new evidence.
- `RUN_SCREENSHOT_ROOT` must point to an existing operator-controlled directory.
- `ENABLE_RUN_SCREENSHOTS=true` independently enables the prior run-linked image
  read endpoint. Enabling capture alone does NOT enable image serving.

Both capture and serving remain disabled by default. This PR does not enable them
in Compose or committed environment files, create fallback directories or change
the schema. Use the API process/container's filesystem path, with write permission
for capture and read permission for serving. Protect stored screenshots as
sensitive data and keep the service limited to authorized staging.

## Capture behavior

When execution returns `failed` and capture is enabled, the executor checks the
current page origin against the configured execution origin. An out-of-origin
page is skipped. For a page still in scope, Playwright takes a viewport PNG with
a five-second capture timeout; it does not capture the entire scrollable page.

The helper validates the PNG signature and 5 MiB size limit, then writes it to a
unique `failure-{uuid}.png` using exclusive creation. Filesystem work runs off the
async request loop. On POSIX, creation requests mode 0600; Windows access remains
subject to the directory's ACL. The storage directory and local filesystem must
be trusted, not writable by an adversary racing path replacements.

The result includes `screenshotCapture.status`:

- `captured`: file written; `timing` is `after_execution_before_close`.
- `unavailable`: capture/configuration/storage failed; a generic reason is provided.
- `skipped`: current page was outside the configured origin.

Disabled capture and passing runs do not add capture metadata. Capture errors do
not replace the test's assertion/root-cause result, skip saving it, rerun steps,
or change suite continuation rules. Cancellation still propagates rather than
starting extra actions. The original database persistence error behavior remains.

Capture occurs after the existing setup/test/optional cleanup phases. Cleanup may
already have changed or dismissed the failing UI state. The image is final-state
evidence, NOT a guaranteed screenshot of the exact failing step. Origin is checked
before capture; this is not a network sandbox or protection against every
concurrent page navigation or on-page side effect.

## Persistence and access

The executor passes the generated absolute path through the existing
`screenshotPath` save contract to `runs.screenshot_path` and records it in native
result JSON. It adds no migration. Existing compatibility DTOs omit the filesystem
path, retain safe capture status metadata, and keep `artifactAvailability` marked
`not_exposed` because no embedded image URL is introduced.

When serving is separately enabled, the image is available through
`GET /compat/runs/{run_id}/screenshot`. Its root/signature/size checks remain in
force. Native execution responses gain optional capture metadata/path only when
enabled; no existing response field is removed.

If saving the execution fails after writing an image, the file may remain
unreferenced. Cancellation during a worker-thread write can also leave a file
without a saved result. There is no automatic cleanup on uncertain database commits, no
retention/quota system, no trace capture, no image redaction and no automatic UI
link. Operators must monitor disk usage and manage protected evidence retention.
Capture can contain credentials or personal data; never treat the opt-in flag as
authentication or consent from every person represented on the page.

## Verification

Executor tests isolate browser and database boundaries while exercising real
temporary file writes, disabled defaults, passing runs, missing storage, invalid
or oversized content, out-of-origin pages and sanitized capture failures. An
opt-in Chromium test performs a real failed assertion, captures one readable
PNG, verifies its save reference and checks that the compatibility mapper does
not expose its filesystem path. Existing PostgreSQL screenshot round-trip tests
cover the stored reference and read endpoint separately. No external website or
actual project screenshot is used.

Local verification passed all 188 Python tests (including 22 PostgreSQL and 6
Chromium tests), 3 Node parser tests and `git diff --check`. Environment: Windows,
Python 3.11 and an isolated PostgreSQL 17 cluster. The existing Starlette/httpx
deprecation warning remains. Linux CI, PostgreSQL 18 and combined Docker/dashboard
deployment acceptance remain unverified locally.
