# In-Browser QA Agent

An explainable browser QA agent that converts constrained English instructions into Playwright browser tests, runs them in Chromium, self-heals broken selectors, explains failures, detects flaky behavior, captures failure screenshots, and stores test history.

This project is being developed as a Fusemachines AI Fellowship capstone project.

## Project Members

| Name | Email |
|---|---|
| Neev Badu | baduneev7@gmail.com |
| Pankaj Kumar Mehta | 123pankajmehta@gmail.com |
| Aradhya Dhungel | aradhyadhungelr@gmail.com |

## Project Overview

Modern web applications change frequently. Automated browser tests often fail because selectors become outdated, even when the actual functionality still works.

Example:

```html
<button id="login-button">Login</button>
```

may later become:

```html
<button id="sign-in-button">Sign In</button>
```

A traditional test may fail because it still expects the old selector. This project solves that problem by using a cost-aware self-healing selector resolver.

The system can:

1. Accept constrained English test instructions.
2. Convert them into structured JSON test steps.
3. Run those steps in a browser using Playwright.
4. Extract meaningful page structure using accessibility-style snapshots.
5. Heal broken selectors using a resolution ladder.
6. Explain failures in plain English.
7. Detect flaky tests using reruns.
8. Save run history and named tests.
9. Show failure screenshots and audit output in a dashboard.

## Core Idea

```text
Natural-language instruction
-> structured test steps
-> Playwright browser execution
-> selector resolution ladder
-> self-healing / failure explanation
-> dashboard result
```

## Tech Stack

| Layer | Technology |
|---|---|
| Target demo website | React + Vite |
| QA dashboard frontend | React + Vite |
| Backend server | Node.js + Express |
| Browser automation | Playwright + Chromium |
| API communication | REST API using fetch |
| Storage | Local JSON files for MVP |
| Styling | Plain CSS |
| Instruction parsing | Custom rule-based JavaScript parser |
| Selector healing | Custom JavaScript resolver |
| AI/Vision fallback | Stubbed for future integration |

## Current Features

- Constrained natural-language test instructions
- Validated 20-action instruction schema
- Rule-based English-to-JSON parser
- Playwright browser execution
- Accessibility snapshot extraction
- Cost-aware selector resolution ladder
- Self-healing selectors
- Approved selector memory
- Post-run semantic approval
- Root-cause explanation for failures
- Failure screenshot capture
- Flaky-test detection with reruns
- Saved run history
- Saved run detail view
- Saved named tests
- Accessibility and testability audit
- Vision/LLM fallback stub with estimated cost

## Project Structure

```text
.
├── apps/
│   ├── target-app/
│   │   ├── src/
│   │   │   ├── main.jsx
│   │   │   └── styles.css
│   │   ├── index.html
│   │   └── package.json
│   │
│   └── dashboard/
│       ├── src/
│       │   ├── main.jsx
│       │   └── styles.css
│       ├── index.html
│       └── package.json
│
├── server/
│   ├── src/
│   │   ├── accessibility.js
│   │   ├── accessibilityAudit.js
│   │   ├── approvalStore.js
│   │   ├── index.js
│   │   ├── parser.js
│   │   ├── resolver.js
│   │   ├── rootCause.js
│   │   ├── runStore.js
│   │   ├── runner.js
│   │   └── testStore.js
│   │
│   ├── data/
│   │   └── Local generated data ignored by Git
│   │
│   └── package.json
│
├── package.json
├── package-lock.json
├── .gitignore
└── README.md
```

## Main Components

### 1. Target Demo App

The target app is the website being tested.

Local URL:

```text
http://127.0.0.1:5173
```

It currently includes:

- Login page
- Dashboard, Projects, Users, Billing, Settings, and Profile pages
- QA Playground for form, keyboard, pointer, and state testing
- Text inputs, textareas, selects, checkboxes, enabled and disabled controls
- Modal forms, transient notices, search, and editable profile fields
- DOM variant selector
- Flaky behavior variant

