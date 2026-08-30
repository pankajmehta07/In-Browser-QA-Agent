export function parseInstruction(instruction) {
  const lines = instruction
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  return lines.map(parseLine);
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