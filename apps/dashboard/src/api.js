export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "/api";

export class ApiRequestError extends Error {
  constructor(message, { status = null, body = null } = {}) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.body = body;
  }
}

export async function apiRequest(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new ApiRequestError(
      "The QA service is unavailable. Start the backend on port 4000 and try again.",
    );
  }

  const contentType = response.headers.get("content-type") || "";
  let body = null;
  if (contentType.includes("application/json")) {
    try {
      body = await response.json();
    } catch {
      throw new ApiRequestError("The QA service returned an invalid JSON response.", {
        status: response.status,
      });
    }
  }

  if (!response.ok) {
    const message = typeof body?.errorMessage === "string" && body.errorMessage.trim()
      ? body.errorMessage
      : `Request failed with status ${response.status}.`;
    throw new ApiRequestError(message, { status: response.status, body });
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
