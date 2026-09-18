import path from "node:path";
import express from "express";
import cors from "cors";
import { deleteTest, listTests, saveTest } from "./testStore.js";
import { runHardcodedLoginTest, runStructuredTest } from "./runner.js";
import { parseInstruction } from "./parser.js";
import { explainFailure } from "./rootCause.js";
import { listRuns, saveRun } from "./runStore.js";
import { auditAccessibility } from "./accessibilityAudit.js";
import { fileURLToPath } from "node:url";
import { listApprovals, saveApproval } from "./approvalStore.js";
const app = express();
const port = 4000;
const currentFilePath = fileURLToPath(import.meta.url);
const currentDirectory = path.dirname(currentFilePath);
const screenshotsDirectory = path.join(currentDirectory, "..", "data", "screenshots");



app.use(cors());
app.use(express.json());
app.use("/screenshots", express.static(screenshotsDirectory));

app.get("/health", (request, response) => {
  response.json({
    ok: true,
    service: "in-browser-qa-agent-server",
  });
});

app.post("/run-hardcoded-test", async (request, response) => {
  try {
    const result = await runHardcodedLoginTest();

    response.json(result);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message,
    });
  }
});

app.post("/run-instruction", async (request, response) => {
  try {
    const { instruction, variant = "original", reruns = 1 } = request.body;

    if (!instruction) {
      response.status(400).json({
        status: "failed",
        errorMessage: "instruction is required",
      });
      return;
    }

    const generatedSteps = parseInstruction(instruction);
    const runCount = Math.max(1, Math.min(Number(reruns) || 1, 5));
    const runResults = [];

    for (let index = 0; index < runCount; index += 1) {
      const result = await runStructuredTest(generatedSteps, { variant });
      const resultWithAudit = {
        ...result,
        runNumber: index + 1,
        rootCause: explainFailure(result),
        accessibilityAudit: auditAccessibility(
          result.accessibility?.final || [],
        ),
      };

      runResults.push(resultWithAudit);
    }

    const finalResult = classifyRerunResults(runResults);

    const savedRun = await saveRun(finalResult);

    response.json({
      ...finalResult,
      savedRunId: savedRun.id,
    });
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message,
    });
  }
});

app.get("/runs", async (request, response) => {
  try {
    const runs = await listRuns();
    response.json(runs);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message,
    });
  }
});

app.get("/runs/:id", async (request, response) => {
  try {
    const runs = await listRuns();
    const run = runs.find((item) => item.id === request.params.id);

    if (!run) {
      response.status(404).json({
        status: "failed",
        errorMessage: "Run not found"
      });
      return;
    }

    response.json(run);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message
    });
  }
});

app.get("/approvals", async (request, response) => {
  try {
    const approvals = await listApprovals();
    response.json(approvals);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message
    });
  }
});

app.post("/approvals", async (request, response) => {
  try {
    const {
      runId,
      stepName,
      oldSelector,
      newSelector,
      oldTarget,
      newTarget,
      decision,
      confidence,
      strategy
    } = request.body;

    if (!runId || !stepName || !decision) {
      response.status(400).json({
        status: "failed",
        errorMessage: "runId, stepName, and decision are required"
      });
      return;
    }

    const savedApproval = await saveApproval({
      runId,
      stepName,
      oldSelector,
      newSelector,
      oldTarget,
      newTarget,
      decision,
      confidence,
      strategy
    });

    response.json(savedApproval);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message
    });
  }
});

app.get("/tests", async (request, response) => {
  try {
    const tests = await listTests();
    response.json(tests);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message
    });
  }
});

app.post("/tests", async (request, response) => {
  try {
    const { name, instruction, variant = "original", reruns = 1 } = request.body;

    if (!name || !instruction) {
      response.status(400).json({
        status: "failed",
        errorMessage: "name and instruction are required"
      });
      return;
    }

    const savedTest = await saveTest({
      name,
      instruction,
      variant,
      reruns
    });

    response.json(savedTest);
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message
    });
  }
});

app.delete("/tests/:id", async (request, response) => {
  try {
    const deleted = await deleteTest(request.params.id);

    if (!deleted) {
      response.status(404).json({
        status: "failed",
        errorMessage: "Test not found",
      });
      return;
    }

    response.json({
      status: "passed",
      deletedId: request.params.id,
    });
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message,
    });
  }
});

