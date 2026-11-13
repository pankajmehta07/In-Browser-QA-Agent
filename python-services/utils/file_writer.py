import json
import os
import re
from datetime import datetime

from utils.logger import log_success, log_error


def generate_filename(url: str) -> str:
    """
    Generate output filename from URL and current timestamp.
    Example: output/auditFiles/audit_example-com_20240101_153045.json
    """
    # slug the url
    slug = (
        url
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .rstrip("/")
    )
    # replace any non-alphanumeric char with hyphen
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # trim leading/trailing hyphens
    slug = slug.strip("-")
    # cap length so filename stays readable
    slug = slug[:50]

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    return os.path.join("output/auditFiles", f"audit_{slug}_{timestamp}.json")


def save_report_to_file(data: dict, filepath: str) -> bool:
    """
    Write serialized report dict to a JSON file.
    Returns True on success, False on failure.
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        log_success(f"Report saved → {filepath}")
        return True

    except Exception as error:
        log_error(f"Failed to save report: {error}")
        return False