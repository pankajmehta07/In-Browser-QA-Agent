export async function extractAccessibilitySnapshot(page) {
  try {
    const elements = await page.locator("body *").evaluateAll((nodes) => {
      function safeText(value) {
        return String(value || "").trim();
      }

      function getElementRole(element) {
        const explicitRole = element.getAttribute("role");

        if (explicitRole) {
          return explicitRole;
        }

        const tagName = element.tagName.toLowerCase();
        const inputType = element.getAttribute("type") || "text";

        if (tagName === "button") {
          return "button";
        }

        if (tagName === "a" && element.hasAttribute("href")) {
          return "link";
        }

        if (tagName === "input") {
          if (["button", "submit", "reset"].includes(inputType)) {
            return "button";
          }

          return "textbox";
        }

        if (tagName === "textarea") {
          return "textbox";
        }

        if (tagName === "select") {
          return "combobox";
        }

        if (/^h[1-6]$/.test(tagName)) {
          return "heading";
        }

        return null;
      }

      function getElementName(element) {
        const ariaLabel = element.getAttribute("aria-label");

        if (ariaLabel) {
          return safeText(ariaLabel);
        }

        const labelledBy = element.getAttribute("aria-labelledby");

        if (labelledBy) {
          const labelElement = document.getElementById(labelledBy);

          if (labelElement) {
            return safeText(labelElement.innerText || labelElement.textContent);
          }
        }

        if (element.id) {
          const label = document.querySelector(`label[for="${element.id}"]`);

          if (label) {
            return safeText(label.innerText || label.textContent);
          }
        }

        return safeText(element.innerText || element.textContent);
      }

      function getCssSelector(element) {
        if (element.id) {
          return `#${element.id}`;
        }

        const tagName = element.tagName.toLowerCase();
        return tagName;
      }

      return nodes
        .map((element) => {
          const role = getElementRole(element);
          const name = getElementName(element);

          if (!role) {
             return null;
          }

          return {
            role,
            name: name || "",
            selector: getCssSelector(element),
            id: element.id || null,
            tagName: element.tagName.toLowerCase(),
          };
        })
        .filter(Boolean);
    });

    return dedupeElements(elements);
  } catch (error) {
    return [
      {
        role: "system",
        name: "Accessibility extraction failed",
        selector: "n/a",
        errorMessage: error.message,
      },
    ];
  }
}

function dedupeElements(elements) {
  const seen = new Set();

  return elements.filter((element) => {
    const key = `${element.role}::${element.name}::${element.selector}`;

    if (seen.has(key)) {
      return false;
    }

    seen.add(key);
    return true;
  });
}
