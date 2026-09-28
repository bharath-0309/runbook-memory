import unittest

import agent
import memory
from data import INCIDENTS, as_memory


class FallbackTests(unittest.TestCase):
    def test_memory_recall_works_without_hindsight_service(self):
        memory._fallback_store.clear()
        for item in INCIDENTS:
            memory.retain(as_memory(item), context=f"{item['service']} incident history")
        results = memory.recall("payments-api incident: 502 spike on /charge, postgres connection timeout")
        self.assertTrue(results)
        self.assertTrue(any("payments-api" in r.lower() for r in results))

    def test_triage_uses_fallback_answer_when_no_llm_key(self):
        result = agent.triage(
            "payments-api",
            "502 spike on /charge, postgres connection timeout",
            "D-4600",
            use_memory=True,
        )
        self.assertIn("rollback", result["answer"].lower())
        self.assertIn("failed", result["answer"].lower())


if __name__ == "__main__":
    unittest.main()
