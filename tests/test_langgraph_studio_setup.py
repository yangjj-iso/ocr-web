import unittest

from app.studio import langgraph_graphs, webapp


class LangGraphStudioSetupTests(unittest.TestCase):
    def test_graph_exports_exist(self):
        self.assertIsNotNone(langgraph_graphs.batch_supervisor_graph)
        self.assertIsNotNone(langgraph_graphs.page_agent_graph)

    def test_webapp_exposes_info_endpoint_definition(self):
        route_paths = {route.path for route in webapp.app.routes}
        self.assertIn("/health/live", route_paths)
        self.assertIn("/studio/info", route_paths)


if __name__ == "__main__":
    unittest.main()
