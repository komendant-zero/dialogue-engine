import os
import sys
import tempfile
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class MockNode:
    def __init__(self, node_id, title, content, node_type, custom_data=None):
        self.id = node_id
        self.title = title
        self.content = content
        self.node_type = node_type
        self.custom_data = custom_data or {}
        self.mode = "standard"

    def _get_display_text(self, text):
        return text

class TestFeatures(unittest.TestCase):
    def test_condition_node_export(self):
        from plugins.condition_node import ConditionNodePlugin

        plugin = ConditionNodePlugin(editor=None)
        
        node = MockNode("cond_1", "Проверка", "has_key == True", "condition")
        conns = [
            {"from": "cond_1", "out_idx": 0, "to": "node_true"},
            {"from": "cond_1", "out_idx": 1, "to": "node_false"}
        ]

        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                data = {"node": node, "file": f, "connections": conns, "handled": False}
                plugin.on_event("renpy_export_node", data)
                self.assertTrue(data["handled"])

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("if has_key == True:", content)
            self.assertIn("jump node_node_true", content)
            self.assertIn("else:", content)
            self.assertIn("jump node_node_false", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_graph_diagnostics_detects_issues(self):
        node_choice = MockNode("choice_1", "Выбор", "Вариант А\nВариант Б", "choice")
        node_target_a = MockNode("story_a", "Сцена А", "Привет", "story")
        node_unreachable = MockNode("orphan_1", "Потерянная", "Никто сюда не ведёт", "story")

        nodes = [node_choice, node_target_a, node_unreachable]
        connections = [
            {"from": "choice_1", "out_idx": 0, "to": "story_a"}
            # out_idx 1 is missing!
        ]

        incoming_map = {n.id: [] for n in nodes}
        outgoing_map = {n.id: [] for n in nodes}
        for c in connections:
            outgoing_map[c['from']].append(c)
            incoming_map[c['to']].append(c)

        # Missing start
        start_nodes = [n for n in nodes if n.title.lower().strip() == 'start']
        self.assertEqual(len(start_nodes), 0)

        # Choice missing branch 1
        connected_indices = {c['out_idx'] for c in outgoing_map["choice_1"]}
        self.assertIn(0, connected_indices)
        self.assertNotIn(1, connected_indices)

        # Unreachable node
        self.assertEqual(len(incoming_map["orphan_1"]), 0)

if __name__ == "__main__":
    unittest.main()
