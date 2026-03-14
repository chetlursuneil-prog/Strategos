#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


def _http_json(
    method: str,
    url: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"http_{exc.code}: {detail[:600]}")
    except Exception as exc:
        raise RuntimeError(f"http_request_failed: {exc}")


def _safe_get(obj: Dict[str, Any], *path: str, default: Any = None) -> Any:
    cur: Any = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strict STRATEGOS advisory flow for Telegram/OpenClaw.")
    parser.add_argument("--scenario", required=True, help="Raw scenario text")
    parser.add_argument("--base-url", default=os.getenv("STRATEGOS_API_BASE_URL", "").strip())
    parser.add_argument("--token", default=os.getenv("STRATEGOS_API_TOKEN", "").strip())
    parser.add_argument("--tenant-id", default="")
    parser.add_argument("--model-version-id", default="")
    args = parser.parse_args()

    base_url = (args.base_url or "").strip().rstrip("/")
    if not base_url:
        print(json.dumps({"error": "missing_base_url"}))
        return 2

    # Base may include /api/v1 already. Keep endpoint join deterministic.
    intake_url = f"{base_url}/intake"
    intake_payload = {
        "tenant_id": (args.tenant_id or "").strip(),
        "model_version_id": (args.model_version_id or "").strip(),
        "text": args.scenario,
    }

    try:
        intake = _http_json("POST", intake_url, args.token, intake_payload, timeout=90)
    except Exception as exc:
        print(json.dumps({"error": "intake_failed", "detail": str(exc)}))
        return 3

    session_id = _safe_get(intake, "data", "session_id") or _safe_get(intake, "session_id")
    snapshot = _safe_get(intake, "data", "snapshot", default={}) or {}
    if not session_id:
        print(json.dumps({"error": "missing_session_id", "intake": intake}))
        return 4

    skills_base = f"{base_url}/advisory/skills"
    board_url = f"{skills_base}/board_insights/{urllib.parse.quote(str(session_id))}"

    board_data: Dict[str, Any] = {}
    board_warning = None
    try:
        board = _http_json("GET", board_url, args.token, None, timeout=180)
        board_data = _safe_get(board, "data", default={}) or {}
    except Exception as exc:
        board_warning = str(exc)

    state = snapshot.get("state") or _safe_get(board_data, "state") or "UNKNOWN"
    contributions = snapshot.get("contributions") or []
    restructuring = snapshot.get("restructuring_actions") or []
    board_insights = board_data.get("insights") or []

    executive_summary = (
        f"STRATEGOS run complete for session {session_id}. "
        f"State: {state}. "
        f"Contributions: {len(contributions)} item(s). "
        f"Restructuring actions: {len(restructuring)}. "
        f"Board insights: {len(board_insights)}."
    )
    if board_warning:
        executive_summary += f" Board insights warning: {board_warning}"

    result = {
        "session_id": str(session_id),
        "deterministic_state": state,
        "contributions": contributions,
        "restructuring": restructuring,
        "board_insights": board_insights,
        "executive_summary": executive_summary,
    }
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

