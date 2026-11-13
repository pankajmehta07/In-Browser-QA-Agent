export function explainFailure(result) {
  if (result.status !== "failed") {
    return null;
  }

  const failedStep = result.steps.find((step) => step.status === "failed");

  if (!failedStep) {
    return {
      title: "Test failed before step logging",
      summary:
        "The test failed before the runner could record a specific failed step.",
      likelyCause: result.errorMessage || "Unknown failure",
      recommendation:
        "Check the backend logs and confirm the target app is running.",
    };
  }

  if (failedStep.resolutionStrategy === "unresolved") {
    const failedAttemptNames = (failedStep.resolutionAttempts || [])
      .map((attempt) => `${attempt.tier}: ${attempt.status}`)
      .join(", ");

    const estimatedCost = (failedStep.resolutionAttempts || []).reduce(
      (total, attempt) => total + (attempt.estimatedCostUsd || 0),
      0,
    );

    return {
      title: "Element could not be resolved",
      summary: `The agent could not find a reliable replacement for "${extractTargetFromStepName(
        failedStep.name,
      )}".`,
      likelyCause:
        "The expected UI element may have been renamed, removed, hidden, or changed too much for the free resolver tiers.",
      recommendation:
        "Check the target page manually. If the UI change is intentional, update the instruction or connect the LLM/vision fallback.",
      evidence: `${failedAttemptNames}. Estimated escalation cost: $${estimatedCost.toFixed(
        4,
      )}`,
    };
  }

  if (failedStep.name.toLowerCase().startsWith("check")) {
    return {
      title: "Assertion failed",
      summary: `The test reached the page, but this check failed: "${failedStep.name}".`,
      likelyCause:
        "The expected text or field value was not visible or did not match the instruction.",
      recommendation:
        "Confirm whether the app behavior changed or the test expectation is outdated.",
      evidence: failedStep.errorMessage,
    };
  }

  return {
    title: "Step execution failed",
    summary: `The test failed while running: "${failedStep.name}".`,
    likelyCause: "The page did not match the expected state for this action.",
    recommendation:
      "Review the failed step, selector details, and accessibility snapshot.",
    evidence: failedStep.errorMessage || result.errorMessage,
  };
}

function extractTargetFromStepName(stepName) {
  return stepName.replace(/^Click\s+/i, "").trim();
}
