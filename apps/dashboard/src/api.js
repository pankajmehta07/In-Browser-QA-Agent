export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:4000";

export async function apiRequest(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error(
      "The QA service is unavailable. Start the backend on port 4000 and try again.",
    );
  }

  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : null;

  if (!response.ok) {
    throw new Error(
      body?.errorMessage || `Request failed with status ${response.status}.`,
    );
  }

  return body;
}

export function jsonRequest(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
