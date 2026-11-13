import assert from "node:assert/strict";
import test from "node:test";
import { parseInstruction } from "../src/parser.js";

const cases = [
  ["Go to Users.", { action: "goto", target: "Users" }],
  ["Type Maya Chen into Name.", { action: "type", value: "Maya Chen", target: "Name" }],
  ["Clear Search users.", { action: "clear", target: "Search users" }],
  ["Click Add User.", { action: "click", target: "Add User" }],
  ["Double click Update Plan.", { action: "double_click", target: "Update Plan" }],
  ["Select QA Engineer from Role.", { action: "select", value: "QA Engineer", target: "Role" }],
  ["Check Weekly digest.", { action: "check", target: "Weekly digest" }],
  ["Uncheck Email reports.", { action: "uncheck", target: "Email reports" }],
  ["Press Enter in Search users.", { action: "press", value: "Enter", target: "Search users" }],
  ["Hover over Notifications.", { action: "hover", target: "Notifications" }],
  ["Wait for Team Members.", { action: "wait_for", target: "Team Members" }],
  ["Check that Users is visible.", { action: "check_visible", target: "Users" }],
  ["Check that Add User is hidden.", { action: "check_hidden", target: "Add User" }],
  ["Check that Email contains user@example.com.", { action: "check_contains", target: "Email", value: "user@example.com" }],
  ["Check that Current Plan has text Pro.", { action: "check_text", target: "Current Plan", value: "Pro" }],
  ["Check that Job Title equals QA Lead.", { action: "check_value", target: "Job Title", value: "QA Lead" }],
  ["Check that Save Profile is enabled.", { action: "check_enabled", target: "Save Profile" }],
  ["Check that Locked action is disabled.", { action: "check_disabled", target: "Locked action" }],
  ["Check that Weekly digest is checked.", { action: "check_checked", target: "Weekly digest" }],
  ["Check that Weekly digest is unchecked.", { action: "check_unchecked", target: "Weekly digest" }],
];

test("parses every supported action into a validated step", () => {
  for (const [instruction, expected] of cases) {
    assert.deepEqual(parseInstruction(instruction), [expected]);
  }
});

test("rejects unsupported instructions before browser execution", () => {
  assert.throws(
    () => parseInstruction("Make the application better."),
    /Unsupported instruction line/,
  );
});

test("requires at least one instruction", () => {
  assert.throws(() => parseInstruction("\n\n"), /At least one instruction/);
});
