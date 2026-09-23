"""
ExperimentLogger.py — Saves structured experiment logs as human-readable JSON.

One JSON file per experiment run, saved to experiment_logs/.
Format is designed to be readable by a psychologist without technical knowledge.
"""

import json
import os
from datetime import datetime, timezone

LOG_DIR = "experiment_logs"


def save_experiment_log(data: dict) -> str:
    """
    Save experiment log as formatted JSON.
    Returns the filename of the saved log.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    pid       = data.get("participant_id", "unbekannt").upper()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    filename  = f"exp_{pid}_{timestamp}.json"
    filepath  = os.path.join(LOG_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[ExperimentLogger] Saved: {filepath}")
    return filename


def list_logs() -> list:
    """Return list of all saved experiment logs."""
    if not os.path.exists(LOG_DIR):
        return []
    files = [f for f in os.listdir(LOG_DIR) if f.endswith(".json")]
    files.sort(reverse=True)
    return files


def read_log(filename: str) -> dict:
    """Return contents of a specific log file."""
    filepath = os.path.join(LOG_DIR, filename)
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
