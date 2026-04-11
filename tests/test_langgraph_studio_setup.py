import unittest

from fastapi.testclient import TestClient

from app.studio import langgraph_graphs, webapp


class LangGraphStudioSetupTests(unittest.TestCase):
    def test_graph_exports_exist(self):
        self.assertIsNotNone(langgraph_graphs.batch_supervisor_graph)
        self.assertIsNotNone(langgraph_graphs.page_agent_graph)

    def test_webapp_exposes_expected_routes(self):
        route_paths = {route.path for route in webapp.app.routes}
        self.assertIn("/health/live", route_paths)
        self.assertIn("/studio/info", route_paths)
        self.assertIn("/studio/topology", route_paths)
        self.assertIn("/studio/tasks/{task_id}/workflow-events", route_paths)

    def test_topology_endpoint_returns_expected_graphs(self):
        client = TestClient(webapp.app)
        response = client.get("/studio/topology")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["view"]["primary_graph"], "batch_supervisor")
        graph_ids = [graph["id"] for graph in payload["graphs"]]
        self.assertEqual(graph_ids, ["batch_supervisor", "page_agent"])

    def test_flow_page_mentions_task_replay(self):
        client = TestClient(webapp.app)
        response = client.get("/studio/flow?taskId=42")
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("OCR full workflow graph", body)
        self.assertIn("Load task trace", body)
        self.assertIn("42", body)


if __name__ == "__main__":
    unittest.main()
