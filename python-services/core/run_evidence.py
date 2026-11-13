"""Optional viewport PNG capture into operator-controlled storage."""

import asyncio
import os
import uuid
from pathlib import Path


MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _root(configured):
    if not configured or not configured.strip():
        raise ValueError("Screenshot storage must be configured")
    root = Path(configured).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Screenshot storage must be a directory")
    return root


def _write_png(root, content):
    path = root / f"failure-{uuid.uuid4()}.png"
    created = False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        return str(path)
    except Exception:
        if created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


async def capture_screenshot(page, configured_root):
    root = await asyncio.to_thread(_root, configured_root)
    content = await page.screenshot(type="png", full_page=False, timeout=5000)
    if not isinstance(content, bytes) or len(content) > MAX_SCREENSHOT_BYTES or not content.startswith(PNG_SIGNATURE):
        raise ValueError("Screenshot content is unavailable or exceeds the supported limit")
    return await asyncio.to_thread(_write_png, root, content)
