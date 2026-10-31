import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";
import { parseInstruction } from "../src/parser.js";
import { runStructuredTest } from "../src/runner.js";
import { resolveButton } from "../src/resolver.js";
import { chromium } from "@playwright/test";

test("goto and click navigate via links without requiring a heading", async () => {
  const server = createServer((request, response) => {
    response.setHeader("Content-Type", "text/html");
    response.end(request.url === "/projects"
      ? "<p>Portfolio</p>"
      : '<a href="/projects">Projects</a><button onclick="location.href=\'/projects\'">Settings</button>');
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}/`;
  try {
    for (const instruction of [
      `goto Projects on ${url}`,
      `Go to ${url}\nClick Projects`,
      `Go to ${url}\nClick Settings`,
      `Go to ${url}\nClick Project`,
    ]) {
      const result = await runStructuredTest(parseInstruction(instruction), { headless: true });
      assert.equal(result.status, "passed", result.errorMessage);
      assert.equal(result.accessibility.final.some((node) => node.name === "Projects"), false);
      const lastStep = result.steps.at(-1);
      assert.equal(lastStep.selectorUsed, instruction.includes("Settings")
        ? 'role=button[name="Settings"]' : 'role=link[name="Projects"]');
    }
  } finally {
    await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});

test("duplicate links are accepted only for the same destination", async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    await page.setContent('<a href="#work">Projects</a><a href="about:blank#work">Projects</a>');
    const sameDestination = await resolveButton(page, "Projects");
    assert.ok(sameDestination.locator);
    await sameDestination.locator.click();
    assert.ok(page.url().endsWith("#work"));
    await page.setContent('<a href="#one">Projects</a><a href="#two">Projects</a>');
    const ambiguous = await resolveButton(page, "Projects");
    assert.equal(ambiguous.locator, null);
  } finally {
    await browser.close();
  }
});