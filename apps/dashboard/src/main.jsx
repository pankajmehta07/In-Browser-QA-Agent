import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const defaultInstruction = `Go to Login.
Type user@example.com into Email.
Type password123 into Password.
Click Login.
Check that Dashboard is visible.
Click Settings.
Check that Email contains user@example.com.`;

function formatConfidence(value) {
  if (typeof value !== "number") {
    return "n/a";
  }

  return `${Math.round(value * 100)}%`;
}

function getApprovalKey(step) {
  return `${step.name}-${step.oldSelector}-${step.newSelector}`;
}

function formatCost(value) {
  if (typeof value !== "number") {
    return "$0.00";
  }

  return `$${value.toFixed(4)}`;
}

function extractTargetFromSelector(selector) {
  if (!selector) {
    return null;
  }

  const match = selector.match(/name="([^"]+)"/);
  return match ? match[1] : selector;
}

function App() {
  const [instruction, setInstruction] = useState(defaultInstruction);
  const [variant, setVariant] = useState("original");
  const [reruns, setReruns] = useState(1);
  const [result, setResult] = useState(null);
  const [runs, setRuns] = useState([]);
  const [tests, setTests] = useState([]);
  const [testName, setTestName] = useState("Login and verify settings email");
  const [selectedRun, setSelectedRun] = useState(null);
  const [approvalDecisions, setApprovalDecisions] = useState({});
  const [isRunning, setIsRunning] = useState(false);

  useEffect(() => {
    loadRuns();
    loadTests();
  }, []);

  async function loadRuns() {
    try {
      const response = await fetch("http://127.0.0.1:4000/runs");
      const data = await response.json();
      setRuns(data);
    } catch (error) {
      console.error(error);
    }
  }

  async function loadTests() {
    try {
      const response = await fetch("http://127.0.0.1:4000/tests");
      const data = await response.json();
      setTests(data);
    } catch (error) {
      console.error(error);
    }
  }

  async function loadRunDetail(runId) {
    try {
      const response = await fetch(`http://127.0.0.1:4000/runs/${runId}`);
      const data = await response.json();
      setSelectedRun(data);
    } catch (error) {
      console.error(error);
    }
  }

  async function submitApproval(step, decision) {
    if (!result?.savedRunId) {
      return;
    }

    const response = await fetch("http://127.0.0.1:4000/approvals", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        runId: result.savedRunId,
        stepName: step.name,
        oldSelector: step.oldSelector,
        newSelector: step.newSelector,
        oldTarget: extractTargetFromSelector(step.oldSelector),
        newTarget: extractTargetFromSelector(step.newSelector),
        decision,
        confidence: step.confidence,
        strategy: step.resolutionStrategy,
      }),
    });

    await response.json();
    await loadRuns();

    setApprovalDecisions((current) => ({
      ...current,
      [getApprovalKey(step)]: decision,
    }));

    setResult((current) => ({
      ...current,
      approvalMessage:
        decision === "approved"
          ? "Selector change approved."
          : "Selector change rejected.",
    }));
  }

  async function saveCurrentTest() {
    const response = await fetch("http://127.0.0.1:4000/tests", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: testName,
        instruction,
        variant,
        reruns,
      }),
    });

    await response.json();
    await loadTests();
  }

  async function runSavedTest(test) {
    setTestName(test.name);
    setInstruction(test.instruction);
    setVariant(test.variant || "original");
    setReruns(test.reruns || 1);

    setIsRunning(true);
    setResult(null);

    try {
      const response = await fetch("http://127.0.0.1:4000/run-instruction", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          instruction: test.instruction,
          variant: test.variant || "original",
          reruns: test.reruns || 1,
        }),
      });

      const data = await response.json();
      setResult(data);
      await loadRuns();
    } catch (error) {
      setResult({
        status: "failed",
        errorMessage: error.message,
        steps: [],
      });
    } finally {
      setIsRunning(false);
    }
  }

  async function runInstruction() {
    setIsRunning(true);
    setResult(null);

    try {
      const response = await fetch("http://127.0.0.1:4000/run-instruction", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ instruction, variant, reruns }),
      });

      const data = await response.json();
      setResult(data);
      await loadRuns();
    } catch (error) {
      setResult({
        status: "failed",
        errorMessage: error.message,
        steps: [],
      });
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main className="dashboard-shell">
      <section className="workspace">
        <div className="intro">
          <p className="eyebrow">In-Browser QA Agent</p>
          <h1>Natural-language browser testing</h1>
          <p>
            Write a supported instruction, run it in Chromium, and inspect the
            generated steps.
          </p>
        </div>

        <div className="layout">
          <section className="panel">
            <div className="panel-heading">
              <h2>Instruction</h2>
              <div className="button-group">
                <button type="button" onClick={saveCurrentTest}>
                  Save Test
                </button>

                <button
                  type="button"
                  onClick={runInstruction}
                  disabled={isRunning}
                >
                  {isRunning ? "Running..." : "Generate and Run"}
                </button>
              </div>
            </div>

            <div className="control-row">
              <label htmlFor="test-name">Test Name</label>
              <input
                id="test-name"
                value={testName}
                onChange={(event) => setTestName(event.target.value)}
              />
            </div>

            <div className="control-row">
              <label htmlFor="variant">Target DOM</label>
              <select
                id="variant"
                value={variant}
                onChange={(event) => setVariant(event.target.value)}
              >
                <option value="original">Original: Login button</option>
                <option value="changed">Changed: Sign In button</option>
                <option value="flaky">Flaky: random Login/Delete button</option>
              </select>
            </div>

            <div className="control-row">
              <label htmlFor="reruns">Reruns</label>
              <select
                id="reruns"
                value={reruns}
                onChange={(event) => setReruns(Number(event.target.value))}
              >
                <option value={1}>1 run</option>
                <option value={3}>3 runs</option>
                <option value={5}>5 runs</option>
              </select>
            </div>

            <textarea
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              spellCheck="false"
            />
          </section>
          <section className="panel">
            <h2>Result</h2>

            {!result && (
              <p className="muted">
                Run the test to see pass/fail status and step details.
              </p>
            )}

            {result && (
              <div>
                <div className={`status ${result.status}`}>
                  Status: {result.status.toUpperCase()}
                </div>

                {result.runs && (
                  <div className="rerun-summary">
                    {result.runs.map((run) => (
                      <span
                        className={`pill ${run.status}`}
                        key={run.runNumber}
                      >
                        Run {run.runNumber}: {run.status}
                      </span>
                    ))}
                  </div>
                )}

                {result.durationMs && (
                  <p className="muted">Duration: {result.durationMs}ms</p>
                )}

                {result.approvalMessage && (
                  <p className="approval-message">{result.approvalMessage}</p>
                )}

                {result.errorMessage && (
                  <pre className="error-box">{result.errorMessage}</pre>
                )}

                {result.screenshot && (
                  <section className="screenshot-box">
                    <h3>Failure Screenshot</h3>
                    <img
                      src={`http://127.0.0.1:4000${result.screenshot.urlPath}`}
                      alt="Failure screenshot"
                    />
                  </section>
                )}

                {result.rootCause && (
                  <section className="root-cause">
                    <h3>Root Cause</h3>
                    <strong>{result.rootCause.title}</strong>
                    <p>{result.rootCause.summary}</p>

                    <dl>
                      <div>
                        <dt>Likely cause</dt>
                        <dd>{result.rootCause.likelyCause}</dd>
                      </div>

                      <div>
                        <dt>Recommendation</dt>
                        <dd>{result.rootCause.recommendation}</dd>
                      </div>

                      {result.rootCause.evidence && (
                        <div>
                          <dt>Evidence</dt>
                          <dd>{result.rootCause.evidence}</dd>
                        </div>
                      )}
                    </dl>
                  </section>
                )}

                {result.accessibilityAudit && (
                  <section className="audit-box">
                    <h3>Accessibility & Testability Audit</h3>

                    <div
                      className={`audit-status ${result.accessibilityAudit.status}`}
                    >
                      {result.accessibilityAudit.status === "passed"
                        ? "No blocking accessibility issues found"
                        : "Accessibility needs attention"}
                    </div>

                    <p className="muted">
                      Issues: {result.accessibilityAudit.issueCount} · Warnings:{" "}
                      {result.accessibilityAudit.warningCount}
                    </p>

                    {[
                      ...result.accessibilityAudit.issues,
                      ...result.accessibilityAudit.warnings,
                    ].length > 0 && (
                      <div className="audit-list">
                        {[
                          ...result.accessibilityAudit.issues,
                          ...result.accessibilityAudit.warnings,
                        ].map((item, index) => (
                          <article
                            className="audit-item"
                            key={`${item.rule}-${index}`}
                          >
                            <strong>{item.rule}</strong>
                            <p>{item.message}</p>
                            <code>{item.selector}</code>
                          </article>
                        ))}
                      </div>
                    )}
                  </section>
                )}

                {result.steps && (
                  <>
                    <h3>Execution Log</h3>
                    <div className="step-list">
                      {result.steps.map((step, index) => (
                        <article
                          className="step-item"
                          key={`${step.name}-${index}`}
                        >
                          <div className="step-main">
                            <div className="step-title-row">
                              <strong>{step.name}</strong>
                              {step.wasHealed && (
                                <span className="heal-badge">Healed</span>
                              )}
                            </div>

                            <p>{step.durationMs}ms</p>

                            {step.selectorUsed && (
                              <dl className="step-details">
                                <div>
                                  <dt>Selector</dt>
                                  <dd>{step.selectorUsed}</dd>
                                </div>

                                <div>
                                  <dt>Strategy</dt>
                                  <dd>{step.resolutionStrategy}</dd>
                                </div>

                                <div>
                                  <dt>Confidence</dt>
                                  <dd>{formatConfidence(step.confidence)}</dd>
                                </div>

                                <div>
                                  <dt>Cost</dt>
                                  <dd>{formatCost(step.estimatedCostUsd)}</dd>
                                </div>

                                {step.wasHealed && (
                                  <>
                                    <div>
                                      <dt>Old</dt>
                                      <dd>{step.oldSelector}</dd>
                                    </div>

                                    <div>
                                      <dt>New</dt>
                                      <dd>{step.newSelector}</dd>
                                    </div>

                                    <div>
                                      <dt>Diff</dt>
                                      <dd>
                                        {extractTargetFromSelector(
                                          step.oldSelector,
                                        )}{" "}
                                        →{" "}
                                        {extractTargetFromSelector(
                                          step.newSelector,
                                        )}
                                      </dd>
                                    </div>
                                  </>
                                )}
                              </dl>
                            )}

                            {step.wasHealed && (
                              <div className="approval-actions">
                                {approvalDecisions[getApprovalKey(step)] ? (
                                  <span className="approval-message">
                                    {approvalDecisions[getApprovalKey(step)] ===
                                    "approved"
                                      ? "Approved for future memory"
                                      : "Rejected"}
                                  </span>
                                ) : (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        submitApproval(step, "approved")
                                      }
                                    >
                                      Approve
                                    </button>

                                    <button
                                      className="secondary-button"
                                      type="button"
                                      onClick={() =>
                                        submitApproval(step, "rejected")
                                      }
                                    >
                                      Reject
                                    </button>
                                  </>
                                )}
                              </div>
                            )}

                            {step.resolutionAttempts && (
                              <details className="attempts">
                                <summary>Resolution ladder</summary>

                                <ol>
                                  {step.resolutionAttempts.map(
                                    (attempt, attemptIndex) => (
                                      <li
                                        key={`${attempt.tier}-${attemptIndex}`}
                                      >
                                        <span
                                          className={`attempt-status ${attempt.status}`}
                                        >
                                          {attempt.status}
                                        </span>

                                        <span>
                                          <strong>{attempt.tier}</strong>
                                          <small>{attempt.description}</small>
                                        </span>

                                        <span>
                                          {formatCost(attempt.estimatedCostUsd)}
                                        </span>
                                      </li>
                                    ),
                                  )}
                                </ol>
                              </details>
                            )}
                          </div>

                          <span className={`pill ${step.status}`}>
                            {step.status}
                          </span>
                        </article>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </section>
          
          <section className="panel saved-tests-panel">
            <div className="panel-heading">
              <h2>Saved Tests</h2>
              <button type="button" onClick={loadTests}>
                Refresh
              </button>
            </div>

            {tests.length === 0 && <p className="muted">No saved tests yet.</p>}

            {tests.length > 0 && (
              <div className="saved-test-list">
                {tests.slice(0, 10).map((test) => (
                  <article className="saved-test-item" key={test.id}>
                    <div>
                      <strong>{test.name}</strong>
                      <p>
                        {test.variant || "original"} · {test.reruns || 1} run
                        {(test.reruns || 1) === 1 ? "" : "s"}
                      </p>
                    </div>

                    <button type="button" onClick={() => runSavedTest(test)}>
                      Run
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="panel history-panel">
            <div className="panel-heading">
              <h2>Recent Runs</h2>
              <button type="button" onClick={loadRuns}>
                Refresh
              </button>
            </div>
            {selectedRun && (
              <section className="panel history-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Saved Run Detail</h2>
                    <p className="muted">
                      {new Date(selectedRun.savedAt).toLocaleString()}
                    </p>
                  </div>

                  <button type="button" onClick={() => setSelectedRun(null)}>
                    Close
                  </button>
                </div>

                <div className={`status ${selectedRun.status}`}>
                  Status: {selectedRun.status.toUpperCase()}
                </div>

                {selectedRun.result?.screenshot && (
                  <section className="screenshot-box">
                    <h3>Failure Screenshot</h3>
                    <img
                      src={`http://127.0.0.1:4000${selectedRun.result.screenshot.urlPath}`}
                      alt="Saved failure screenshot"
                    />
                  </section>
                )}

                {selectedRun.result?.rootCause && (
                  <section className="root-cause">
                    <h3>Root Cause</h3>
                    <strong>{selectedRun.result.rootCause.title}</strong>
                    <p>{selectedRun.result.rootCause.summary}</p>
                  </section>
                )}

                {selectedRun.result?.accessibilityAudit && (
                  <section className="audit-box">
                    <h3>Accessibility & Testability Audit</h3>
                    <div
                      className={`audit-status ${selectedRun.result.accessibilityAudit.status}`}
                    >
                      {selectedRun.result.accessibilityAudit.status === "passed"
                        ? "No blocking accessibility issues found"
                        : "Review recommended"}
                    </div>
                    <p className="muted">
                      Issues: {selectedRun.result.accessibilityAudit.issueCount}{" "}
                      / Warnings:{" "}
                      {selectedRun.result.accessibilityAudit.warningCount}
                    </p>
                  </section>
                )}

                {selectedRun.result?.generatedSteps && (
                  <>
                    <h3>Generated Steps</h3>
                    <pre>
                      {JSON.stringify(
                        selectedRun.result.generatedSteps,
                        null,
                        2,
                      )}
                    </pre>
                  </>
                )}

                {selectedRun.result?.steps && (
                  <>
                    <h3>Execution Log</h3>
                    <div className="step-list">
                      {selectedRun.result.steps.map((step, index) => (
                        <article
                          className="step-item"
                          key={`${step.name}-${index}`}
                        >
                          <div className="step-main">
                            <div className="step-title-row">
                              <strong>{step.name}</strong>
                              {step.wasHealed && (
                                <span className="heal-badge">Healed</span>
                              )}
                            </div>

                            <p>{step.durationMs}ms</p>

                            {step.selectorUsed && (
                              <dl className="step-details">
                                <div>
                                  <dt>Selector</dt>
                                  <dd>{step.selectorUsed}</dd>
                                </div>
                                <div>
                                  <dt>Strategy</dt>
                                  <dd>{step.resolutionStrategy}</dd>
                                </div>
                                <div>
                                  <dt>Confidence</dt>
                                  <dd>{formatConfidence(step.confidence)}</dd>
                                </div>
                                <div>
                                  <dt>Cost</dt>
                                  <dd>{formatCost(step.estimatedCostUsd)}</dd>
                                </div>
                              </dl>
                            )}
                          </div>

                          <span className={`pill ${step.status}`}>
                            {step.status}
                          </span>
                        </article>
                      ))}
                    </div>
                  </>
                )}
              </section>
            )}

            {runs.length === 0 && <p className="muted">No saved runs yet.</p>}

            {runs.length > 0 && (
              <div className="history-list">
                {runs.slice(0, 10).map((run) => (
                  <article
                    className={`history-item ${
                      selectedRun?.id === run.id ? "selected-history-item" : ""
                    }`}
                    key={run.id}
                    onClick={() => loadRunDetail(run.id)}
                  >
                    <div>
                      <strong>{new Date(run.savedAt).toLocaleString()}</strong>
                      <p>
                        {run.durationMs}ms · {run.runCount} run
                        {run.runCount === 1 ? "" : "s"} · cost{" "}
                        {formatCost(run.totalCostUsd)} · a11y{" "}
                        {run.accessibilityIssueCount || 0} issues /{" "}
                        {run.accessibilityWarningCount || 0} warnings
                      </p>
                    </div>

                    <div className="history-badges">
                      <span className={`pill ${run.status}`}>{run.status}</span>
                      {run.wasHealed && (
                        <span className="heal-badge">Healed</span>
                      )}
                      {run.flaky && <span className="heal-badge">Flaky</span>}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
