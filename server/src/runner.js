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
      await page.getByLabel("Email", { exact: true }).fill("user@example.com");
    });

    await runStep(steps, "Type password", async () => {
      await page.getByLabel("Password", { exact: true }).fill("password123");
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
        await expect(
          page.getByLabel("Email", { exact: true }),
        ).toHaveValue("user@example.com");
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

      await page.getByRole("button", { name: step.target, exact: true }).click();
      await expect(
        page.getByRole("heading", { name: step.target, exact: true }).first(),
      ).toBeVisible();
    });

    return;
  }

  if (step.action === "type") {
    await runStep(steps, `Type into ${step.target}`, async () => {
      await (await findTarget(page, step.target)).fill(step.value);
    });

    return;
  }

  if (step.action === "clear") {
    await runStep(steps, `Clear ${step.target}`, async () => {
      await (await findTarget(page, step.target)).clear();
    });

    return;
  }

  if (step.action === "click") {
    await runResolvedClickStep(page, steps, step);
    return;
  }

  if (step.action === "double_click") {
    await runStep(steps, `Double click ${step.target}`, async () => {
      await (await findTarget(page, step.target)).dblclick();
    });

    return;
  }

  if (step.action === "select") {
    await runStep(steps, `Select ${step.value} from ${step.target}`, async () => {
      await (await findTarget(page, step.target)).selectOption({ label: step.value });
    });

    return;
  }

  if (step.action === "check" || step.action === "uncheck") {
    const verb = step.action === "check" ? "Check" : "Uncheck";

    await runStep(steps, `${verb} ${step.target}`, async () => {
      const locator = await findTarget(page, step.target);

      if (step.action === "check") {
        await locator.check();
      } else {
        await locator.uncheck();
      }
    });

    return;
  }

  if (step.action === "press") {
    await runStep(steps, `Press ${step.value} in ${step.target}`, async () => {
      await (await findTarget(page, step.target)).press(step.value);
    });

    return;
  }

  if (step.action === "hover") {
    await runStep(steps, `Hover over ${step.target}`, async () => {
      await (await findTarget(page, step.target)).hover();
    });

    return;
  }

  if (step.action === "wait_for") {
    await runStep(steps, `Wait for ${step.target}`, async () => {
      await (await findTarget(page, step.target)).waitFor({ state: "visible" });
    });

    return;
  }

  if (step.action === "check_visible") {
    await runStep(steps, `Check ${step.target} is visible`, async () => {
      await expect(await findTarget(page, step.target)).toBeVisible();
    });

    return;
  }

  if (step.action === "check_hidden") {
    await runStep(steps, `Check ${step.target} is hidden`, async () => {
      await expect(await findTarget(page, step.target, { allowMissing: true })).toBeHidden();
    });

    return;
  }

  if (step.action === "check_contains") {
    await runStep(
      steps,
      `Check ${step.target} contains ${step.value}`,
      async () => {
        const locator = await findTarget(page, step.target);
        const isFormControl = await locator.evaluate((element) =>
          ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName),
        );

        if (isFormControl) {
          await expect(locator).toHaveValue(new RegExp(escapeRegExp(step.value)));
        } else {
          await expect(locator).toContainText(step.value);
        }
      },
    );

    return;
  }

  if (step.action === "check_text") {
    await runStep(steps, `Check ${step.target} has text ${step.value}`, async () => {
      await expect(await findTarget(page, step.target)).toHaveText(step.value);
    });

    return;
  }

  if (step.action === "check_value") {
    await runStep(steps, `Check ${step.target} equals ${step.value}`, async () => {
      await expect(await findTarget(page, step.target)).toHaveValue(step.value);
    });

    return;
  }

  const stateMatchers = {
    check_enabled: ["enabled", (locator) => expect(locator).toBeEnabled()],
    check_disabled: ["disabled", (locator) => expect(locator).toBeDisabled()],
    check_checked: ["checked", (locator) => expect(locator).toBeChecked()],
    check_unchecked: ["unchecked", (locator) => expect(locator).not.toBeChecked()],
  };

  if (stateMatchers[step.action]) {
    const [state, assertion] = stateMatchers[step.action];
    await runStep(steps, `Check ${step.target} is ${state}`, async () => {
      await assertion(await findTarget(page, step.target));
    });

    return;
  }

  throw new Error(`Unsupported action: ${step.action}`);
}

async function findTarget(page, target, options = {}) {
  const candidates = [
    page.getByLabel(target, { exact: true }),
    page.getByRole("heading", { name: target, exact: true }),
    page.getByRole("textbox", { name: target, exact: true }),
    page.getByRole("combobox", { name: target, exact: true }),
    page.getByRole("checkbox", { name: target, exact: true }),
    page.getByRole("radio", { name: target, exact: true }),
    page.getByRole("button", { name: target, exact: true }),
    page.getByRole("link", { name: target, exact: true }),
    page.getByPlaceholder(target, { exact: true }),
    page.getByText(target, { exact: true }),
    page.getByText(target, { exact: false }),
  ];

  for (const candidate of candidates) {
    if ((await candidate.count()) > 0) {
      return candidate.first();
    }
  }

  if (options.allowMissing) {
    return page.getByText(target, { exact: true }).first();
  }

  throw new Error(`Unable to find target "${target}"`);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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
