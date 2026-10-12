import { validateSteps } from "./actionSchema.js";

export function parseInstruction(instruction) {
  const lines = instruction
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  return validateSteps(lines.map(parseLine));
}

function parseLine(line) {
  const cleanLine = line.replace(/\.$/, "");

  const goToMatch = cleanLine.match(/^go to (.+)$/i);
  if (goToMatch) {
    return {
      action: "goto",
      target: goToMatch[1]
    };
  }

  const typeMatch = cleanLine.match(/^type (.+) into (.+)$/i);
  if (typeMatch) {
    return {
      action: "type",
      value: typeMatch[1],
      target: typeMatch[2]
    };
  }

  const clearMatch = cleanLine.match(/^clear (.+)$/i);
  if (clearMatch) {
    return { action: "clear", target: clearMatch[1] };
  }

  const doubleClickMatch = cleanLine.match(/^double click (.+)$/i);
  if (doubleClickMatch) {
    return { action: "double_click", target: doubleClickMatch[1] };
  }

  const selectMatch = cleanLine.match(/^select (.+) from (.+)$/i);
  if (selectMatch) {
    return {
      action: "select",
      value: selectMatch[1],
      target: selectMatch[2],
    };
  }

  const uncheckMatch = cleanLine.match(/^uncheck (.+)$/i);
  if (uncheckMatch) {
    return { action: "uncheck", target: uncheckMatch[1] };
  }

  const checkControlMatch = cleanLine.match(/^check (?!that\b)(.+)$/i);
  if (checkControlMatch) {
    return { action: "check", target: checkControlMatch[1] };
  }

  const pressMatch = cleanLine.match(/^press (.+) in (.+)$/i);
  if (pressMatch) {
    return {
      action: "press",
      value: pressMatch[1],
      target: pressMatch[2],
    };
  }

  const hoverMatch = cleanLine.match(/^hover over (.+)$/i);
  if (hoverMatch) {
    return { action: "hover", target: hoverMatch[1] };
  }

  const waitMatch = cleanLine.match(/^wait for (.+)$/i);
  if (waitMatch) {
    return { action: "wait_for", target: waitMatch[1] };
  }

  const clickMatch = cleanLine.match(/^click (.+)$/i);
  if (clickMatch) {
    return {
      action: "click",
      target: clickMatch[1]
    };
  }

  const visibleMatch = cleanLine.match(/^check that (.+) is visible$/i);
  if (visibleMatch) {
    return {
      action: "check_visible",
      target: visibleMatch[1]
    };
  }

  const hiddenMatch = cleanLine.match(/^check that (.+) is hidden$/i);
  if (hiddenMatch) {
    return { action: "check_hidden", target: hiddenMatch[1] };
  }

  const enabledMatch = cleanLine.match(/^check that (.+) is enabled$/i);
  if (enabledMatch) {
    return { action: "check_enabled", target: enabledMatch[1] };
  }

  const disabledMatch = cleanLine.match(/^check that (.+) is disabled$/i);
  if (disabledMatch) {
    return { action: "check_disabled", target: disabledMatch[1] };
  }

  const uncheckedMatch = cleanLine.match(/^check that (.+) is unchecked$/i);
  if (uncheckedMatch) {
    return { action: "check_unchecked", target: uncheckedMatch[1] };
  }

  const checkedMatch = cleanLine.match(/^check that (.+) is checked$/i);
  if (checkedMatch) {
    return { action: "check_checked", target: checkedMatch[1] };
  }

  const textMatch = cleanLine.match(/^check that (.+) has text (.+)$/i);
  if (textMatch) {
    return {
      action: "check_text",
      target: textMatch[1],
      value: textMatch[2],
    };
  }

  const valueMatch = cleanLine.match(/^check that (.+) equals (.+)$/i);
  if (valueMatch) {
    return {
      action: "check_value",
      target: valueMatch[1],
      value: valueMatch[2],
    };
  }

  const containsMatch = cleanLine.match(/^check that (.+) contains (.+)$/i);
  if (containsMatch) {
    return {
      action: "check_contains",
      target: containsMatch[1],
      value: containsMatch[2]
    };
  }

  throw new Error(`Unsupported instruction line: "${line}"`);
}
