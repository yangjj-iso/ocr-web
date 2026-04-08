import unittest

from app.core.ocr_engine import _map_baidu_page


class BaiduPageMappingTests(unittest.TestCase):
    def test_map_page_handles_nested_polygon_locations(self):
        page = {
            "layouts": [
                {
                    "layout_id": "layout-1",
                    "type": "text",
                    "position": [[[10, 20], [110, 20], [110, 60], [10, 60]]],
                    "text": "测试文本",
                    "span_boxes": [
                        {
                            "text": "测试片段",
                            "location": [[[12, 22], [50, 22], [50, 36], [12, 36]]],
                        }
                    ],
                }
            ],
            "tables": [],
            "images": [],
        }

        mapped = _map_baidu_page(page)
        self.assertEqual(len(mapped["regions"]), 1)
        region = mapped["regions"][0]
        self.assertEqual(region["bbox"], [10.0, 20.0, 110.0, 60.0])
        self.assertEqual(region["region_lines"][0]["bbox"], [12.0, 22.0, 50.0, 36.0])

    def test_map_page_handles_invalid_span_location_without_crash(self):
        page = {
            "layouts": [
                {
                    "layout_id": "layout-2",
                    "type": "text",
                    "position": [0, 0, 100, 40],
                    "text": "示例",
                    "span_boxes": [
                        {"text": "片段A", "location": [10, 10, 30, 15]},
                        {"text": "片段B", "location": [[["bad"]]]},
                    ],
                }
            ],
            "tables": [],
            "images": [],
        }

        mapped = _map_baidu_page(page)
        self.assertEqual(len(mapped["regions"]), 1)
        region_lines = mapped["regions"][0]["region_lines"]
        self.assertEqual(len(region_lines), 2)
        self.assertEqual(region_lines[0]["bbox"], [10.0, 10.0, 40.0, 25.0])
        self.assertEqual(region_lines[1]["bbox"], [])


if __name__ == "__main__":
    unittest.main()
