import unittest
import os
import tempfile

from flask import Flask
import numpy as np

import proposals
import workflow
import workflow_api
from workflow_api import init_workflow
from precedent_index import PrecedentIndex


class WorkflowApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.testing = True
        init_workflow(cls.app)

    def test_each_demo_account_can_login_and_load_dashboard(self):
        for username, user in workflow.DEMO_USERS.items():
            with self.subTest(username=username):
                client = self.app.test_client()
                response = client.post("/api/workflow/login", json={"username": username, "password": workflow.demo_password()})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["user"]["role"], user["role"])
                dashboard = client.get("/api/workflow/dashboard")
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn("proposals", dashboard.get_json())
                dashboard.close()
                response.close()

    def test_dashboard_requires_login(self):
        response = self.app.test_client().get("/api/workflow/dashboard")
        self.assertEqual(response.status_code, 401)

    def test_workflow_page_loads(self):
        response = self.app.test_client().get("/workflow")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Verify audit trail", response.data)
        response.close()

    def test_similar_api_returns_citations_and_alerts(self):
        temporary = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        index_path = temporary.name
        temporary.close()
        previous_index = workflow_api.precedent_index

        class StubGateway:
            def __init__(self):
                self.calls = []

            def call(self, model, messages, **kwargs):
                self.calls.append(kwargs)
                return type("Response", (), {"content": "Both texts describe patrol vehicles for the north zone."})()

        gateway = StubGateway()
        self.app.extensions["workflow_gateway"] = gateway
        workflow_api.precedent_index = PrecedentIndex(index_path, embedding_fn=lambda text: np.array([1.0, 0.0], dtype=np.float32))
        try:
            workflow_api.precedent_index.upsert({
                "id": "rejected-patrol",
                "title": "Procurement of patrol cars for north zone",
                "description": "Replace aging patrol vehicles in the north zone",
                "justification": "Fleet maintenance costs are increasing",
                "status": "Rejected",
                "latest_decision": {"reason": "Rejected on cost: exceeds the approved ceiling."},
            })
            workflow_api.precedent_index.upsert({
                "id": "active-patrol",
                "title": "Purchase patrol cars for north zone",
                "description": "Acquire patrol cars to extend north zone coverage",
                "justification": "Improve response times",
                "status": "Submitted",
                "latest_decision": {"reason": "Reviewer requested updated cost comparison."},
            })
            client = self.app.test_client()
            client.post("/api/workflow/login", json={"username": "insp.ops", "password": workflow.demo_password()})
            response = client.post("/api/proposals/similar", json={
                "title": "Buy patrol cars for the north zone",
                "description": "Replace vehicles and reduce fleet maintenance costs",
            })
            self.assertEqual(response.status_code, 200)
            body = response.get_json()
            self.assertEqual({hit["id"] for hit in body["results"]}, {"rejected-patrol", "active-patrol"})
            self.assertTrue(all(hit["decision_remark"] and hit["why_similar"] for hit in body["results"]))
            self.assertEqual(body["alerts"]["previously_rejected"]["proposal_id"], "rejected-patrol")
            self.assertEqual(body["alerts"]["possible_duplicate"]["proposal_id"], "active-patrol")
            self.assertEqual(len(gateway.calls), 2)
            self.assertTrue(all(call["timeout"] == 15 for call in gateway.calls))
            response.close()
        finally:
            workflow_api.precedent_index = previous_index
            self.app.extensions["workflow_gateway"] = None
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.remove(index_path + suffix)
                except FileNotFoundError:
                    pass

    def test_draft_is_not_in_similar_results_or_visible_to_other_users(self):
        client = self.app.test_client()
        client.post("/api/workflow/login", json={"username": "insp.ops", "password": workflow.demo_password()})
        created = client.post("/api/workflow/proposals", json={
            "title": "Zyzzx patrol vehicle procurement token",
            "category": "Procurement",
            "department": "North Zone",
            "description": "Unique zyzzx phrase must not leak to searches",
            "justification": "Temporary draft visibility test",
        }).get_json()["proposal"]
        try:
            other_user = self.app.test_client()
            other_user.post("/api/workflow/login", json={"username": "dsp.review", "password": workflow.demo_password()})
            detail = other_user.get(f"/api/proposals/{created['id']}/precedents")
            self.assertEqual(detail.status_code, 404)
            search = other_user.post("/api/proposals/similar", json={
                "title": "Zyzzx patrol vehicle procurement token",
                "description": "Unique zyzzx phrase must not leak to searches",
            })
            self.assertNotIn(created["id"], {hit["id"] for hit in search.get_json()["results"]})
            detail.close()
            search.close()
        finally:
            connection = proposals.get_db_connection()
            with connection:
                connection.execute("DELETE FROM proposals WHERE id=?", (created["id"],))
            connection.close()

    def test_audit_verification_passes_for_a_new_proposal(self):
        proposal = proposals.create_proposal(
            title="Workflow audit test",
            category="Operational",
            department="Test Unit",
            description="Temporary integration test proposal",
            justification="Verify the proposal audit chain",
            estimated_cost=1,
            created_by="Insp. Operations",
        )
        try:
            client = self.app.test_client()
            client.post("/api/workflow/login", json={"username": "insp.ops", "password": workflow.demo_password()})
            response = client.get(f"/api/workflow/proposals/{proposal['id']}/verify")
            self.assertTrue(response.get_json()["valid"])
            response.close()
        finally:
            connection = proposals.get_db_connection()
            with connection:
                connection.execute("DELETE FROM proposals WHERE id=?", (proposal["id"],))
            connection.close()


if __name__ == "__main__":
    unittest.main()