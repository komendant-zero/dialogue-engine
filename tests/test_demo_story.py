import json
import os
import unittest

class TestDemoStory(unittest.TestCase):
    def test_demo_story_valid_json(self):
        demo_path = os.path.join(os.path.dirname(__file__), "..", "examples", "demo_story.json")
        self.assertTrue(os.path.exists(demo_path), "examples/demo_story.json must exist")

        with open(demo_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("nodes", data)
        self.assertIn("connections", data)
        self.assertGreater(len(data["nodes"]), 0)
        self.assertGreater(len(data["connections"]), 0)

        node_ids = {n["id"] for n in data["nodes"]}
        # Verify that all connections reference existing nodes
        for c in data["connections"]:
            self.assertIn(c["from"], node_ids, f"Connection from '{c['from']}' not found in nodes")
            self.assertIn(c["to"], node_ids, f"Connection to '{c['to']}' not found in nodes")
            self.assertIn("out_idx", c)

        # Verify start node exists
        start_nodes = [n for n in data["nodes"] if n["title"].lower().strip() == "start"]
        self.assertEqual(len(start_nodes), 1, "There should be exactly one 'start' node")

        # Verify condition node exists
        cond_nodes = [n for n in data["nodes"] if n["type"] == "condition"]
        self.assertGreaterEqual(len(cond_nodes), 1, "Demo story should contain at least one condition node")

if __name__ == "__main__":
    unittest.main()
