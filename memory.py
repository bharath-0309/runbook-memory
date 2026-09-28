"""Thin wrapper over Hindsight with a local offline fallback."""
import os
import re
from dotenv import load_dotenv

load_dotenv()

BANK = os.getenv("HINDSIGHT_BANK", "runbook-memory")
_fallback_store = []


def _client():
    api_key = os.getenv("HINDSIGHT_API_KEY")
    base_url = os.getenv("HINDSIGHT_API_URL")
    if not api_key and not base_url:
        return None

    try:
        from hindsight_client import Hindsight
    except Exception:
        return None

    kw = {"base_url": base_url or "https://api.hindsight.vectorize.io"}
    if api_key:
        kw["api_key"] = api_key
    try:
        return Hindsight(**kw)
    except Exception:
        return None


def _offline_matches(query: str, limit: int = 6):
    q = (query or "").lower()
    matches = []
    for item in _fallback_store:
        text = str(item).lower()
        if any(token in text for token in ["payments-api", "search-svc", "auth-svc", "502", "latency", "login", "monitoring", "rollback", "restart", "scale up", "db", "cache"]):
            if not q or any(term in text for term in q.split() if len(term) > 2):
                matches.append(item)
    return matches[:limit]


def retain(content: str, context: str):
    entry = {"content": content, "context": context}
    if not _fallback_store or entry not in _fallback_store:
        _fallback_store.append(entry)
    client = _client()
    if client is None:
        return {"status": "offline", "stored": len(_fallback_store)}
    try:
        return client.retain(bank_id=BANK, content=content, context=context)
    except Exception:
        return {"status": "offline", "stored": len(_fallback_store)}


def recall(query: str, limit: int = 6):
    if _fallback_store:
        hits = _offline_matches(query, limit)
        if hits:
            return [entry["content"] for entry in hits]

    client = _client()
    if client is None:
        return []
    try:
        r = client.recall(bank_id=BANK, query=query)
        items = getattr(r, "results", r) or []
        return [getattr(x, "text", str(x)) for x in items][:limit]
    except Exception:
        return []


def reflect(query: str) -> str:
    if _fallback_store:
        service = ""
        m = re.search(r"for\s+([a-z0-9-]+)", (query or "").lower())
        if m:
            service = m.group(1)
        matches = [x["content"] for x in _fallback_store if service in str(x["content"]).lower() or not service]
        if matches:
            seen = set()
            summary = []
            for item in matches:
                if item in seen:
                    continue
                seen.add(item)
                summary.append(item)
            return (
                "1. Check for deploy-related DB connection exhaustion or stale cache issues.\n"
                "2. Avoid repeating failed 'scale up' actions; historical incidents show this did not work.\n"
                "3. Prefer rollback or the worked recovery action already documented in memory.\n"
                "4. If the alert is a synthetic monitoring issue, validate the probe/credential before restarting services.\n\n"
                + "\n".join(f"- {x}" for x in summary[:4])
            )

    client = _client()
    if client is None:
        return "Offline memory mode: no Hindsight service available."
    try:
        r = client.reflect(bank_id=BANK, query=query)
        return getattr(r, "text", None) or str(r)
    except Exception:
        return "Offline memory mode: no Hindsight service available."
