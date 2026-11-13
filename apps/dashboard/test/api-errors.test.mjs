import assert from "node:assert/strict";
import { before, after, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium } from "@playwright/test";

let server, browser, baseUrl;

before(async () => {
  server = await createServer({ configFile: false, root: fileURLToPath(new URL("../", import.meta.url)),
    logLevel: "silent", server: { host: "127.0.0.1", port: 0 } });
  await server.listen();
  baseUrl = `http://127.0.0.1:${server.httpServer.address().port}`;
  browser = await chromium.launch({ headless: true,
    ...(process.env.BROWSERQA_TEST_CHANNEL ? { channel: process.env.BROWSERQA_TEST_CHANNEL } : {}) });
});

after(async () => {
  await browser?.close();
  await server?.close();
});

async function request(t, response, options = {}) {
  const context = await browser.newContext();
  t.after(() => context.close());
  const page = await context.newPage();
  // Load only the real API module, not the dashboard or any real backend.
  await page.route("**/client-test", route => route.fulfill({ contentType: "text/html", body: "<!doctype html><title>API contract</title>" }));
  let calls = 0;
  await page.route("**/api/contract-test", async route => {
    calls++;
    if (options.networkFailure) return route.abort("failed");
    return route.fulfill({ status: response.status, contentType: response.contentType || "application/json",
      body: typeof response.body === "string" ? response.body : JSON.stringify(response.body) });
  });
  await page.goto(`${baseUrl}/client-test`);
  const outcome = await page.evaluate(async () => {
    const { apiRequest, ApiRequestError } = await import("/src/api.js");
    try {
      return { value: await apiRequest("/contract-test", { method: "POST" }) };
    } catch (error) {
      return { message: error.message, status: error.status, body: error.body,
        typed: typeof ApiRequestError === "function" && error instanceof ApiRequestError };
    }
  });
  return { outcome, calls };
}

test("503 retains the complete partial suite report without retrying", async t => {
  const report = { status: "incomplete", errorMessage: "Suite stopped early", safeToRetry: false,
    tests: [{ testId: "one", state: "completed", savedRunId: "saved-one" }, { testId: "two", state: "completed_unsaved" }] };
  const { outcome, calls } = await request(t, { status: 503, body: report });
  assert.equal(outcome.status, 503);
  assert.deepEqual(outcome.body, report);
  assert.equal(outcome.message, "Suite stopped early");
  assert.equal(outcome.typed, true);
  assert.equal(calls, 1);
});

test("409 retains current revision for explicit conflict handling", async t => {
  const body = { status: "failed", currentRevision: 3, errorMessage: "Reload before saving" };
  const { outcome, calls } = await request(t, { status: 409, body });
  assert.equal(outcome.status, 409);
  assert.deepEqual(outcome.body, body);
  assert.equal(outcome.message, "Reload before saving");
  assert.equal(calls, 1);
});

test("successful JSON keeps the existing result contract", async t => {
  const body = { id: "saved", revision: 2 };
  const { outcome, calls } = await request(t, { status: 200, body });
  assert.deepEqual(outcome.value, body);
  assert.equal(calls, 1);
});

test("non-JSON errors retain status without exposing raw HTML", async t => {
  const { outcome } = await request(t, { status: 502, contentType: "text/html", body: "<html>private proxy diagnostic</html>" });
  assert.equal(outcome.status, 502);
  assert.equal(outcome.body, null);
  assert.equal(outcome.message, "Request failed with status 502.");
  assert.equal(outcome.typed, true);
});

test("malformed JSON produces a bounded error with the HTTP status", async t => {
  const { outcome, calls } = await request(t, { status: 503, body: "{private invalid JSON" });
  assert.equal(outcome.status, 503);
  assert.equal(outcome.body, null);
  assert.equal(outcome.typed, true);
  assert.match(outcome.message, /invalid JSON/i);
  assert.doesNotMatch(outcome.message, /private/);
  assert.equal(calls, 1);
});

test("network failures preserve legacy message and never replay a POST", async t => {
  const { outcome, calls } = await request(t, {}, { networkFailure: true });
  assert.equal(outcome.status, null);
  assert.equal(outcome.body, null);
  assert.equal(outcome.typed, true);
  assert.match(outcome.message, /QA service is unavailable/);
  assert.equal(calls, 1);
});
