import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertCircle,
  Archive,
  BookOpenCheck,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  Code2,
  ExternalLink,
  FileSearch,
  FlaskConical,
  History,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  WandSparkles,
  X,
  XCircle,
} from "lucide-react";
import { API_BASE_URL, apiRequest, jsonRequest } from "./api.js";
import "./styles.css";

const defaultInstruction = `Go to Login.
Type user@example.com into Email.
Type password123 into Password.
Click Login.
Check that Dashboard is visible.
Go to QA Playground.
Clear Scenario Name.
Type Checkout regression into Scenario Name.
Select Critical from Priority.
Check Requires approval.
Check that Requires approval is checked.
Type Validate the checkout flow into Test Notes.
Press End in Test Notes.
Hover over Hover target.
Wait for Hover detected.
Double click Increment counter.
Check that Counter value has text 2.
Check that Archive scenario is disabled.`;

const grammarExamples = [
  "Go to Users", "Type Maya Chen into Name", "Clear Search users",
  "Click Add User", "Double click Increment counter",
  "Select Critical from Priority", "Check Requires approval",
  "Uncheck Weekly digest", "Press Enter in Search users",
  "Hover over Hover target", "Wait for Hover detected",
  "Check that Dashboard is visible", "Check that Add User is hidden",
  "Check that Email contains user@example.com",
  "Check that Counter value has text 2",
  "Check that Job Title equals QA Lead",
  "Check that Save Profile is enabled",
  "Check that Archive scenario is disabled",
  "Check that Weekly digest is checked",
  "Check that Weekly digest is unchecked",
];

const views = [
  { id: "runner", label: "Test Runner", icon: FlaskConical },
  { id: "tests", label: "Test Library", icon: BookOpenCheck },
  { id: "history", label: "Run History", icon: History },
];

function formatConfidence(value) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "n/a";
}

function formatCost(value) {
  return typeof value === "number" ? `$${value.toFixed(4)}` : "$0.0000";
}

