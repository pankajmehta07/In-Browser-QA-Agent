import os

# static known pages — extend as more pages are added
# keys are normalized (lowercase, stripped)
# values are paths (relative) or full URLs

STATIC_PAGE_REGISTRY: dict[str, str] = {
    "login":        "/login",
    "dashboard":    "/dashboard",
    "settings":     "/settings",
    "home":         "/",
    "register":     "/register",
    "signup":       "/signup",
    "sign up":      "/signup",
    "profile":      "/profile",
    "logout":       "/logout",
    "sign out":     "/logout",
}


def get_base_url() -> str:
    """
    Get the base URL of the target app.
    Falls back to localhost:5173 if not set.
    """
    return os.environ.get("TARGET_APP_URL", "http://127.0.0.1:5173").rstrip("/")


def resolve_static(target: str) -> str | None:
    """
    Look up target in the static registry.
    Returns a full URL or None if not found.
    """
    normalized = target.strip().lower()
    path       = STATIC_PAGE_REGISTRY.get(normalized)

    if not path:
        return None

    # already a full URL
    if path.startswith("http"):
        return path

    return get_base_url() + path