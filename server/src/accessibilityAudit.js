const interactiveRoles = new Set(["button", "link", "textbox", "combobox"]);

export function auditAccessibility(snapshot = []) {
  const issues = [];
  const warnings = [];
  const passed = [];

  auditMissingNames(snapshot, issues, passed);
  auditDuplicateInteractiveNames(snapshot, warnings, passed);
  auditGenericSelectors(snapshot, warnings, passed);

  return {
    score: calculateScore(issues.length, warnings.length),
    issueCount: issues.length,
    warningCount: warnings.length,
    passedCount: passed.length,
    issues,
    warnings,
    passed,
  };
}

function auditMissingNames(snapshot, issues, passed) {
  const interactiveElements = snapshot.filter((element) =>
    interactiveRoles.has(element.role),
  );

  for (const element of interactiveElements) {
    if (!element.name || !element.name.trim()) {
      issues.push({
        rule: "missing_accessible_name",
        severity: "issue",
        message: `${element.role} has no accessible name.`,
        selector: element.selector,
        element,
      });
    } else {
      passed.push({
        rule: "has_accessible_name",
        message: `${element.role} "${element.name}" has an accessible name.`,
        selector: element.selector,
      });
    }
  }
}

function auditDuplicateInteractiveNames(snapshot, warnings, passed) {
  const counts = new Map();

  for (const element of snapshot) {
    if (!interactiveRoles.has(element.role)) {
      continue;
    }

    if (!element.name || !element.name.trim()) {
      continue;
    }

    const key = `${element.role}::${element.name.trim().toLowerCase()}`;
    const existing = counts.get(key) || [];

    counts.set(key, [...existing, element]);
  }

  for (const [key, elements] of counts.entries()) {
    if (elements.length > 1) {
      const [role, name] = key.split("::");

      warnings.push({
        rule: "duplicate_interactive_name",
        severity: "warning",
        message: `Multiple ${role} elements use the accessible name "${name}". This can make tests and screen-reader navigation ambiguous.`,
        selectors: elements.map((element) => element.selector),
        elements,
      });
    } else {
      passed.push({
        rule: "unique_interactive_name",
        message: `${elements[0].role} "${elements[0].name}" is unique on this page.`,
        selector: elements[0].selector,
      });
    }
  }
}

function auditGenericSelectors(snapshot, warnings, passed) {
  for (const element of snapshot) {
    if (!interactiveRoles.has(element.role)) {
      continue;
    }

    if (element.selector === element.tagName) {
      warnings.push({
        rule: "generic_selector",
        severity: "warning",
        message: `${element.role} "${element.name || "unnamed"}" has no stable id-based selector.`,
        selector: element.selector,
        element,
      });
    } else {
      passed.push({
        rule: "stable_selector_hint",
        message: `${element.role} "${element.name || "unnamed"}" has a more specific selector.`,
        selector: element.selector,
      });
    }
  }
}

function calculateScore(issueCount, warningCount) {
  const rawScore = 100 - issueCount * 25 - warningCount * 8;
  return Math.max(0, rawScore);
}
