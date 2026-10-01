"""Save execution metrics without recording briefs, reports, or secrets."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


logger = logging.getLogger(__name__)

# Anchor the path to the project, regardless of where the command starts.
LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "runs.jsonl"


def log_run(
    run_id: str,
    implementation: str,
    status: str,
    elapsed_seconds: float,
    error_type: str | None = None,
) -> None:
    """Append one record for a completed or failed UI attempt."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "implementation": implementation,
        "status": status,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "error_type": error_type,
    }

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        # A logging failure should not prevent delivery of the report.
        logger.warning("Could not save the execution metrics.")