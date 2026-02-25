from typing import Any, Dict


def format_response(data: Any = None, meta: Dict = None):
    return {"status": "success", "data": data or {}, "meta": meta or {}}
