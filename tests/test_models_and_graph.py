"""
Tests for Core Models and Graph Logic.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models import ConnectionData, NodeData, ProjectData, ProjectMetadata
from core.graph import GraphModel


class TestCoreModelsAndGraph(unittest.TestCase):
    def test_node_data_serialization(self):
        node = NodeData(
            id="node_123",
            x=150.0,
            y=250.0,
            title="Герой",
            content="Привет мир!",
            node_type="story",
            custom_data={"bg_color": "#ff0000"}
        )
        d = node.to_dict()
        self.assertEqual(d["id"], "node_123")
        self.assertEqual(d["x"], 150.0)
        self.assertEqual(d["y"], 250.0)
        self.assertEqual(d["title"], "Герой")
        self.assertEqual(d["type"], "story")
        self.assertEqual(d["custom_data"]["bg_color"], "#ff0000")
        self.assertTrue(d["is_character"])

        restored = NodeData.from_dict(d)
        self.assertEqual(restored.id, "node_123")
        self.assertEqual(restored.title, "Герой")
        self.assertEqual(restored.content, "Привет мир!")

    def test_graph_add_and_remove_node(self):
        graph = GraphModel()
        n1 = NodeData(id="n1", title="Start", content="Start text", node_type="story")
        n2 = NodeData(id="n2", title="End", content="End text", node_type="story")

        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_connection("n1", 0, "n2")

        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(len(graph.connections), 1)

        # Removing n1 should also remove connection
        graph.remove_node("n1")
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(len(graph.connections), 0)

    def test_start_nodes_and_reachability(self):
        graph = GraphModel()
        n_start = NodeData(id="start", title="Start", content="", node_type="story")
        n_mid = NodeData(id="mid", title="Mid", content="", node_type="story")
        n_orphan = NodeData(id="orphan", title="Orphan", content="", node_type="story")

        graph.add_node(n_start)
        graph.add_node(n_mid)
        graph.add_node(n_orphan)

        graph.add_connection("start", 0, "mid")

        start_nodes = graph.get_start_nodes()
        self.assertEqual(len(start_nodes), 1)
        self.assertEqual(start_nodes[0].id, "start")

        reachable = graph.get_reachable_nodes()
        self.assertIn("start", reachable)
        self.assertIn("mid", reachable)
        self.assertNotIn("orphan", reachable)

        unreachable = graph.get_unreachable_nodes()
        self.assertEqual(len(unreachable), 1)
        self.assertEqual(unreachable[0].id, "orphan")

    def test_cycle_detection(self):
        graph = GraphModel()
        n1 = NodeData(id="1", title="1", content="", node_type="story")
        n2 = NodeData(id="2", title="2", content="", node_type="story")
        n3 = NodeData(id="3", title="3", content="", node_type="story")

        graph.add_node(n1)
        graph.add_node(n2)
        graph.add_node(n3)

        graph.add_connection("1", 0, "2")
        graph.add_connection("2", 0, "3")
        graph.add_connection("3", 0, "1")

        cycles = graph.detect_cycles()
        self.assertTrue(len(cycles) > 0)
        self.assertIn("1", cycles[0])
        self.assertIn("2", cycles[0])
        self.assertIn("3", cycles[0])

    def test_graph_validation(self):
        graph = GraphModel()
        choice_node = NodeData(id="c1", title="Выбор", content="Вариант 1\nВариант 2\nВариант 3", node_type="choice")
        target_node = NodeData(id="t1", title="Target", content="Ok", node_type="story")

        graph.add_node(choice_node)
        graph.add_node(target_node)
        # Connect only option 0
        graph.add_connection("c1", 0, "t1")

        issues = graph.validate()
        warnings = [i for i in issues if i.level == "warning"]
        # Should warn about option 1 and option 2 not connected
        missing_choice_warnings = [w for w in warnings if "вариант #" in w.message.lower()]
        self.assertEqual(len(missing_choice_warnings), 2)


if __name__ == "__main__":
    unittest.main()
