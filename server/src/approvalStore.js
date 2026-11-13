import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const currentFilePath = fileURLToPath(import.meta.url);
const currentDirectory = path.dirname(currentFilePath);
const dataDirectory = path.join(currentDirectory, "..", "data");
const approvalsFilePath = path.join(dataDirectory, "approvals.json");

export async function saveApproval(approval) {
  await ensureStore();

  const approvals = await listApprovals();

  const savedApproval = {
    id: crypto.randomUUID(),
    savedAt: new Date().toISOString(),
    ...approval
  };

  approvals.unshift(savedApproval);

  await fs.writeFile(
    approvalsFilePath,
    JSON.stringify(approvals.slice(0, 100), null, 2)
  );

  return savedApproval;
}

export async function listApprovals() {
  await ensureStore();

  const raw = await fs.readFile(approvalsFilePath, "utf8");

  if (!raw.trim()) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    await fs.writeFile(approvalsFilePath, "[]");
    return [];
  }
}

async function ensureStore() {
  await fs.mkdir(dataDirectory, { recursive: true });

  try {
    await fs.access(approvalsFilePath);
  } catch {
    await fs.writeFile(approvalsFilePath, "[]");
  }
}

export async function findApprovedMapping(oldTarget) {
  const approvals = await listApprovals();

  return approvals.find(
    (approval) =>
      approval.decision === "approved" &&
      normalize(approval.oldTarget) === normalize(oldTarget)
  );
}

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}