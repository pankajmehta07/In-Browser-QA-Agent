import assert from "node:assert/strict";
import { before, after, test as nodeTest } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, expect } from "@playwright/test";

let server;
let browser;
let baseUrl;

const test = (name, run) => nodeTest(name, { timeout: 15000 }, run);

before(async () => {
  server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL("../", import.meta.url)),
    logLevel: "silent",
    server: { host: "127.0.0.1", port: 0 },
  });
  await server.listen();
  baseUrl = `http://127.0.0.1:${server.httpServer.address().port}`;
  browser = await chromium.launch({ headless: true,
    ...(process.env.BROWSERQA_TEST_CHANNEL ? { channel: process.env.BROWSERQA_TEST_CHANNEL } : {}),
  });
});

after(async () => {
  await browser?.close();
  await server?.close();
});

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

async function dashboard(t, options = {}) {
  const context = await browser.newContext();
  t.after(() => context.close());
  const page = await context.newPage();
  page.setDefaultTimeout(4000);
  const state = {
    tests: [
      { id: "one", name: "First test", instruction: "Go to Projects.", variant: "original", reruns: 1 },
      { id: "two", name: "Second test", instruction: "Go to Users.", variant: "original", reruns: 1 },
    ],
    mutations: [],
    listCalls: 0,
    failSave: false,
    failDelete: false,
    failRefresh: false,
    ...options,
  };
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api", "");
    const method = request.method();
    if (method !== "GET") {
      state.mutations.push({ path, method, body: request.postDataJSON() });
      state.started?.resolve();
    }
    const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/health") return json({ status: "ok" });
    if (path === "/runs") return json([]);
    if (path === "/tests" && method === "GET") {
      state.listCalls++;
      if (state.failRefresh && state.listCalls > 1) return json({ errorMessage: "Library refresh failed" }, 500);
      return json(state.tests);
    }
    if (path === "/tests" && method === "POST") {
      state.started?.resolve();
      if (state.gate) await state.gate.promise;
      if (state.failSave) return json({ errorMessage: "Cannot save test" }, 500);
      const saved = { ...request.postDataJSON(), id: `saved-${state.tests.length}` };
      state.tests.push(saved);
      return json(saved, 201);
    }
    if (path.startsWith("/tests/") && method === "DELETE") {
      state.started?.resolve();
      if (state.gate) await state.gate.promise;
      if (state.failDelete) return json({ errorMessage: "Cannot delete test" }, 500);
      const id = path.split("/").at(-1);
      state.tests = state.tests.filter(item => item.id !== id);
      return json({ status: "passed", deletedId: id });
    }
    // Unexpected execution requests are recorded but never reach a real backend.
    return json({ status: "passed", steps: [] });
  });
  await page.goto(baseUrl);
  await expect(page.locator(".nav-count")).toHaveText("2");
  return { page, state };
}

async function library(page) {
  await page.getByRole("navigation").getByRole("button", { name: /Test Library/ }).click();
  await expect(page.getByRole("heading", { name: "Test Library", exact: true })).toBeVisible();
}

