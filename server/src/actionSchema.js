export const ACTION_DEFINITIONS = Object.freeze({
  goto: ["target"],
  type: ["target", "value"],
  clear: ["target"],
  click: ["target"],
  double_click: ["target"],
  select: ["target", "value"],
  check: ["target"],
  uncheck: ["target"],
  press: ["target", "value"],
  hover: ["target"],
  wait_for: ["target"],
  check_visible: ["target"],
  check_hidden: ["target"],
  check_contains: ["target", "value"],
  check_text: ["target", "value"],
  check_value: ["target", "value"],
  check_enabled: ["target"],
  check_disabled: ["target"],
  check_checked: ["target"],
  check_unchecked: ["target"],
});

export function validateSteps(steps) {
  if (!Array.isArray(steps) || steps.length === 0) {
    throw new Error("At least one instruction is required.");
  }

  return steps.map((step, index) => validateStep(step, index));
}

export function validateStep(step, index = 0) {
  if (!step || typeof step !== "object" || Array.isArray(step)) {
    throw new Error(`Step ${index + 1} must be an object.`);
  }

  const requiredFields = ACTION_DEFINITIONS[step.action];

  if (!requiredFields) {
    throw new Error(`Step ${index + 1} uses unsupported action: ${step.action}`);
  }

  for (const field of requiredFields) {
    if (typeof step[field] !== "string" || !step[field].trim()) {
      throw new Error(
        `Step ${index + 1} (${step.action}) requires a non-empty ${field}.`,
      );
    }
  }

  return {
    action: step.action,
    ...Object.fromEntries(
      requiredFields.map((field) => [field, step[field].trim()]),
    ),
  };
}