app.post("/run-test-suite", async (request, response) => {
  try {
    const { testIds = [], variant = "original", reruns = 1 } = request.body;

    const savedTests = await listTests();

    const selectedTests =
      testIds.length > 0
        ? savedTests.filter((test) => testIds.includes(test.id))
        : savedTests;

    if (selectedTests.length === 0) {
      response.status(400).json({
        status: "failed",
        errorMessage: "No saved tests found for the suite.",
      });
      return;
    }

    const suiteStartedAt = new Date().toISOString();
    const suiteResults = [];

    for (const test of selectedTests) {
      const generatedSteps = parseInstruction(test.instruction);
      const runCount = Math.max(1, Math.min(Number(reruns) || 1, 5));
      const runResults = [];

      for (let index = 0; index < runCount; index += 1) {
        const result = await runStructuredTest(generatedSteps, { variant });

        runResults.push({
          ...result,
          runNumber: index + 1,
          rootCause: explainFailure(result),
          accessibilityAudit: auditAccessibility(
            result.accessibility?.final || [],
          ),
        });
      }

      const finalTestResult = classifyRerunResults(runResults);

      suiteResults.push({
        id: test.id,
        name: test.name,
        instruction: test.instruction,
        status: finalTestResult.status,
        flaky: finalTestResult.flaky || false,
        durationMs: finalTestResult.durationMs,
        generatedSteps,
        result: finalTestResult,
      });
    }

    const suiteFinishedAt = new Date().toISOString();

    const passedCount = suiteResults.filter(
      (test) => test.status === "passed",
    ).length;

    const failedCount = suiteResults.filter(
      (test) => test.status === "failed",
    ).length;

    const flakyCount = suiteResults.filter(
      (test) => test.status === "flaky" || test.flaky,
    ).length;

    const suiteStatus =
      failedCount > 0 ? "failed" : flakyCount > 0 ? "flaky" : "passed";

    const suiteResult = {
      status: suiteStatus,
      startedAt: suiteStartedAt,
      finishedAt: suiteFinishedAt,
      durationMs:
        new Date(suiteFinishedAt).getTime() -
        new Date(suiteStartedAt).getTime(),
      type: "suite",
      testCount: suiteResults.length,
      passedCount,
      failedCount,
      flakyCount,
      variant,
      reruns: Math.max(1, Math.min(Number(reruns) || 1, 5)),
      tests: suiteResults,
      rootCause:
        suiteStatus === "passed"
          ? null
          : {
              title: "Test suite contains failing or flaky tests",
              summary:
                "At least one saved test did not pass during the suite run.",
              likelyCause:
                "One or more workflows may have a broken selector, changed UI text, flaky behavior, or unsupported instruction.",
              recommendation:
                "Open the failing test result, inspect the failed step, and approve healing if the DOM change is intentional.",
              evidence: suiteResults
                .map((test) => `${test.name}: ${test.status}`)
                .join(", "),
            },
    };

    const savedRun = await saveRun(suiteResult);

    response.json({
      ...suiteResult,
      savedRunId: savedRun.id,
    });
  } catch (error) {
    response.status(500).json({
      status: "failed",
      errorMessage: error.message,
    });
  }
});

app.listen(port, () => {
  console.log(`QA Agent server running at http://127.0.0.1:${port}`);
});

function classifyRerunResults(runResults) {
  const statuses = runResults.map((result) => result.status);
  const uniqueStatuses = new Set(statuses);

  if (runResults.length === 1) {
    return runResults[0];
  }

  if (uniqueStatuses.size === 1 && uniqueStatuses.has("passed")) {
    return {
      ...runResults[runResults.length - 1],
      status: "passed",
      flaky: false,
      runs: runResults,
    };
  }

  if (uniqueStatuses.size === 1 && uniqueStatuses.has("failed")) {
    return {
      ...runResults[runResults.length - 1],
      status: "failed",
      flaky: false,
      runs: runResults,
    };
  }

  return {
    ...runResults[runResults.length - 1],
    status: "flaky",
    flaky: true,
    runs: runResults,
    rootCause: {
      title: "Flaky behavior detected",
      summary:
        "The same instruction produced mixed pass/fail results across reruns.",
      likelyCause:
        "The test may depend on timing, async UI updates, animations, or nondeterministic app state.",
      recommendation:
        "Stabilize the UI wait condition or add a more reliable assertion before treating this as a regression.",
      evidence: statuses
        .map((status, index) => `Run ${index + 1}: ${status}`)
        .join(", "),
    },
  };
}
