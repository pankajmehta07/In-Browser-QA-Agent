# In-Browser QA Agent

This project is a learning MVP for an in-browser QA agent.

The system will:

1. Accept simple English test instructions.
2. Convert them into structured test steps.
3. Run those steps in a browser using Playwright.
4. Detect broken selectors.
5. Try to heal selectors using fallback strategies.
6. Show pass/fail and healing details in a dashboard.

## Apps

- `apps/target-app`: demo website that we will test
- `apps/dashboard`: user dashboard for writing instructions and viewing results
- `server`: backend API, parser, Playwright runner, and selector healing logic