Supported target variants:

```text
original -> Login button
changed  -> Sign In button
flaky    -> randomly Login/Delete behavior
```

Example URLs:

```text
http://127.0.0.1:5173
http://127.0.0.1:5173?variant=changed
http://127.0.0.1:5173?variant=flaky
```

### 2. Backend Server

The backend receives instructions, parses them, runs browser tests, resolves selectors, stores results, and serves screenshots.

Local URL:

```text
http://127.0.0.1:4000
```

Main endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Check server health |
| POST | `/run-hardcoded-test` | Run initial hardcoded Playwright test |
| POST | `/run-instruction` | Run a natural-language instruction |
| GET | `/runs` | List saved test runs |
| GET | `/runs/:id` | Get one saved run detail |
| GET | `/approvals` | List semantic approval decisions |
| POST | `/approvals` | Save approve/reject decision |
| GET | `/tests` | List saved named tests |
| POST | `/tests` | Save a named test |

### 3. Dashboard

The dashboard is the main user interface.

Local URL:

```text
http://127.0.0.1:5174
```

The dashboard supports:

- Writing test instructions
- Selecting DOM variant
- Selecting rerun count
- Running tests
- Saving named tests
- Running saved tests
- Viewing generated steps
- Viewing execution logs
- Viewing selector healing details
- Approving/rejecting healed selector diffs
- Viewing root-cause explanation
- Viewing failure screenshots
- Viewing recent run history
- Opening saved run detail
- Viewing accessibility and testability audit results

## Local Setup

### Prerequisites

Install:

- Node.js 20+
- npm
- Git

### Install Dependencies

From the project root:

```powershell
npm install
```

### Install Playwright Chromium

```powershell
npx playwright install chromium
```

## Running The Project Locally

Open three separate terminals.

### Terminal 1: Target App

```powershell
npm run dev:target
```

Runs at:

```text
http://127.0.0.1:5173
```

### Terminal 2: Backend Server

```powershell
npm run dev:server
```

Runs at:

```text
http://127.0.0.1:4000
```

Health check:

```powershell
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:4000/health"
```

### Terminal 3: Dashboard

```powershell
npm run dev:dashboard
```

Runs at:

```text
http://127.0.0.1:5174
```

## Supported Instruction Format

The MVP intentionally supports constrained English instead of arbitrary natural language.

Example:

```text
Go to Login.
Type user@example.com into Email.
Type password123 into Password.
Click Login.
Check that Dashboard is visible.
Click Settings.
Check that Email contains user@example.com.
```

Supported sentence patterns:

| Category | Pattern | Example |
|---|---|---|
| Navigation | `Go to ...` / `Goto ...` / `Navigate to ...` | `Go to QA Playground.` |
| Input | `Type ... into ...` | `Type Smoke test into Scenario Name.` |
| Input | `Clear ...` | `Clear Scenario Name.` |
| Pointer | `Click ...` | `Click Add User.` |
| Pointer | `Double click ...` | `Double click Increment counter.` |
| Selection | `Select ... from ...` | `Select Critical from Priority.` |
| Checkbox | `Check ...` | `Check Requires approval.` |
| Checkbox | `Uncheck ...` | `Uncheck Weekly digest.` |
| Keyboard | `Press ... in ...` | `Press Enter in Search users.` |
| Pointer | `Hover over ...` | `Hover over Hover target.` |
| Synchronization | `Wait for ...` | `Wait for Hover detected.` |
| Assertion | `Check that ... is visible` | `Check that Dashboard is visible.` |
| Assertion | `Check that ... is hidden` | `Check that Missing panel is hidden.` |
| Assertion | `Check that ... contains ...` | `Check that Email contains user@example.com.` |
| Assertion | `Check that ... has text ...` | `Check that Counter value has text 2.` |
| Assertion | `Check that ... equals ...` | `Check that Job Title equals QA Lead.` |
| Assertion | `Check that ... is enabled` | `Check that Save Profile is enabled.` |
| Assertion | `Check that ... is disabled` | `Check that Archive scenario is disabled.` |
| Assertion | `Check that ... is checked` | `Check that Email reports is checked.` |
| Assertion | `Check that ... is unchecked` | `Check that Weekly digest is unchecked.` |

