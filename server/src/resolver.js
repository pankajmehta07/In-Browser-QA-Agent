import { extractAccessibilitySnapshot } from "./accessibility.js";
import { findApprovedMapping } from "./approvalStore.js";

export async function resolveButton(page, targetName) {
  const attempts = [];

  const exactAttempt = {
    tier: "exact_role_match",
    description: `Try exact button name "${targetName}"`,
    estimatedCostUsd: 0,
    confidence: 1,
    status: "failed",
  };

  try {
    const exactLocator = page.getByRole("button", { name: targetName });
    await exactLocator.waitFor({ state: "visible", timeout: 1000 });

    exactAttempt.status = "passed";

    attempts.push(exactAttempt);

    return {
      locator: exactLocator,
      selectorUsed: `role=button[name="${targetName}"]`,
      wasHealed: false,
      oldSelector: null,
      newSelector: `role=button[name="${targetName}"]`,
      resolutionStrategy: "exact_role_match",
      confidence: 1,
      estimatedCostUsd: 0,
      attempts,
    };
  } catch (error) {
    exactAttempt.errorMessage = error.message;
    attempts.push(exactAttempt);
  }

  const memoryAttempt = {
    tier: "approved_memory",
    description: `Check approved selector memory for "${targetName}"`,
    estimatedCostUsd: 0,
    confidence: 0,
    status: "failed",
  };

  const approvedMapping = await findApprovedMapping(targetName);

  if (approvedMapping) {
    memoryAttempt.status = "passed";
    memoryAttempt.confidence = 1;
    memoryAttempt.approvedMapping = {
      oldTarget: approvedMapping.oldTarget,
      newTarget: approvedMapping.newTarget,
      savedAt: approvedMapping.savedAt,
    };

    attempts.push(memoryAttempt);

    const memoryLocator = page.getByRole("button", {
      name: approvedMapping.newTarget,
    });

    return {
      locator: memoryLocator,
      selectorUsed: `role=button[name="${approvedMapping.newTarget}"]`,
      wasHealed: true,
      oldSelector: `role=button[name="${targetName}"]`,
      newSelector: `role=button[name="${approvedMapping.newTarget}"]`,
      resolutionStrategy: "approved_memory",
      confidence: 1,
      estimatedCostUsd: 0,
      attempts,
    };
  }

  attempts.push(memoryAttempt);

  const accessibilityAttempt = {
    tier: "accessibility_text_similarity",
    description: `Search accessibility snapshot for a button similar to "${targetName}"`,
    estimatedCostUsd: 0,
    confidence: 0,
    status: "failed",
  };

  const snapshot = await extractAccessibilitySnapshot(page);
  const buttonCandidates = snapshot.filter(
    (element) => element.role === "button",
  );

  const scoredCandidates = buttonCandidates
    .map((candidate) => ({
      ...candidate,
      score: scoreButtonCandidate(targetName, candidate.name),
    }))
    .sort((a, b) => b.score - a.score);

  const bestCandidate = scoredCandidates[0];

  if (bestCandidate) {
    accessibilityAttempt.bestCandidate = {
      name: bestCandidate.name,
      selector: bestCandidate.selector,
      score: bestCandidate.score,
    };

    accessibilityAttempt.confidence = bestCandidate.score;
  }

  if (bestCandidate && bestCandidate.score >= 0.8) {
    const healedLocator = page.getByRole("button", {
      name: bestCandidate.name,
    });

    accessibilityAttempt.status = "passed";
    attempts.push(accessibilityAttempt);

    return {
      locator: healedLocator,
      selectorUsed: `role=button[name="${bestCandidate.name}"]`,
      wasHealed: true,
      oldSelector: `role=button[name="${targetName}"]`,
      newSelector: `role=button[name="${bestCandidate.name}"]`,
      resolutionStrategy: "accessibility_text_similarity",
      confidence: bestCandidate.score,
      estimatedCostUsd: 0,
      attempts,
    };
  }

  attempts.push(accessibilityAttempt);

  const visionAttempt = await simulateVisionFallback(targetName, snapshot);
  attempts.push(visionAttempt);

  return {
    locator: null,
    selectorUsed: null,
    wasHealed: false,
    oldSelector: `role=button[name="${targetName}"]`,
    newSelector: null,
    resolutionStrategy: "unresolved",
    confidence: 0,
    estimatedCostUsd: attempts.reduce(
      (total, attempt) => total + attempt.estimatedCostUsd,
      0,
    ),
    attempts,
  };
  function scoreButtonCandidate(expected, actual) {
    const normalizedExpected = normalizeText(expected);
    const normalizedActual = normalizeText(actual);

    if (normalizedExpected === normalizedActual) {
      return 1;
    }

    const knownPairs = new Map([
      ["login::sign in", 0.91],
      ["sign in::login", 0.91],
      ["log in::sign in", 0.91],
      ["save::save changes", 0.9],
      ["settings::settings", 1],
    ]);

    const pairKey = `${normalizedExpected}::${normalizedActual}`;

    if (knownPairs.has(pairKey)) {
      return knownPairs.get(pairKey);
    }

    if (
      normalizedActual.includes(normalizedExpected) ||
      normalizedExpected.includes(normalizedActual)
    ) {
      return 0.85;
    }

    return 0;
  }

  function normalizeText(value) {
    return value.trim().toLowerCase().replace(/\s+/g, " ");
  }
}

async function simulateVisionFallback(targetName, snapshot) {
  const visibleCandidates = snapshot
    .filter((element) => ["button", "link", "textbox"].includes(element.role))
    .slice(0, 8)
    .map((element) => `${element.role}: ${element.name}`)
    .join(", ");

  return {
    tier: "vision_llm_fallback",
    description: `Vision/LLM fallback would inspect the screenshot and page context to resolve "${targetName}".`,
    estimatedCostUsd: 0.004,
    confidence: 0,
    status: "skipped",
    reason: "No API key or multimodal model integration is configured yet.",
    promptPreview: {
      target: targetName,
      visibleCandidates,
    },
  };
}
