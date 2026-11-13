import base64
import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from api.main import app


ID = "00000000-0000-0000-0000-000000000001"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jL1sAAAAASUVORK5CYII=")


class CompatibilityScreenshotTests(TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.directory = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.root = self.directory / "screenshots"
        self.root.mkdir()
        self.file = self.root / "failure.png"
        self.file.write_bytes(PNG)
        stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        stack.enter_context(patch.dict(os.environ, {"ENABLE_RUN_SCREENSHOTS": "true", "RUN_SCREENSHOT_ROOT": str(self.root)}))
        self.read = stack.enter_context(patch("api.routers.compat.get_run_by_id", new_callable=AsyncMock,
            return_value={"screenshot_path": str(self.file)}))
        self.client = stack.enter_context(TestClient(app))
        self.path = f"/compat/runs/{ID}/screenshot"

    def test_saved_run_screenshot_is_served_as_private_png(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertNotIn(str(self.root), str(response.headers))
        self.read.assert_awaited_once_with(ID)

    def test_disabled_by_default_does_not_read_database(self):
        with patch.dict(os.environ):
            os.environ.pop("ENABLE_RUN_SCREENSHOTS", None)
            response = self.client.get(self.path)
        self.assertEqual(response.status_code, 403)
        self.assertIn("errorMessage", response.json())
        self.read.assert_not_awaited()

    def test_missing_root_configuration_is_not_a_public_file_fallback(self):
        with patch.dict(os.environ):
            os.environ.pop("RUN_SCREENSHOT_ROOT", None)
            response = self.client.get(self.path)
        self.assertEqual(response.status_code, 503)
        self.read.assert_not_awaited()

    def test_missing_run_or_unavailable_reference_returns_generic_404(self):
        for row in [None, {}, {"screenshot_path": str(self.root / "missing.png")}, {"screenshot_path": str(self.root)}]:
            with self.subTest(row=row):
                self.read.return_value = row
                response = self.client.get(self.path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(str(self.directory), response.text)

    def test_outside_root_and_traversal_references_cannot_expose_files(self):
        outside = self.directory / "private.png"
        outside.write_bytes(PNG)
        for reference in [str(outside), str(self.root / ".." / "private.png")]:
            with self.subTest(reference=reference):
                self.read.return_value = {"screenshot_path": reference}
                response = self.client.get(self.path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(str(outside), response.text)

    def test_non_png_and_oversized_files_are_rejected(self):
        bad = self.root / "bad.png"
        bad.write_bytes(b"<html>not a screenshot</html>")
        wrong_type = self.root / "image.svg"
        wrong_type.write_bytes(PNG)
        huge = self.root / "huge.png"
        with huge.open("wb") as stream:
            stream.write(PNG)
            stream.truncate(5 * 1024 * 1024 + 1)
        for file in [bad, wrong_type, huge]:
            with self.subTest(file=file):
                self.read.return_value = {"screenshot_path": str(file)}
                self.assertEqual(self.client.get(self.path).status_code, 404)

    def test_legacy_relative_path_is_resolved_against_process_working_directory(self):
        self.read.return_value = {"screenshot_path": "screenshots/failure.png"}
        with patch("pathlib.Path.cwd", return_value=self.directory):
            response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, PNG)

    def test_invalid_run_id_is_rejected_before_lookup(self):
        self.assertEqual(self.client.get("/compat/runs/not-a-uuid/screenshot").status_code, 422)
        self.read.assert_not_awaited()

    def test_symlink_escape_is_rejected(self):
        outside = self.directory / "outside.png"
        outside.write_bytes(PNG)
        link = self.root / "linked.png"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks requires platform permissions")
        self.read.return_value = {"screenshot_path": str(link)}
        self.assertEqual(self.client.get(self.path).status_code, 404)

    def test_database_failure_is_sanitized(self):
        self.read.side_effect = RuntimeError("private database password")
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database password", response.text)