function formatDuration(value) {
  if (!value) return "0 ms";
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${value} ms`;
}

function extractTargetFromSelector(selector) {
  if (!selector) return null;
  const match = selector.match(/name="([^"]+)"/);
  return match ? match[1] : selector;
}

function getApprovalKey(step) {
  return `${step.name}-${step.oldSelector}-${step.newSelector}`;
}

function App() {
  const [activeView, setActiveView] = useState("runner");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [instruction, setInstruction] = useState(defaultInstruction);
  const [variant, setVariant] = useState("original");
  const [reruns, setReruns] = useState(1);
  const [testName, setTestName] = useState("Expanded QA playground workflow");
  const [result, setResult] = useState(null);
  const [runs, setRuns] = useState([]);
  const [tests, setTests] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [selectedTestIds, setSelectedTestIds] = useState([]);
  const [approvalDecisions, setApprovalDecisions] = useState({});
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [serviceStatus, setServiceStatus] = useState("checking");
  const [testSearch, setTestSearch] = useState("");
  const [runFilter, setRunFilter] = useState("all");
  const [pendingDelete, setPendingDelete] = useState(null);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    initialize();
  }, []);

  useEffect(() => {
    function handleShortcut(event) {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        if (!isRunning && activeView === "runner") runInstruction();
      }
    }

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  });

  async function initialize() {
    setIsLoadingData(true);
    await Promise.all([checkService(), loadRuns(), loadTests()]);
    setIsLoadingData(false);
  }

  function notify(message, tone = "success") {
    setToast({ message, tone });
    window.setTimeout(() => setToast(null), 3000);
  }

  async function checkService() {
    try {
      await apiRequest("/health");
      setServiceStatus("online");
    } catch {
      setServiceStatus("offline");
    }
  }

  async function loadRuns() {
    try {
      setRuns((await apiRequest("/runs")) || []);
    } catch (error) {
      setServiceStatus("offline");
      notify(error.message, "error");
    }
  }

  async function loadTests() {
    try {
      setTests((await apiRequest("/tests")) || []);
    } catch (error) {
      setServiceStatus("offline");
      notify(error.message, "error");
    }
  }

  async function loadRunDetail(runId) {
    try {
      setSelectedRun(await apiRequest(`/runs/${runId}`));
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function saveCurrentTest() {
    if (!testName.trim() || !instruction.trim()) {
      notify("Add a test name and at least one instruction.", "error");
      return;
    }

    try {
      await apiRequest(
        "/tests",
        jsonRequest("POST", { name: testName.trim(), instruction, variant, reruns }),
      );
      await loadTests();
      notify("Test saved to the library.");
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function executeRequest(path, body) {
    setIsRunning(true);
    setResult(null);
    setActiveView("runner");

    try {
      const data = await apiRequest(path, jsonRequest("POST", body));
      setResult(data);
      setServiceStatus("online");
      await loadRuns();
    } catch (error) {
      setResult({ status: "failed", errorMessage: error.message, steps: [] });
      if (error.message.includes("unavailable")) setServiceStatus("offline");
    } finally {
      setIsRunning(false);
    }
  }

  async function runInstruction() {
    if (!instruction.trim()) {
      notify("Enter an instruction before running the test.", "error");
      return;
    }
    await executeRequest("/run-instruction", { instruction, variant, reruns });
  }

  async function runSavedTest(test) {
    setTestName(test.name);
    setInstruction(test.instruction);
    setVariant(test.variant || "original");
    setReruns(test.reruns || 1);
    await executeRequest("/run-instruction", {
      instruction: test.instruction,
      variant: test.variant || "original",
      reruns: test.reruns || 1,
    });
  }

  async function runTestSuite() {
    await executeRequest("/run-test-suite", {
      variant,
      reruns,
      testIds: selectedTestIds.length > 0 ? selectedTestIds : undefined,
    });
  }

  async function confirmDeleteTest() {
    if (!pendingDelete) return;
    try {
      await apiRequest(`/tests/${pendingDelete.id}`, { method: "DELETE" });
      setSelectedTestIds((current) => current.filter((id) => id !== pendingDelete.id));
      setPendingDelete(null);
      await loadTests();
      notify("Saved test deleted.");
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function submitApproval(step, decision) {
    if (!result?.savedRunId) return;
    try {
      await apiRequest(
        "/approvals",
        jsonRequest("POST", {
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
      );
      setApprovalDecisions((current) => ({
        ...current,
        [getApprovalKey(step)]: decision,
      }));
      notify(decision === "approved" ? "Selector saved to healing memory." : "Selector change rejected.");
      await loadRuns();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  const visibleTests = useMemo(() => {
    const query = testSearch.trim().toLowerCase();
    if (!query) return tests;
    return tests.filter((test) =>
      `${test.name} ${test.instruction}`.toLowerCase().includes(query),
    );
  }, [testSearch, tests]);

  const visibleRuns = useMemo(() => {
    if (runFilter === "all") return runs;
    if (runFilter === "healed") return runs.filter((run) => run.wasHealed);
    return runs.filter((run) => run.status === runFilter);
  }, [runFilter, runs]);

  const stats = useMemo(() => {
    const completed = runs.filter((run) => ["passed", "failed", "flaky"].includes(run.status));
    const passed = completed.filter((run) => run.status === "passed").length;
    return {
      total: completed.length,
      passRate: completed.length ? Math.round((passed / completed.length) * 100) : 0,
      healed: completed.filter((run) => run.wasHealed).length,
      saved: tests.length,
    };
  }, [runs, tests]);

  function changeView(view) {
    setActiveView(view);
    setMobileNavOpen(false);
  }

  return (
    <main className="app-shell">
      <aside className={`app-sidebar ${mobileNavOpen ? "open" : ""}`}>
        <div className="product-brand"><span><Sparkles size={18} /></span><div><strong>BrowserQA</strong><small>Agent Console</small></div></div>
        <button className="mobile-close icon-button" type="button" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}><X size={20} /></button>

        <nav aria-label="QA Agent navigation">
          <p className="nav-caption">Workspace</p>
          {views.map(({ id, label, icon: Icon }) => (
            <button className={activeView === id ? "active" : ""} type="button" key={id} onClick={() => changeView(id)}>
              <Icon size={18} />{label}
              {id === "tests" && tests.length > 0 && <span className="nav-count">{tests.length}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className={`service-card ${serviceStatus}`}>
            <span className="service-dot" />
            <div><strong>QA service</strong><small>{serviceStatus === "online" ? "Operational" : serviceStatus === "offline" ? "Unavailable" : "Checking"}</small></div>
            <button className="icon-button" type="button" title="Check service" aria-label="Check service" onClick={checkService}><RefreshCw size={15} /></button>
          </div>
          <a href="http://127.0.0.1:5173" target="_blank" rel="noreferrer"><ExternalLink size={16} />Open target app</a>
        </div>
      </aside>

      {mobileNavOpen && <button className="nav-backdrop" type="button" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}

      <section className="app-workspace">
        <header className="topbar">
          <div><button className="mobile-menu icon-button" type="button" aria-label="Open navigation" onClick={() => setMobileNavOpen(true)}><Menu size={20} /></button><span className="breadcrumb">QA Workspace</span><ChevronRight size={14} /><strong>{views.find((view) => view.id === activeView)?.label}</strong></div>
          <div className="topbar-actions"><span className={`environment-status ${serviceStatus}`}><span />{serviceStatus === "online" ? "Backend connected" : "Backend offline"}</span><a className="docs-link" href="https://playwright.dev/docs/locators" target="_blank" rel="noreferrer"><Code2 size={16} />Locator docs</a></div>
        </header>

        <div className="page-container">
          {activeView === "runner" && (
            <RunnerView
              instruction={instruction}
              setInstruction={setInstruction}
              variant={variant}
              setVariant={setVariant}
              reruns={reruns}
              setReruns={setReruns}
              testName={testName}
              setTestName={setTestName}
              result={result}
              isRunning={isRunning}
              stats={stats}
              saveCurrentTest={saveCurrentTest}
              runInstruction={runInstruction}
              runTestSuite={runTestSuite}
              submitApproval={submitApproval}
              approvalDecisions={approvalDecisions}
            />
          )}

          {activeView === "tests" && (
            <TestLibrary
              tests={visibleTests}
              totalTests={tests.length}
              search={testSearch}
              setSearch={setTestSearch}
              selectedIds={selectedTestIds}
              setSelectedIds={setSelectedTestIds}
              runSavedTest={runSavedTest}
              runSuite={runTestSuite}
              isRunning={isRunning}
              setPendingDelete={setPendingDelete}
              refresh={loadTests}
              createTest={() => changeView("runner")}
            />
          )}

          {activeView === "history" && (
            <RunHistory
              runs={visibleRuns}
              totalRuns={runs.length}
              filter={runFilter}
              setFilter={setRunFilter}
              selectedRun={selectedRun}
              setSelectedRun={setSelectedRun}
              loadRunDetail={loadRunDetail}
              refresh={loadRuns}
            />
          )}

          {isLoadingData && <div className="loading-overlay"><LoaderCircle size={22} className="spin" />Loading workspace...</div>}
        </div>
      </section>

      {pendingDelete && <ConfirmDialog title="Delete saved test?" description={`This will permanently remove "${pendingDelete.name}" from the test library.`} confirmLabel="Delete test" onCancel={() => setPendingDelete(null)} onConfirm={confirmDeleteTest} />}
      {toast && <Toast {...toast} />}
    </main>
  );
}

function RunnerView(props) {
  return (
    <>
      <PageHeader eyebrow="Automation workspace" title="Test Runner" description="Turn plain-language scenarios into observable browser tests." action={<button className="primary-action" type="button" onClick={props.runInstruction} disabled={props.isRunning}>{props.isRunning ? <LoaderCircle size={17} className="spin" /> : <Play size={17} />}{props.isRunning ? "Running test" : "Run test"}</button>} />

      <section className="stat-grid">
        <Stat icon={Activity} label="Total runs" value={props.stats.total} detail="Recorded executions" />
        <Stat icon={CheckCircle2} label="Pass rate" value={`${props.stats.passRate}%`} detail="Across recent runs" tone="success" />
        <Stat icon={WandSparkles} label="Healed runs" value={props.stats.healed} detail="Recovered automatically" tone="violet" />
        <Stat icon={Archive} label="Saved tests" value={props.stats.saved} detail="Ready for regression" tone="amber" />
      </section>

      <div className="runner-grid">
        <section className="surface composer-panel">
          <div className="surface-header"><div><h2>Test scenario</h2><p>One action per line using the supported instruction grammar.</p></div><span className="shortcut-hint">Ctrl + Enter to run</span></div>
          <div className="form-field"><label htmlFor="test-name">Test name</label><input id="test-name" value={props.testName} onChange={(event) => props.setTestName(event.target.value)} placeholder="Name this scenario" /></div>
          <div className="inline-fields"><div className="form-field"><label htmlFor="variant">Target DOM</label><select id="variant" value={props.variant} onChange={(event) => props.setVariant(event.target.value)}><option value="original">Original DOM</option><option value="changed">Changed DOM</option><option value="flaky">Flaky DOM</option></select></div><div className="form-field"><label htmlFor="reruns">Repeat</label><select id="reruns" value={props.reruns} onChange={(event) => props.setReruns(Number(event.target.value))}><option value={1}>1 run</option><option value={3}>3 runs</option><option value={5}>5 runs</option></select></div></div>
          <div className="form-field instruction-field"><label htmlFor="instruction">Instructions</label><textarea id="instruction" value={props.instruction} onChange={(event) => props.setInstruction(event.target.value)} spellCheck="false" /></div>
          <details className="grammar-guide"><summary>Supported actions <span>20 patterns</span></summary><div>{grammarExamples.map((example) => <button type="button" key={example} onClick={() => props.setInstruction((current) => `${current.trim()}\n${example}.`)}><code>{example}</code><Plus size={13} /></button>)}</div></details>
          <div className="composer-actions"><button className="secondary-button" type="button" onClick={props.saveCurrentTest}><Save size={16} />Save test</button><button className="secondary-button" type="button" onClick={props.runTestSuite} disabled={props.isRunning}><LayoutDashboard size={16} />Run saved suite</button><button type="button" onClick={props.runInstruction} disabled={props.isRunning}>{props.isRunning ? <LoaderCircle size={16} className="spin" /> : <Play size={16} />}{props.isRunning ? "Running" : "Generate and run"}</button></div>
        </section>

        <section className="surface result-panel">
          <div className="surface-header"><div><h2>Result inspector</h2><p>Execution evidence, healing decisions, and diagnostics.</p></div>{props.result && <StatusBadge status={props.result.status} />}</div>
          {props.isRunning ? <RunningState /> : props.result ? <ResultInspector result={props.result} onApprove={props.submitApproval} approvalDecisions={props.approvalDecisions} /> : <EmptyState icon={FileSearch} title="No run selected" description="Run the scenario to inspect generated steps and diagnostics here." />}
        </section>
      </div>
    </>
  );
}

function TestLibrary({ tests, totalTests, search, setSearch, selectedIds, setSelectedIds, runSavedTest, runSuite, isRunning, setPendingDelete, refresh, createTest }) {
  const allVisibleSelected = tests.length > 0 && tests.every((test) => selectedIds.includes(test.id));
  function toggle(id) {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }
  function toggleAll() {
    const visibleIds = tests.map((test) => test.id);
    setSelectedIds((current) => allVisibleSelected ? current.filter((id) => !visibleIds.includes(id)) : [...new Set([...current, ...visibleIds])]);
  }

  return <><PageHeader eyebrow="Regression assets" title="Test Library" description={`${totalTests} reusable scenarios available for individual or suite execution.`} action={<div className="header-actions"><button className="secondary-button icon-only" type="button" title="Refresh tests" aria-label="Refresh tests" onClick={refresh}><RefreshCw size={17} /></button><button type="button" onClick={createTest}><Plus size={17} />New test</button></div>} /><section className="surface library-surface"><div className="library-toolbar"><div className="search-box"><Search size={17} /><input aria-label="Search saved tests" placeholder="Search tests or instructions" value={search} onChange={(event) => setSearch(event.target.value)} /></div><button type="button" onClick={runSuite} disabled={isRunning || totalTests === 0}><Play size={16} />{selectedIds.length ? `Run selected (${selectedIds.length})` : "Run full suite"}</button></div>{tests.length === 0 ? <EmptyState icon={BookOpenCheck} title={search ? "No matching tests" : "No saved tests"} description={search ? "Try a different search term." : "Create and save a scenario from the Test Runner."} action={!search && <button type="button" onClick={createTest}><Plus size={16} />Create first test</button>} /> : <div className="test-table"><div className="test-row test-table-head"><input type="checkbox" aria-label="Select all visible tests" checked={allVisibleSelected} onChange={toggleAll} /><span>Test</span><span>Environment</span><span>Runs</span><span>Actions</span></div>{tests.map((test) => <article className="test-row" key={test.id}><input type="checkbox" aria-label={`Select ${test.name}`} checked={selectedIds.includes(test.id)} onChange={() => toggle(test.id)} /><div className="test-name-cell"><span className="test-icon"><FlaskConical size={17} /></span><div><strong>{test.name}</strong><small>{test.instruction.split(/\r?\n/).filter(Boolean).length} instruction steps</small></div></div><span className="environment-chip">{test.variant || "original"}</span><span>{test.reruns || 1}</span><div className="row-actions"><button className="table-action" type="button" title="Run test" onClick={() => runSavedTest(test)}><Play size={16} />Run</button><button className="icon-button danger-icon" type="button" title="Delete test" aria-label={`Delete ${test.name}`} onClick={() => setPendingDelete(test)}><Trash2 size={16} /></button></div></article>)}</div>}</section></>;
}

function RunHistory({ runs, totalRuns, filter, setFilter, selectedRun, setSelectedRun, loadRunDetail, refresh }) {
  return <><PageHeader eyebrow="Execution evidence" title="Run History" description={`${totalRuns} recorded runs with diagnostics and healing metadata.`} action={<button className="secondary-button" type="button" onClick={refresh}><RefreshCw size={16} />Refresh</button>} /><div className="history-layout"><section className="surface history-browser"><div className="filter-tabs" role="tablist" aria-label="Filter runs">{["all", "passed", "failed", "flaky", "healed"].map((option) => <button className={filter === option ? "active" : ""} type="button" key={option} onClick={() => setFilter(option)}>{option}</button>)}</div>{runs.length === 0 ? <EmptyState icon={History} title="No runs in this view" description="Execute a test or choose another status filter." /> : <div className="history-list">{runs.slice(0, 30).map((run) => <button className={`history-item ${selectedRun?.id === run.id ? "selected-history-item" : ""}`} type="button" key={run.id} onClick={() => loadRunDetail(run.id)}><span className={`run-marker ${run.status}`}><StatusIcon status={run.status} /></span><div className="history-copy"><strong>{new Date(run.savedAt).toLocaleString()}</strong><span>{formatDuration(run.durationMs)}<i />{run.runCount} run{run.runCount === 1 ? "" : "s"}<i />{formatCost(run.totalCostUsd)}</span></div><div className="history-badges"><StatusBadge status={run.status} />{run.wasHealed && <span className="healed-label"><WandSparkles size={12} />Healed</span>}</div><ChevronRight size={17} /></button>)}</div>}</section><section className="surface history-detail"><div className="surface-header"><div><h2>Run details</h2><p>{selectedRun ? new Date(selectedRun.savedAt).toLocaleString() : "Select a run to inspect"}</p></div>{selectedRun && <button className="icon-button" type="button" title="Close details" aria-label="Close details" onClick={() => setSelectedRun(null)}><X size={18} /></button>}</div>{selectedRun ? <ResultInspector result={selectedRun.result || selectedRun} compact /> : <EmptyState icon={FileSearch} title="Choose a run" description="Select a run from the list to inspect its steps and evidence." />}</section></div></>;
}

function ResultInspector({ result, onApprove, approvalDecisions = {}, compact = false }) {
  const steps = result.steps || [];
  return <div className={`result-content ${compact ? "compact" : ""}`}><div className="result-summary"><div><StatusBadge status={result.status} large /><span>{formatDuration(result.durationMs)}</span></div>{result.savedRunId && <code>{result.savedRunId.slice(0, 8)}</code>}</div>{result.runs && <div className="rerun-summary">{result.runs.map((run) => <span className={`pill ${run.status}`} key={run.runNumber}>Run {run.runNumber}: {run.status}</span>)}</div>}{result.errorMessage && <div className="error-banner"><AlertCircle size={18} /><div><strong>Execution failed</strong><pre>{result.errorMessage}</pre></div></div>}{result.screenshot && <section className="evidence-block"><SectionTitle icon={FileSearch} title="Failure screenshot" /><img className="failure-screenshot" src={`${API_BASE_URL}${result.screenshot.urlPath}`} alt="Browser state at failure" /></section>}{result.rootCause && <section className="diagnostic-card"><SectionTitle icon={AlertCircle} title="Root cause analysis" /><strong>{result.rootCause.title}</strong><p>{result.rootCause.summary}</p><dl><div><dt>Likely cause</dt><dd>{result.rootCause.likelyCause}</dd></div><div><dt>Recommendation</dt><dd>{result.rootCause.recommendation}</dd></div>{result.rootCause.evidence && <div><dt>Evidence</dt><dd>{result.rootCause.evidence}</dd></div>}</dl></section>}{result.accessibilityAudit && <AccessibilityAudit audit={result.accessibilityAudit} />}{result.type === "suite" && result.tests && <SuiteSummary result={result} />}{steps.length > 0 && <section className="evidence-block"><SectionTitle icon={Activity} title="Execution log" meta={`${steps.length} steps`} /><div className="step-list">{steps.map((step, index) => <StepItem key={`${step.name}-${index}`} step={step} onApprove={onApprove} decision={approvalDecisions[getApprovalKey(step)]} />)}</div></section>}{steps.length === 0 && !result.errorMessage && result.type !== "suite" && <EmptyState icon={CheckCircle2} title="Run completed" description="No individual execution steps were recorded." />}</div>;
}

function StepItem({ step, onApprove, decision }) {
  return <article className="step-item"><span className={`step-index ${step.status}`}>{step.status === "passed" ? <Check size={14} /> : <X size={14} />}</span><div className="step-main"><div className="step-title-row"><strong>{step.name}</strong>{step.wasHealed && <span className="healed-label"><WandSparkles size={12} />Healed</span>}</div><p>{formatDuration(step.durationMs)}</p>{step.selectorUsed && <dl className="step-details"><div><dt>Selector</dt><dd>{step.selectorUsed}</dd></div><div><dt>Strategy</dt><dd>{step.resolutionStrategy}</dd></div><div><dt>Confidence</dt><dd>{formatConfidence(step.confidence)}</dd></div><div><dt>Cost</dt><dd>{formatCost(step.estimatedCostUsd)}</dd></div>{step.wasHealed && <div><dt>Change</dt><dd>{extractTargetFromSelector(step.oldSelector)} -&gt; {extractTargetFromSelector(step.newSelector)}</dd></div>}</dl>}{step.wasHealed && onApprove && <div className="approval-actions">{decision ? <span className={`decision-label ${decision}`}>{decision === "approved" ? "Approved for memory" : "Rejected"}</span> : <><button type="button" onClick={() => onApprove(step, "approved")}><Check size={14} />Approve</button><button className="secondary-button" type="button" onClick={() => onApprove(step, "rejected")}><X size={14} />Reject</button></>}</div>}{step.resolutionAttempts?.length > 0 && <details className="attempts"><summary>Resolution ladder</summary><ol>{step.resolutionAttempts.map((attempt, index) => <li key={`${attempt.tier}-${index}`}><span className={`attempt-status ${attempt.status}`}>{attempt.status}</span><span><strong>{attempt.tier}</strong><small>{attempt.description}</small></span><span>{formatCost(attempt.estimatedCostUsd)}</span></li>)}</ol></details>}</div></article>;
}

function AccessibilityAudit({ audit }) {
  const findings = [...(audit.issues || []), ...(audit.warnings || [])];
  return <section className="audit-card"><SectionTitle icon={ShieldCheck} title="Accessibility audit" /><div className="audit-summary"><span className={`audit-status ${audit.status}`}>{audit.status === "passed" ? "No blocking issues" : "Review recommended"}</span><span>{audit.issueCount} issues</span><span>{audit.warningCount} warnings</span></div>{findings.length > 0 && <div className="audit-list">{findings.map((item, index) => <article className="audit-item" key={`${item.rule}-${index}`}><strong>{item.rule}</strong><p>{item.message}</p><code>{item.selector}</code></article>)}</div>}</section>;
}

function SuiteSummary({ result }) {
  return <section className="evidence-block"><SectionTitle icon={LayoutDashboard} title="Suite summary" /><div className="suite-stats"><span><strong>{result.testCount}</strong>Total</span><span className="success"><strong>{result.passedCount}</strong>Passed</span><span className="danger"><strong>{result.failedCount}</strong>Failed</span><span className="warning"><strong>{result.flakyCount}</strong>Flaky</span></div><div className="suite-list">{result.tests.map((test) => <div key={test.id}><span className={`run-marker ${test.status}`}><StatusIcon status={test.status} /></span><div><strong>{test.name}</strong><small>{formatDuration(test.durationMs)}</small></div><StatusBadge status={test.status} /></div>)}</div></section>;
}

function PageHeader({ eyebrow, title, description, action }) {
  return <header className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{action}</header>;
}

function Stat({ icon: Icon, label, value, detail, tone = "blue" }) {
  return <article className="stat-card"><span className={`stat-icon ${tone}`}><Icon size={18} /></span><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div></article>;
}

function StatusIcon({ status }) {
  if (status === "passed") return <CheckCircle2 size={16} />;
  if (status === "flaky") return <AlertCircle size={16} />;
  return <XCircle size={16} />;
}

function StatusBadge({ status = "failed", large = false }) {
  return <span className={`status-badge ${status} ${large ? "large" : ""}`}><StatusIcon status={status} />{status}</span>;
}

function SectionTitle({ icon: Icon, title, meta }) {
  return <div className="section-title"><div><Icon size={17} /><h3>{title}</h3></div>{meta && <span>{meta}</span>}</div>;
}

function EmptyState({ icon: Icon, title, description, action }) {
  return <div className="empty-state"><span><Icon size={22} /></span><h3>{title}</h3><p>{description}</p>{action}</div>;
}

function RunningState() {
  return <div className="running-state"><span className="runner-pulse"><LoaderCircle size={24} className="spin" /></span><h3>Running in Chromium</h3><p>The agent is executing your scenario and collecting evidence.</p><div><i /><i /><i /></div></div>;
}

function ConfirmDialog({ title, description, confirmLabel, onCancel, onConfirm }) {
  return <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel(); }}><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><span className="danger-dialog-icon"><Trash2 size={20} /></span><h2 id="confirm-title">{title}</h2><p>{description}</p><div><button className="secondary-button" type="button" onClick={onCancel}>Cancel</button><button className="danger-button" type="button" onClick={onConfirm}>{confirmLabel}</button></div></section></div>;
}

function Toast({ message, tone }) {
  return <div className={`toast ${tone}`} role="status">{tone === "error" ? <AlertCircle size={17} /> : <CheckCircle2 size={17} />}{message}</div>;
}

createRoot(document.getElementById("root")).render(<App />);