Navigation and click actions resolve both buttons and links by accessible name.
`goto faculty on https://doece.tcioe.edu.np/` opens the website and follows
its faculty link. Duplicate visible links are accepted only when they point
to the same resolved URL; links with conflicting destinations remain ambiguous.
Use `Check that ... is visible` for assertions rather than navigation.

Every parsed step is checked against the action schema before Playwright is
started. Unsupported actions and missing fields therefore fail early instead
of reaching browser execution.

To navigate the example website using the container:

```sh
docker compose run --rm --no-deps python-services python cli/run.py run-natural-language \
  --url https://goto faculty on https://doece.tcioe.edu.np// \
  --instruction "goto faculty on https://doece.tcioe.edu.np/"
```

### Python CLI: Natural-Language Mode

The Python CLI uses an LLM to work toward a natural-language question or QA goal.
It sends page text, interactive elements, discovered link destinations, and
action feedback to the model, executes one action, then reads the page and replans.
The free tiers of three providers are supported, called through the
[LiteLLM](https://docs.litellm.ai/) router:

| Provider | `--provider` | Key variable | Model variable (code default) | Fallback model variable (code default) |
| --- | --- | --- | --- | --- |
| Google AI Studio | `google` | `GEMINI_API_KEY` | `GEMINI_MODEL` (`gemini-3.6-flash`) | `GEMINI_FALLBACK_MODEL` (`gemini-3.5-flash-lite`) |
| Groq | `groq` | `GROQ_API_KEY` | `GROQ_MODEL` (`openai/gpt-oss-120b`) | `GROQ_FALLBACK_MODEL` (`openai/gpt-oss-20b`) |
| NVIDIA | `nvidia` | `NVIDIA_API_KEY` | `NVIDIA_MODEL` (`mistralai/mistral-large-4-1t-a52b`) | `NVIDIA_FALLBACK_MODEL` (same) |

Add the key for at least one provider to the root `.env`, then rebuild the
Python service so LiteLLM is installed:

```sh
docker compose up -d --build python-services
docker compose exec python-services python cli/run.py
```

With no arguments, the CLI first asks which provider to use, then prompts for
one natural-language message at a
time using `>>> `. The CLI exits with an error if the chosen provider's key is
not set. Questions can follow relevant discovered links to find
information on other pages, then return an evidence-grounded answer with source
URLs. QA goals infer the necessary supported browser steps without requiring
explicit instructions for each step. If a message
includes an `http://` or `https://` URL, that URL is used; otherwise the CLI
uses `TARGET_APP_URL` (the Compose default is `http://target-app:5173`). Press
Ctrl-C or Ctrl-D to quit. The browser page and recent conversation stay active
throughout the REPL session; instructions without a new URL continue on the
current page.
For a single instruction instead, use:

```sh
docker compose exec python-services python cli/run.py run-natural-language \
  --provider google \
  --url http://target-app:5173 \
  --instruction "Check that the login page is visible"
```

`--provider` defaults to `LLM_PROVIDER` (Compose default `groq`).

Both the REPL and single-instruction command use the same bounded agent loop.
The model plans up to eight actions for the current page, and the CLI executes them
locally without another model request while the page remains unchanged. It asks
for fresh evidence after navigation, a visible page-state change, or an action
failure. The CLI uses exact, approved, and accessibility-similarity selector
resolution for those batches, without its separate LLM selector fallback. The
interactive CLI retains visited-page evidence and recent actions between user
instructions. Research navigation is limited to observed HTTP(S) links or a URL
supplied by the user; it does not authorize form submission or state-changing
interactions. The agent reports when it cannot finish rather than inventing
missing facts.

The chosen provider's model is always tried first. On a rate limit (429),
server error such as 503, timeout (90 seconds), or a prompt that exceeds a
model's input cap, LiteLLM retries where useful and then falls back in order:
the chosen provider's fallback model, then every other provider whose key is
set (its model, then its fallback model). The CLI logs the routing order at the
first request and warns whenever a fallback answers. Failing models are cooled
down for 30 seconds. Set `LLM_CROSS_PROVIDER_FALLBACK=false` to stay on the
chosen provider. Prompt trimming uses the chosen provider's input cap: Groq
6,000 estimated tokens, Google AI Studio and NVIDIA 30,000. Input estimation
uses one token per three UTF-8 bytes plus message overhead, not an exact model
tokenizer. The CLI logs reported usage, including cached prompt tokens. Groq
and Gemini cache matching prompt prefixes automatically, so the system prompt
stays at the start of each request; caching reduces cost and latency but does
not preserve conversation state between requests.

For example, asking `Who are the deputy HODs of the department on https://doece.tcioe.edu.np/`
lets the agent choose relevant staff or administration links instead of limiting
its answer to the homepage. Answers depend on what the website actually exposes.

Use `--dry-run` to inspect the next proposed action without executing it;
later actions depend on fresh page evidence. Set the provider's model variable
in `.env` to choose a different model. Natural-language mode currently supports `click`,
`type`, `check_visible`, `check_contains`, `goto`, and `wait_for_change` actions.

After each action the agent records an observation: a diff of the interactive
elements and page text (for example a button changing from `Send` to
`Sending...`), plus browser events such as console messages, page errors,
alerts, failed requests, and the HTTP status of form or API requests. When an
action batch changes the page or produces events, the model reviews this
evidence and can request `wait_for_change` (value: maximum seconds, default 10,
max 30) to wait for a pending result before reporting the outcome. Alerts and
confirms are accepted automatically; prompts are dismissed.

### Expanded Playground Scenario

```text
Go to Login.
Type user@example.com into Email.
Type password123 into Password.
Click Login.
Go to QA Playground.
Clear Scenario Name.
Type Checkout regression into Scenario Name.
Select Critical from Priority.
Check Requires approval.
Check that Requires approval is checked.
Type Validate the checkout flow into Test Notes.
Hover over Hover target.
Wait for Hover detected.
Double click Increment counter.
Check that Counter value has text 2.
Check that Archive scenario is disabled.
```

Generated test steps are represented as JSON objects such as:

```json
[
  {
    "action": "goto",
    "target": "Login"
  },
  {
    "action": "type",
    "target": "Email",
    "value": "user@example.com"
  },
  {
    "action": "click",
    "target": "Login"
  }
]
```

## Selector Resolution Ladder

The project uses a cost-aware selector resolution ladder.

```text
1. exact_role_match
2. approved_memory
3. accessibility_text_similarity
4. vision_llm_fallback stub
```

### Example Self-Healing Case

Instruction:

```text
Click Login.
```

Original DOM:

```html
<button id="login-button">Login</button>
```

Changed DOM:

```html
<button id="sign-in-button">Sign In</button>
```

Expected healing result:

```text
Old selector: role=button[name="Login"]
New selector: role=button[name="Sign In"]
Strategy: accessibility_text_similarity
Confidence: 0.91
Estimated cost: $0.0000
```

After the user approves the change, future runs can use:

```text
approved_memory
```

before falling back to text similarity again.

## Demo Scenarios

### 1. Normal Passing Test

Use:

```text
Target DOM: Original
Reruns: 1
```

Expected:

```text
Status: PASSED
Strategy: exact_role_match
Healed: false
```

### 2. Self-Healing Selector Test

Use:

```text
Target DOM: Changed
Reruns: 1
```

Instruction still says:

```text
Click Login.
```

Expected:

```text
Status: PASSED
Healed: true
Old selector: role=button[name="Login"]
New selector: role=button[name="Sign In"]
```

### 3. Root-Cause Failure Test

Change:

```text
Click Login.
```

to:

```text
Click Export.
```

Expected:

```text
Status: FAILED
Root-cause explanation appears
Failure screenshot appears
Vision/LLM fallback stub is shown as skipped
```

### 4. Flaky Test Detection

Use:

```text
Target DOM: Flaky
Reruns: 5
```

Expected:

```text
Status: FLAKY
Mixed pass/fail rerun results
```

### 5. Saved Tests And Run History

Expected:

```text
Save named test
Run saved test
View recent runs
Open saved run detail
```

## Local Data Storage

This MVP uses JSON files for local storage:

```text
server/data/runs.json
server/data/approvals.json
server/data/tests.json
server/data/screenshots/
```

These files are ignored by Git because they are generated local data.

The clean empty state for JSON storage files is:

```json
[]
```

## Git And GitHub Workflow

This project follows the Fusemachines AI Fellowship GitHub workflow.

### Branching

```text
main      -> stable branch, PR merge only
develop   -> integration branch
feature/* -> new features
bugfix/*  -> bug fixes
docs/*    -> documentation updates
```

### Daily Workflow

```powershell
git checkout develop
git pull origin develop
git checkout -b feature/short-task-name
```

Work and commit:

```powershell
git add .
git commit -m "feat(scope): short description"
```

Push:

```powershell
git push -u origin feature/short-task-name
```

Then open a Pull Request into:

```text
develop
```

### Commit Convention

Use Conventional Commits:

```text
feat: new feature
fix: bug fix
docs: documentation only
style: formatting only
refactor: code change without new feature/fix
chore: maintenance/config
test: tests
perf: performance improvement
```

Examples:

```text
feat(resolver): add approved selector memory
fix(run-store): handle empty runs file
docs(readme): add setup instructions
chore(repo): ignore generated server data
```

## Pull Request Checklist

Before opening a PR:

```text
- Pull latest develop
- Confirm branch name is lowercase and hyphenated
- Confirm commit messages follow Conventional Commits
- Confirm node_modules is not staged
- Confirm .env files are not staged
- Confirm generated server data is not staged
- Run the relevant local app/test manually
- Add screenshots for UI changes
- Write clear testing steps in the PR description
```

PR description should include:

```md
## What does this do?

Briefly explain the change.

## How to test

1. Run required services.
2. Open dashboard.
3. Perform the test steps.

## Screenshots

Add screenshots for UI changes.

## Related Issue

Link Trello/GitHub issue if available.
```

## Security Notes

Do not commit:

```text
.env
API keys
passwords
node_modules
dist
server/data/*.json
server/data/screenshots/
```

Future LLM or vision API keys must be stored in environment variables, not source code.

## Current Limitations

- The instruction parser is rule-based and supports only constrained English.
- Vision/LLM fallback is currently a stub, not a real API integration.
- Storage uses JSON files instead of a database.
- Target app is still small and should be expanded with more workflows.
- No CI/CD pipeline yet.
- No automated unit test suite yet.
- Browser support is Chromium only.

## Planned Next Work

- Expand target demo app with Users, Projects, Billing, and Profile pages.
- Add more realistic saved test cases.
- Add test suite runner.
- Add metrics dashboard.
- Add parser and resolver tests.
- Experiment with SLM/LLM parsing.
- Add real LLM or vision fallback if time allows.
- Improve documentation and final demo script.

## Team Task Ownership

| Member | Focus Area |
|---|---|
| Neev Badu | Core system, backend, resolver, runner, dashboard integration, GitHub workflow |
| Pankaj Kumar Mehta | SLM/LLM experiments, parser evaluation, metrics, research documentation |
| Aradhya Dhungel | Target app expansion, demo workflows, UI polish, demo documentation |

## AIF Engineering Reminder

This project should demonstrate not only a working AI/QA idea, but also professional engineering workflow:

```text
Clear code
Consistent commits
GitHub PR workflow
No secrets in repo
Useful documentation
Peer review
Measurable evaluation
```
