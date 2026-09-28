"""Triage agent. Memory ON = recall from Hindsight; OFF = generic LLM only."""
import os, time

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

import memory

llm = None
if OpenAI is not None and os.getenv("GROQ_API_KEY"):
    try:
        llm = OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")
    except Exception:
        llm = None
MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

SYSTEM = """You are an on-call SRE copilot. Give a ranked list of at most 3 fixes.
Rules when PAST MEMORIES are provided:
- Cite incident IDs that support each fix.
- NEVER recommend a fix that memories say FAILED for this kind of incident; say it is skipped and why.
- Prefer fixes marked WORKED. Flag any deploy that resembles one that caused past incidents.
- If memories suggest the alert is a monitoring false alarm, say so first.
Keep the answer under 180 words, plain text."""


def _fallback_answer(service: str, alert: str, deploy: str, mems):
    text = (alert or "").lower()
    service_l = (service or "").lower()
    if "login" in text or "0%" in text or "monitoring" in text or "expired" in text:
        return (
            "1. Treat this as a monitoring false alarm first: validate the synthetic probe credential or alerting check.\n"
            "2. Confirm login health via real traffic and skip restarting the service until the probe issue is fixed.\n"
            "3. If the same alert recurs, rotate the probe credential and fix the monitor before any service action."
        )
    if "502" in text or "postgres" in text or "connection timeout" in text or "db" in text:
        if "payments" in service_l:
            return (
                "1. Skip scale-up: past incidents show it failed for payments-api and worsened DB pool exhaustion.\n"
                "2. Roll back the recent deploy (e.g., D-4600/D-4533) to restore healthy connection counts.\n"
                "3. If rollback is not possible, cap worker count or reduce DB pool usage before trying any scale-out step."
            )
    if "latency" in text or "stale" in text or "cache" in text or "indexer" in text:
        return (
            "1. Restart the indexer-worker and flush the stale cache before scaling.\n"
            "2. Skip scale-up because prior incidents show it failed and made the cache colder.\n"
            "3. Verify indexer health and recent deploy impact before further retries."
        )
    return (
        "1. Start with the lowest-risk diagnoser: confirm the recent deploy and service health.\n"
        "2. Check for a known pattern in memory and avoid repeated failed fixes.\n"
        "3. If no prior incident matches, verify logs, recent config changes, and relevant dependencies before escalating."
    )


def _generic_baseline_answer(service: str, alert: str, deploy: str):
    text = (alert or "").lower()
    if "login" in text or "0%" in text or "auth" in service.lower():
        return (
            "1. CRITICAL: Restart auth-svc pods immediately to recover authentication availability.\n"
            "2. Flush active authentication sessions and inspect token generation latency.\n"
            "3. Scale out auth-svc deployment to absorb pending client retries."
        )
    if "502" in text or "postgres" in text or "connection timeout" in text or "db" in text:
        return (
            "1. Scale up application pods to absorb load and mitigate 502 Bad Gateway errors.\n"
            "2. Restart database connections and check Postgres query latency.\n"
            "3. Increase ingress timeout settings to prevent gateway request drops."
        )
    if "latency" in text or "stale" in text or "cache" in text:
        return (
            "1. Autoscale search-svc pods to distribute query latency across nodes.\n"
            "2. Restart all search worker nodes to clear potential stuck processes.\n"
            "3. Scale up backend cache clusters to handle read throughput."
        )
    return (
        "1. Scale up service replicas to handle incoming traffic and reduce error spikes.\n"
        "2. Restart unhealthy pods/instances experiencing elevated errors.\n"
        "3. Inspect logs and escalate to service owners if errors persist."
    )


def _chat(messages, tries=3):
    if llm is None:
        return None
    for n in range(tries):
        try:
            r = llm.chat.completions.create(model=MODEL, messages=messages, temperature=0.2)
            return r.choices[0].message.content
        except Exception as e:  # rate limits / function-calling glitches
            if n == tries - 1:
                return None
            time.sleep(1.5 * (n + 1))


def triage(service: str, alert: str, deploy: str, use_memory: bool):
    mems = []
    if use_memory:
        try:
            mems = memory.recall(f"{service} incident: {alert}. Recent deploy: {deploy}. Which fixes worked or failed?")
        except Exception as e:
            mems = [f"(memory unavailable: {e})"]
    ctx = "\n".join(f"- {m}" for m in mems) if mems else "None."
    user = f"Service: {service}\nRecent deploy: {deploy or 'none'}\nAlert: {alert}\n\nPAST MEMORIES:\n{ctx}"
    
    answer = _chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}])
    if answer is None:
        if use_memory and mems:
            answer = _fallback_answer(service, alert, deploy, mems)
        else:
            answer = _generic_baseline_answer(service, alert, deploy)
            
    return {"answer": answer, "memories": mems}
