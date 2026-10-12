import os
import tempfile
import unittest

from precedent_index import PrecedentIndex, reciprocal_rank_fusion


class PrecedentIndexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = temporary.name
        temporary.close()
        self.index = PrecedentIndex(self.db_path, embedding_fn=lambda text: None)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except FileNotFoundError:
                pass

    def test_rank_fusion_rewards_cross_retriever_matches(self):
        fused = reciprocal_rank_fusion(["alpha", "beta"], ["beta", "alpha"])
        self.assertEqual(fused[0][0], "alpha")
        self.assertAlmostEqual(fused[0][1], fused[1][1])

    def test_search_returns_keyword_results_and_fallback_flag(self):
        self.index.upsert({
            "id": "car-proposal",
            "title": "Patrol vehicle replacement",
            "description": "Buy patrol cars for the north zone",
            "justification": "Replace old fleet vehicles",
            "category": "Procurement",
            "department": "North",
            "status": "Rejected",
            "latest_decision": {"reason": "Cost exceeded the allocated budget."},
        })
        results = self.index.search("buy new patrol cars for north zone")
        self.assertEqual(results[0]["id"], "car-proposal")
        self.assertTrue(results[0]["keyword_only"])
        self.assertIn("north", results[0]["matched_terms"])

    def test_drafts_and_withdrawn_proposals_are_not_indexed(self):
        for status in ("Draft", "Withdrawn"):
            self.assertFalse(self.index.upsert({"id": status, "status": status}))
        self.assertEqual(self.index.search("proposal"), [])


if __name__ == "__main__":
    unittest.main()