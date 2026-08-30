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
- Dashboard page
- Settings page
- Email field
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

```text
Go to ...
Type ... into ...
Click ...
Check that ... is visible.
Check that ... contains ...
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
