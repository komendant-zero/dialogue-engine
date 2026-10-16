"""
Tests for Project Serialization, Deserialization, and Robustness.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models import ConnectionData, NodeData, ProjectData
from core.serialization import ProjectSerializer, SerializationError


class TestSerialization(unittest.TestCase):
    def test_roundtrip_serialization(self):
        n1 = NodeData(id="n1", title="Start", content="Hello world", node_type="story", custom_data={"bg_color": "#123456"})
        n2 = NodeData(id="n2", title="Choice", content="Option A\nOption B", node_type="choice")
        c1 = ConnectionData(from_node="n1", out_idx=0, to_node="n2")

        original_project = ProjectData(nodes=[n1, n2], connections=[c1])

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            ProjectSerializer.save_to_file(original_project, tmp_path)
            loaded_project = ProjectSerializer.load_from_file(tmp_path)

            self.assertEqual(len(loaded_project.nodes), 2)
            self.assertEqual(len(loaded_project.connections), 1)

            loaded_n1 = next(n for n in loaded_project.nodes if n.id == "n1")
            self.assertEqual(loaded_n1.title, "Start")
            self.assertEqual(loaded_n1.content, "Hello world")
            self.assertEqual(loaded_n1.custom_data.get("bg_color"), "#123456")

            self.assertEqual(loaded_project.connections[0].from_node, "n1")
            self.assertEqual(loaded_project.connections[0].to_node, "n2")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(f"{tmp_path}.bak"):
                os.remove(f"{tmp_path}.bak")

    def test_corrupt_json_handling(self):
        corrupt_json = "{'nodes': [ broken json ... "
        with self.assertRaises(SerializationError):
            ProjectSerializer.load_from_json(corrupt_json)

    def test_broken_connections_cleaned(self):
        data = {
            "nodes": [
                {"id": "n1", "x": 0, "y": 0, "title": "A", "content": "", "type": "story"}
            ],
            "connections": [
                {"from": "n1", "out_idx": 0, "to": "non_existent_node_id"}
            ]
        }
        json_str = json.dumps(data)
        project = ProjectSerializer.load_from_json(json_str)
        self.assertEqual(len(project.nodes), 1)
        # Dangling connection to non-existent node should be filtered out
        self.assertEqual(len(project.connections), 0)

    def test_load_real_violant_project(self):
        violant_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "violant.json"))
        if os.path.exists(violant_path):
            project = ProjectSerializer.load_from_file(violant_path)
            self.assertTrue(len(project.nodes) > 0)
            self.assertTrue(len(project.connections) > 0)

    def test_node_id_preservation_and_determinism(self):
        from ui.node_view import Node

        class DummyEditor:
            def __init__(self):
                self.zoom_level = 1.0

        dummy = DummyEditor()
        # Explicit ID should be preserved
        n = Node(dummy, 100, 200, "Node A", "Content", "story", node_id="custom_fixed_id_123")
        self.assertEqual(n.id, "custom_fixed_id_123")

        data = n.to_node_data()
        self.assertEqual(data.id, "custom_fixed_id_123")

        reconstructed = Node.from_node_data(dummy, data)
        self.assertEqual(reconstructed.id, "custom_fixed_id_123")


if __name__ == "__main__":
    unittest.main()