test("saving sends exactly one POST with the current test fields", async t => {
  const { page, state } = await dashboard(t);
  await page.getByLabel("Test name", { exact: true }).fill("  New regression  ");
  await page.getByLabel("Target DOM", { exact: true }).selectOption("changed");
  await page.getByLabel("Repeat", { exact: true }).selectOption("3");
  await page.getByLabel("Instructions", { exact: true }).fill("Go to Projects.\nClick New Project.");
  await page.getByRole("button", { name: "Save test", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Test saved to the library.");
  assert.equal(state.mutations.length, 1);
  assert.equal(state.mutations[0].path, "/tests");
  assert.equal(state.mutations[0].method, "POST");
  assert.equal(state.mutations[0].body.name, "New regression");
  assert.equal(state.mutations[0].body.instruction, "Go to Projects.\nClick New Project.");
  assert.equal(state.mutations[0].body.variant, "changed");
  assert.equal(state.mutations[0].body.reruns, 3);
  await library(page);
  await expect(page.locator("article.test-row")).toHaveCount(3);
});

test("saving rejects blank names and instructions without a request", async t => {
  const { page, state } = await dashboard(t);
  await page.getByLabel("Test name", { exact: true }).fill("   ");
  await page.getByRole("button", { name: "Save test", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("test name");
  await page.getByLabel("Test name", { exact: true }).fill("Valid name");
  await page.getByLabel("Instructions", { exact: true }).fill("   ");
  await page.getByRole("button", { name: "Save test", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("instructions");
  assert.deepEqual(state.mutations, []);
});

test("rapid save clicks are guarded until the request completes", async t => {
  const gate = deferred();
  const started = deferred();
  t.after(() => gate.resolve());
  const { page, state } = await dashboard(t, { gate, started });
  await page.getByRole("button", { name: "Save test", exact: true }).evaluate(button => { button.click(); button.click(); });
  await started.promise;
  await expect(page.getByRole("button", { name: "Saving...", exact: true })).toBeDisabled();
  gate.resolve();
  await expect(page.getByRole("status")).toHaveText("Test saved to the library.");
  assert.equal(state.mutations.length, 1);
  await expect(page.getByRole("button", { name: "Save test", exact: true })).toBeEnabled();
});

test("failed saves report the error and permit retry", async t => {
  const { page, state } = await dashboard(t, { failSave: true });
  await page.getByRole("button", { name: "Save test", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Cannot save test");
  assert.equal(state.mutations.length, 1);
  state.failSave = false;
  await page.getByRole("button", { name: "Save test", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Test saved to the library.");
  assert.equal(state.mutations.length, 2);
});

test("canceling deletion never mutates data or starts execution", async t => {
  const { page, state } = await dashboard(t);
  await library(page);
  await page.getByRole("button", { name: "Delete First test", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  assert.deepEqual(state.mutations, []);
});

test("confirmation deletes only the chosen test and clears its selection", async t => {
  const { page, state } = await dashboard(t);
  await library(page);
  await page.getByLabel("Select First test", { exact: true }).check();
  await page.getByRole("button", { name: "Delete First test", exact: true }).click();
  const request = page.waitForRequest(req => req.url().includes("/api/") && req.method() !== "GET");
  await page.getByRole("dialog").getByRole("button", { name: "Delete test", exact: true }).click();
  assert.equal((await request).method(), "DELETE");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator("article.test-row")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Run full suite", exact: true })).toBeVisible();
  assert.deepEqual(state.mutations.map(({ method, path }) => ({ method, path })), [{ method: "DELETE", path: "/tests/one" }]);
  assert.ok(state.listCalls > 1);
});

test("in-flight deletion blocks repeat clicks and dismissal", async t => {
  const gate = deferred();
  const started = deferred();
  t.after(() => gate.resolve());
  const { page, state } = await dashboard(t, { gate, started });
  await library(page);
  await page.getByRole("button", { name: "Delete First test", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete test", exact: true }).evaluate(button => { button.click(); button.click(); });
  await started.promise;
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "Deleting...", exact: true })).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "Cancel", exact: true })).toBeDisabled();
  await page.locator(".dialog-backdrop").click({ position: { x: 2, y: 2 } });
  await expect(dialog).toBeVisible();
  gate.resolve();
  await expect(dialog).toHaveCount(0);
  assert.equal(state.mutations.length, 1);
});

test("failed deletion keeps the record and dialog and allows retry", async t => {
  const { page, state } = await dashboard(t, { failDelete: true });
  await library(page);
  await page.getByRole("button", { name: "Delete First test", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Delete test", exact: true }).click();
  await expect(dialog.getByRole("alert")).toHaveText("Cannot delete test");
  await expect(page.locator("article.test-row")).toHaveCount(2);
  state.failDelete = false;
  await dialog.getByRole("button", { name: "Delete test", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  assert.deepEqual(state.mutations.map(item => item.path), ["/tests/one", "/tests/one"]);
});

test("successful deletion remains removed when the library refresh fails", async t => {
  const { page, state } = await dashboard(t, { failRefresh: true });
  await library(page);
  await page.getByRole("button", { name: "Delete First test", exact: true }).click();
  const request = page.waitForRequest(req => req.url().includes("/api/") && req.method() !== "GET");
  await page.getByRole("dialog").getByRole("button", { name: "Delete test", exact: true }).click();
  assert.equal((await request).method(), "DELETE");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator("article.test-row")).toHaveCount(1);
  await expect(page.getByRole("status")).toContainText("deleted");
  await expect(page.getByRole("status")).toContainText("refresh");
  assert.equal(state.mutations.length, 1);
});

test("a saved test with a failed refresh is reported as saved, not failed", async t => {
  const { page, state } = await dashboard(t, { failRefresh: true });
  await page.getByRole("button", { name: "Save test", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Test saved, but the library refresh failed.");
  await expect(page.getByRole("button", { name: "Save test", exact: true })).toBeEnabled();
  assert.equal(state.mutations.length, 1);
});

test("deletion preserves selection of other tests", async t => {
  const { page } = await dashboard(t);
  await library(page);
  await page.getByLabel("Select all visible tests").check();
  await page.getByRole("button", { name: "Delete First test", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete test", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByLabel("Select Second test", { exact: true })).toBeChecked();
  await expect(page.getByRole("button", { name: "Run selected (1)", exact: true })).toBeVisible();
});
