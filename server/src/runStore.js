import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const currentFilePath = fileURLToPath(import.meta.url);
const currentDirectory = path.dirname(currentFilePath);
const dataDirectory = path.join(currentDirectory, "..", "data");
const runsFilePath = path.join(dataDirectory, "runs.json");

export async function saveRun(run) {
  await ensureStore();

  const runs = await listRuns();

  const savedRun = {
    id: crypto.randomUUID(),
    savedAt: new Date().toISOString(),
    ...summarizeRun(run),
    result: run,
  };

  runs.unshift(savedRun);

  await fs.writeFile(runsFilePath, JSON.stringify(runs.slice(0, 50), null, 2));

  return savedRun;
}

export async function listRuns() {
  await ensureStore();

  const raw = await fs.readFile(runsFilePath, "utf8");

  if (!raw.trim()) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    await fs.writeFile(runsFilePath, "[]");
    return [];
  }
}

async function ensureStore() {
  await fs.mkdir(dataDirectory, { recursive: true });

  try {
    await fs.access(runsFilePath);
  } catch {
    await fs.writeFile(runsFilePath, "[]");
  }
}

function summarizeRun(run) {
  const steps = run.steps || [];
  const healedSteps = steps.filter((step) => step.wasHealed);
  const totalCostUsd = steps.reduce(
    (total, step) => total + (step.estimatedCostUsd || 0),
    0,
  );

  return {
    status: run.status,
    flaky: Boolean(run.flaky),
    durationMs: run.durationMs,
    runCount: run.runs ? run.runs.length : 1,
    healedCount: healedSteps.length,
    wasHealed: healedSteps.length > 0,
    totalCostUsd,
    rootCauseTitle: run.rootCause?.title || null,
    accessibilityIssueCount: run.accessibilityAudit?.issueCount || 0,
    accessibilityWarningCount: run.accessibilityAudit?.warningCount || 0,
  };
}
