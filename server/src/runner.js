import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect } from "@playwright/test";
import { extractAccessibilitySnapshot } from "./accessibility.js";
import { resolveButton } from "./resolver.js";

const targetAppBaseUrl = "http://127.0.0.1:5173";

const currentFilePath = fileURLToPath(import.meta.url);
const currentDirectory = path.dirname(currentFilePath);
const screenshotsDirectory = path.join(currentDirectory, "..", "data", "screenshots");


function getTargetAppUrl(variant = "original") {
  const url = new URL(targetAppBaseUrl);

  if (variant !== "original") {
    url.searchParams.set("variant", variant);
  }

  return url.toString();
}

export async function runHardcodedLoginTest() {
  const startedAt = new Date();
  const browser = await chromium.launch({
    headless: false,
    slowMo: 300,
  });

  const page = await browser.newPage();

  const steps = [];

  try {
    await page.goto(getTargetAppUrl());

    await runStep(steps, "Open login page", async () => {
      await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
    });

    await runStep(steps, "Type email", async () => {
      await page.getByLabel("Email").fill("user@example.com");
    });

    await runStep(steps, "Type password", async () => {
      await page.getByLabel("Password").fill("password123");
    });

    await runStep(steps, "Click Login", async () => {
      await page.getByRole("button", { name: "Login" }).click();
    });

    await runStep(steps, "Check Dashboard is visible", async () => {
      await expect(page.getByText("Dashboard")).toBeVisible();
    });

    await runStep(steps, "Click Settings", async () => {
      await page.getByRole("button", { name: "Settings" }).click();
    });

    await runStep(
      steps,
      "Check email field contains user@example.com",
      async () => {
        await expect(page.getByLabel("Email")).toHaveValue("user@example.com");
      },
    );

    const finishedAt = new Date();

    return {
      status: "passed",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      steps,
    };
  } catch (error) {
    const finishedAt = new Date();

    return {
      status: "failed",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      errorMessage: error.message,
      steps,
    };
  } finally {
    await browser.close();
  }
}

export async function runStructuredTest(stepsToRun, options = {}) {
  const startedAt = new Date();
  const browser = await chromium.launch({
    headless: false,
    slowMo: 300,
  });

  const page = await browser.newPage();

  const steps = [];
  let initialAccessibilitySnapshot = [];

  try {
    await page.goto(getTargetAppUrl(options.variant));

    initialAccessibilitySnapshot = await extractAccessibilitySnapshot(page);

    for (const step of stepsToRun) {
      await executeStructuredStep(page, steps, step);
    }

    const finalAccessibilitySnapshot = await extractAccessibilitySnapshot(page);
    const finishedAt = new Date();

    return {
      status: "passed",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      generatedSteps: stepsToRun,
      steps,
      accessibility: {
        initial: initialAccessibilitySnapshot,
        final: finalAccessibilitySnapshot,
      },
    };
  } catch (error) {
    const finalAccessibilitySnapshot = await extractAccessibilitySnapshot(page);
    const screenshot = await captureFailureScreenshot(page);
    const finishedAt = new Date();

    return {
      status: "failed",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      generatedSteps: stepsToRun,
      errorMessage: error.message,
      steps,
      screenshot,
      accessibility: {
        initial: initialAccessibilitySnapshot,
        final: finalAccessibilitySnapshot,
      }
    };
  } finally {
    await browser.close();
  }
}

async function executeStructuredStep(page, steps, step) {
  if (step.action === "goto") {
    await runStep(steps, `Go to ${step.target}`, async () => {
      if (step.target.toLowerCase() === "login") {
        await expect(
          page.getByRole("heading", { name: "Login" }),
        ).toBeVisible();
        return;
      }

      throw new Error(`Unknown page target: ${step.target}`);
    });

    return;
  }

  if (step.action === "type") {
    await runStep(steps, `Type into ${step.target}`, async () => {
      await page.getByLabel(step.target).fill(step.value);
    });

    return;
  }

  if (step.action === "click") {
    await runResolvedClickStep(page, steps, step);
    return;
  }

  if (step.action === "check_visible") {
    await runStep(steps, `Check ${step.target} is visible`, async () => {
      await expect(page.getByText(step.target)).toBeVisible();
    });

    return;
  }

  if (step.action === "check_contains") {
    await runStep(
      steps,
      `Check ${step.target} contains ${step.value}`,
      async () => {
        await expect(page.getByLabel(step.target)).toHaveValue(step.value);
      },
    );

    return;
  }

  throw new Error(`Unsupported action: ${step.action}`);
}

async function runStep(steps, name, action) {
  const startedAt = new Date();

  try {
    await action();

    const finishedAt = new Date();

    steps.push({
      name,
      status: "passed",
      durationMs: finishedAt - startedAt,
    });
  } catch (error) {
    const finishedAt = new Date();

    steps.push({
      name,
      status: "failed",
      durationMs: finishedAt - startedAt,
      errorMessage: error.message,
    });

    throw error;
  }
}

async function captureFailureScreenshot(page) {
  await fs.mkdir(screenshotsDirectory, { recursive: true });

  const filename = `failure-${Date.now()}.png`;
  const absolutePath = path.join(screenshotsDirectory, filename);

  await page.screenshot({
    path: absolutePath,
    fullPage: true
  });

  return {
    filename,
    urlPath: `/screenshots/${filename}`,
    absolutePath
  };
}

async function runResolvedClickStep(page, steps, step) {
  const startedAt = new Date();
  const resolution = await resolveButton(page, step.target);

  if (!resolution.locator) {
    const finishedAt = new Date();

    steps.push({
      name: `Click ${step.target}`,
      status: "failed",
      durationMs: finishedAt - startedAt,
      selectorUsed: null,
      wasHealed: false,
      oldSelector: resolution.oldSelector,
      newSelector: null,
      resolutionStrategy: resolution.resolutionStrategy,
      confidence: resolution.confidence,
      estimatedCostUsd: resolution.estimatedCostUsd,
      resolutionAttempts: resolution.attempts,
      errorMessage: `Unable to resolve button "${step.target}"`
    });

    throw new Error(`Unable to resolve button "${step.target}"`);
  }

  await resolution.locator.click();

  const finishedAt = new Date();

  steps.push({
    name: `Click ${step.target}`,
    status: "passed",
    durationMs: finishedAt - startedAt,
    selectorUsed: resolution.selectorUsed,
    wasHealed: resolution.wasHealed,
    oldSelector: resolution.oldSelector,
    newSelector: resolution.newSelector,
    resolutionStrategy: resolution.resolutionStrategy,
    confidence: resolution.confidence,
    estimatedCostUsd: resolution.estimatedCostUsd,
    resolutionAttempts: resolution.attempts
  });
}