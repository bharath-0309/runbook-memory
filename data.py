"""Synthetic incident history with planted patterns the agent must learn.
Patterns: (1) payments-api 502s after deploys = DB pool exhaustion, rollback works,
scaling up fails; (2) search-svc latency = stale cache, restarting the indexer worker
works, scaling fails; (3) auth-svc alert that is really a monitoring bug."""

INCIDENTS = [
 dict(id="INC-201", service="payments-api", date="2026-06-03", deploy="D-4410",
  alert="502 Bad Gateway spike on /charge, p99 latency 9s, error rate 14%",
  root="DB connection pool exhausted after deploy D-4410 raised worker count from 8 to 16",
  fixes=[("Scale up payments-api pods","failed"),("Roll back deploy D-4410","worked")]),
 dict(id="INC-204", service="search-svc", date="2026-06-11", deploy="D-4432",
  alert="Search latency p95 4.2s, results returning stale product data",
  root="Indexer worker stuck, cache never invalidated",
  fixes=[("Scale up search-svc","failed"),("Restart indexer-worker then flush cache","worked")]),
 dict(id="INC-209", service="payments-api", date="2026-06-19", deploy="D-4471",
  alert="502 errors on /charge after release, Postgres 'too many connections' in logs",
  root="Pool exhaustion again: new retry logic multiplied connections",
  fixes=[("Scale up payments-api pods","failed"),("Increase DB max_connections","partial"),("Roll back deploy D-4471","worked")]),
 dict(id="INC-212", service="auth-svc", date="2026-06-25", deploy="none",
  alert="CRITICAL: auth-svc login success rate 0% for 6 minutes",
  root="Monitoring bug: synthetic probe used an expired test credential. Real traffic was healthy",
  fixes=[("Restart auth-svc","failed"),("Rotate probe credential in monitoring","worked")]),
 dict(id="INC-216", service="search-svc", date="2026-07-02", deploy="D-4502",
  alert="Search returns yesterday's prices, latency climbing to 3s",
  root="Indexer worker stalled after deploy D-4502",
  fixes=[("Restart indexer-worker then flush cache","worked")]),
 dict(id="INC-220", service="payments-api", date="2026-07-09", deploy="D-4533",
  alert="Intermittent 502 on /charge, connection timeout to postgres-primary",
  root="Pool exhaustion after worker-count change in D-4533",
  fixes=[("Scale up payments-api pods","failed"),("Roll back deploy D-4533","worked")]),
 dict(id="INC-224", service="search-svc", date="2026-07-15", deploy="D-4561",
  alert="Slow search, users report outdated listings",
  root="Indexer worker stuck again; autoscaling made it worse by adding cold caches",
  fixes=[("Scale up search-svc","failed"),("Restart indexer-worker then flush cache","worked")]),
 dict(id="INC-229", service="auth-svc", date="2026-07-22", deploy="none",
  alert="CRITICAL: login success rate 0%, on-call paged",
  root="Same synthetic probe credential expired again",
  fixes=[("Rotate probe credential in monitoring","worked")]),
]

def as_memory(i):
    fx = "; ".join(f"{f} -> {o.upper()}" for f, o in i["fixes"])
    return (f"Incident {i['id']} on {i['date']} in {i['service']} (deploy {i['deploy']}). "
            f"Alert: {i['alert']}. Root cause: {i['root']}. Fixes tried: {fx}.")
