export function classifyRerunResults(runResults) {
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