# LLM instruction preview for review

`POST /compat/instructions/preview` observes the server-configured page and asks
the existing Groq planner for a structured draft. It never executes the proposed
steps or saves a test. This is a current-page planning adapter, not the full
conversational Page Agent from the personal prototype.

## Opt-in request

```json
{
  "instruction": "Enter user@example.com in Email and click Login",
  "confirmPageRead": true,
  "allowAI": true
}
```

Operators must set `ENABLE_INSTRUCTION_PREVIEW=true` and configure `GROQ_API_KEY`.
The existing `GROQ_MODEL` setting is reused (default `openai/gpt-oss-120b`). The
flag remains disabled by default and is not enabled in Compose by this PR.

Instructions are limited to 10,000 characters. Both consent fields must be actual
boolean true values. Extra fields, including client URL overrides, are rejected.
Only `TARGET_APP_URL` selects the page. Restrict it to an authorized staging
origin and keep the API behind appropriate access controls; the flag and consent
fields are not authentication or tenant authorization.

## Flow

1. Validate consent, feature flag, provider configuration and server target.
2. Open a fresh headless browser and navigate to the configured page.
3. Reject observation outside its configured origin.
4. Extract visible controls and headings, then prepare compact provider context.
5. Call the existing Groq planner with a 45-second response timeout.
6. Validate the entire generated list against the supported TestPlan schema.
7. Check each proposed target against observed control names, roles and states.
8. Return a review-only draft or specific needs-input issues, then close the browser.

Only the existing five actions are supported: `goto`, `type`, `click`,
`check_visible`, and `check_contains`. `goto` asserts an already-visible heading;
it does not navigate. Malformed or unsupported steps reject the whole provider
plan with 502 rather than silently dropping individual steps.

The response includes `status`, `reviewRequired: true`, `plan`, `issues`, parser
source/model/duration, and `coverage: current_page_only` for generated plans.
Issues identify the step, action, target and reason. If the provider returns an
answer instead of test steps, the response requests clarification with no plan.

Targets must match observed names. Clicks require one enabled button/link;
typing and field assertions require one enabled input/textarea textbox. Headings
and observed names can ground visibility assertions. Unobserved future controls,
duplicate action targets, disabled controls and unsupported field types become
`needs_input`, not silently approved or guessed interactions.

## What draft means

Even `status: draft` is NOT a passing test, complete workflow or verified business
expectation. No form has been filled or submitted. The tester must review actions,
credentials, expected results and later page states before explicitly saving and
running a plan through the existing endpoints. Target grounding does not prove
the user intended every model-proposed action or neutralize all prompt injection.

This endpoint does not discover authenticated states, click tabs, inspect opened
dialogs, load saved browser sessions, infer hidden controls, ask follow-up questions
in a durable conversation, or generate comprehensive edge-case coverage. A login
followed by project creation will need further observation, not invented controls.
Unresolved placeholders still need resolution before saved-plan execution.

## Provider context and cost boundaries

The adapter sends the instruction, up to 100 visible named controls, up to 20
headings and a title capped at 200 characters. Control/heading names longer than
200 characters are excluded rather than shortened into inaccurate targets. URL
query and fragment are removed from the provider snapshot. The full body text and
input values are not read by this adapter for the provider call.

This is minimization, not comprehensive PII or credential redaction. Instructions,
titles, headings, control names and URL paths may themselves contain sensitive
data. Explicit provider consent is required; use disposable staging data. Existing
browser logs and native extractors retain their existing behavior.

The existing system prompt treats page content as untrusted data. The adapter
does not change native prompts, SDK configuration, pricing, caching or budgets.
There is no new daily token budget or exact usage counter here; the native helper
does not return token usage. The 45-second timeout is not a token/cost guarantee,
and existing SDK-level retry behavior remains unchanged. Mocked CI never makes
real provider calls. Provider failure/timeout returns a sanitized 502 without
executing generated steps; other infrastructure failures use compatibility errors.

## Safety and integration limits

Opening a page executes its scripts and can make network requests or trigger
on-load effects. This is not a network sandbox or a guarantee of zero website
side effects. Origin checks occur around observation, not before every outgoing
request. Do not expose it to arbitrary untrusted targets. Browser cleanup is
attempted after observation and provider failures; no browser remains open for a
user review pause.

There is no dashboard wiring, proxy cutover, database migration, automatic save,
automatic execution, rule-based fallback change or durable job in this PR. The
native `/instructions/run` API remains unchanged. Full workflow execution and
production authorization remain separate integration gates.

## Verification

ASGI tests exercise consent/configuration gates, model-plan validation, context
minimization, observed-target checks, ambiguous/disabled/wrong-type controls,
provider failures, origin changes and cleanup. Browser/provider boundaries are
mocked there. An opt-in local Chromium test uses the real discovery extractor and
a mocked provider, proving that previewing a type/click plan leaves the fixture's
input, record and local storage unchanged. No live LLM or external site is used.

Local verification passed all 180 Python tests (including 22 PostgreSQL and 5
Chromium tests), 3 Node parser tests and `git diff --check`. Environment: Windows,
Python 3.11 and an isolated PostgreSQL 17 cluster. The existing Starlette/httpx
deprecation warning remains. Live-provider quality, Linux CI, PostgreSQL 18 and
combined Docker/dashboard deployment acceptance remain unverified locally.
