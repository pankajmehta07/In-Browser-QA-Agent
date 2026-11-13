import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const currentFilePath = fileURLToPath(import.meta.url);
const currentDirectory = path.dirname(currentFilePath);
const dataDirectory = path.join(currentDirectory, "..", "data");
const testsFilePath = path.join(dataDirectory, "tests.json");

export async function saveTest(test) {
  await ensureStore();

  const tests = await listTests();

  const savedTest = {
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...test,
  };

  tests.unshift(savedTest);

  await fs.writeFile(
    testsFilePath,
    JSON.stringify(tests.slice(0, 100), null, 2),
  );

  return savedTest;
}

export async function listTests() {
  await ensureStore();

  const raw = await fs.readFile(testsFilePath, "utf8");

  if (!raw.trim()) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    await fs.writeFile(testsFilePath, "[]");
    return [];
  }
}

export async function deleteTest(testId) {
  await ensureStore();

  const tests = await listTests();
  const remainingTests = tests.filter((test) => test.id !== testId);

  if (remainingTests.length === tests.length) {
    return false;
  }

  await fs.writeFile(testsFilePath, JSON.stringify(remainingTests, null, 2));

  return true;
}

async function ensureStore() {
  await fs.mkdir(dataDirectory, { recursive: true });

  try {
    await fs.access(testsFilePath);
  } catch {
    await fs.writeFile(testsFilePath, "[]");
  }
}
