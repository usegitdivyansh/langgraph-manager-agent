"""
slack_users -- deterministic name -> Slack user ID mapping.
Built once from users.list, cached in memory. NO fuzzy matching:
exact case-insensitive match on real_name / display_name / first token
of real_name. If a name has no Slack account, callers get None and
should fall back to plain text.
"""
import os
from slack_sdk import WebClient
_CACHE: dict[str, str] | None = None
def _build_map() -> dict[str, str]:
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    resp = client.users_list()
    mapping: dict[str, str] = {}
    for m in resp["members"]:
        if m.get("deleted") or m.get("is_bot") or m["id"] == "USLACKBOT":
            continue
        uid = m["id"]
        keys = set()
        real = (m.get("real_name") or "").strip()
        disp = (m["profile"].get("display_name") or "").strip()
        if real:
            keys.add(real.lower())
            keys.add(real.split()[0].lower())
        if disp:
            keys.add(disp.lower())
        for k in keys:
            if k and k not in mapping:
                mapping[k] = uid
    return mapping
def get_user_map(refresh: bool = False) -> dict[str, str]:
    global _CACHE
    if _CACHE is None or refresh:
        try:
            _CACHE = _build_map()
        except Exception as e:
            print(f"[SLACK USERS WARNING] could not build user map: {e}")
            _CACHE = {}
    return _CACHE
def lookup_user_id(person_name: str) -> str | None:
    """Exact (case-insensitive) lookup. Returns Slack user ID or None."""
    if not person_name:
        return None
    return get_user_map().get(person_name.strip().lower())
def lookup_person_name(user_id: str) -> str | None:
    """Reverse lookup: Slack user ID -> the person's first name (as used in the
    wiki). Returns None if the ID is unknown. Deterministic, no fuzzy matching."""
    if not user_id:
        return None
    for name, uid in get_user_map().items():
        if uid == user_id and " " not in name:
            return name.capitalize()
    return None
def mention(person_name: str) -> str:
    """Return <@UID> if the person has a Slack account, else the plain name."""
    uid = lookup_user_id(person_name)
    return f"<@{uid}>" if uid else person_name
