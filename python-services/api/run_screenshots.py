"""Bounded reads of run-linked PNGs from an operator-controlled directory."""

import stat
from pathlib import Path


MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ScreenshotUnavailable(Exception):
    pass


class ScreenshotConfigurationError(Exception):
    pass


def read_screenshot(reference, configured_root):
    try:
        root = Path(configured_root).resolve(strict=True)
        if not root.is_dir():
            raise ScreenshotConfigurationError()
    except (OSError, ValueError, RuntimeError) as exc:
        raise ScreenshotConfigurationError() from exc
    try:
        if not isinstance(reference, str) or not reference.strip():
            raise ScreenshotUnavailable()
        path = Path(reference)
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.resolve(strict=True)
        if not path.is_relative_to(root) or path.suffix.lower() != ".png":
            raise ScreenshotUnavailable()
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SCREENSHOT_BYTES:
            raise ScreenshotUnavailable()
        with path.open("rb") as stream:
            content = stream.read(MAX_SCREENSHOT_BYTES + 1)
        if len(content) > MAX_SCREENSHOT_BYTES or not content.startswith(PNG_SIGNATURE):
            raise ScreenshotUnavailable()
        return content
    except (OSError, ValueError, RuntimeError) as exc:
        raise ScreenshotUnavailable() from exc
