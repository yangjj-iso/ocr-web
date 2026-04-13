import unittest

from fastapi.testclient import TestClient

from app.studio import langgraph_graphs, webapp


class LangGraphStudioSetupTests(unittest.TestCase):
    def test_graph_exports_exist(self):
        self.assertIsNotNone(langgraph_graphs.archive_main_graph)
        self.assertIsNotNone(langgraph_graphs.archive_draft_graph)
        self.assertIsNotNone(langgraph_graphs.archive_final_graph)
        self.assertIsNotNone(langgraph_graphs.archive_resume_graph)

    def test_webapp_exposes_expected_routes(self):
        route_paths = {getattr(route, "path", "") for route in webapp.app.routes}
        self.assertIn("/health/live", route_paths)
        self.assertIn("/studio/info", route_paths)
        self.assertIn("/studio/topology", route_paths)
        self.assertIn("/studio/flow", route_paths)

    def test_topology_endpoint_returns_expected_graphs(self):
        client = TestClient(webapp.app)
        response = client.get("/studio/topology")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["view"]["primary_graph"], "archive_main")
        graph_ids = [graph["id"] for graph in payload["graphs"]]
        self.assertEqual(graph_ids, ["archive_main", "archive_draft", "archive_final", "archive_resume"])

    def test_flow_page_mentions_archive_workflow(self):
        client = TestClient(webapp.app)
        response = client.get("/studio/flow")
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("Archive workflow topology", body)
        self.assertIn("Develop.md Aligned", body)
        self.assertIn("hierarchical OCR / batch_supervisor / page_agent 工作流已移除", body)


if __name__ == "__main__":
    unittest.main()
