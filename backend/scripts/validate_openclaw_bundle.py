import json
from pathlib import Path


REQUIRED_SEQUENCE = [
    "strategos.create_session",
    "strategos.run_engine",
    "strategos.fetch_state",
    "strategos.fetch_contributions",
    "strategos.fetch_restructuring",
    "strategos.fetch_board_insights",
]

REQUIRED_FINAL_PAYLOAD_KEYS = [
    "session_id",
    "deterministic_state",
    "contributions",
    "restructuring",
    "board_insights",
    "executive_summary",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    skills_file = root / "openclaw" / "skills" / "strategos_skills.json"
    agents_file = root / "openclaw" / "agents" / "strategos_advisory_board.json"

    for file in [skills_file, agents_file]:
        if not file.exists():
            print(f"ERROR: Missing file: {file}")
            return 1

    try:
        skills = json.loads(skills_file.read_text(encoding="utf-8"))
        agents = json.loads(agents_file.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: Invalid JSON: {exc}")
        return 1

    required_skill_keys = {"id", "method", "path"}
    for idx, skill in enumerate(skills.get("skills", [])):
        missing = [k for k in required_skill_keys if k not in skill]
        if missing:
            print(f"ERROR: skills[{idx}] missing keys: {missing}")
            return 1

    known_skill_ids = {s.get("id") for s in skills.get("skills", [])}

    missing_required_skill_ids = [
        skill_id for skill_id in REQUIRED_SEQUENCE if skill_id not in known_skill_ids
    ]
    if missing_required_skill_ids:
        print(
            "ERROR: Missing required skill ids for strict orchestration:",
            missing_required_skill_ids,
        )
        return 1

    for idx, agent in enumerate(agents.get("agents", [])):
        for skill_id in agent.get("skills", []):
            if skill_id not in known_skill_ids:
                print(f"ERROR: agent[{idx}] references unknown skill id: {skill_id}")
                return 1

    execution_contract = agents.get("execution_contract")
    if not isinstance(execution_contract, dict):
        print("ERROR: Missing execution_contract in advisory board config")
        return 1

    if execution_contract.get("required_sequence") != REQUIRED_SEQUENCE:
        print("ERROR: execution_contract.required_sequence mismatch")
        return 1

    if execution_contract.get("final_payload_required_keys") != REQUIRED_FINAL_PAYLOAD_KEYS:
        print("ERROR: execution_contract.final_payload_required_keys mismatch")
        return 1

    print("OpenClaw bundle validation: OK")
    print(f"Skills: {len(skills.get('skills', []))}")
    print(f"Agents: {len(agents.get('agents', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
