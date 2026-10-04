"""
Tests for Core RenPyExporter.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models import ConnectionData, NodeData, ProjectData
from export.renpy_exporter import RenPyExporter


class TestRenpyExporterV2(unittest.TestCase):
    def test_full_project_export(self):
        exporter = RenPyExporter(plugin_manager=None)

        n1 = NodeData(id="start_node", title="start", content="Начало истории", node_type="story")
        n2 = NodeData(id="choice_node", title="Выбор пути", content="Пойти налево\nПойти направо", node_type="choice")
        n3 = NodeData(id="left_branch", title="Лес", content="Вы в тёмном лесу", node_type="story")
        n4 = NodeData(id="right_branch", title="Замок", content="Вы у ворот замка", node_type="story")

        c1 = ConnectionData(from_node="start_node", out_idx=0, to_node="choice_node")
        c2 = ConnectionData(from_node="choice_node", out_idx=0, to_node="left_branch")
        c3 = ConnectionData(from_node="choice_node", out_idx=1, to_node="right_branch")

        project = ProjectData(nodes=[n1, n2, n3, n4], connections=[c1, c2, c3])

        temp_dir = tempfile.mkdtemp(prefix="de_export_test_")
        try:
            success, msg = exporter.export(project, temp_dir)
            self.assertTrue(success)

            rpy_file = os.path.join(temp_dir, "script.rpy")
            self.assertTrue(os.path.exists(rpy_file))

            with open(rpy_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("label start:", content)
            self.assertIn("jump node_start_node", content)
            self.assertIn('"Начало истории"', content)
            self.assertIn("menu:", content)
            self.assertIn('"Пойти налево":', content)
            self.assertIn("jump node_left_branch", content)
            self.assertIn('"Пойти направо":', content)
            self.assertIn("jump node_right_branch", content)
        finally:
            if os.path.exists(os.path.join(temp_dir, "script.rpy")):
                os.remove(os.path.join(temp_dir, "script.rpy"))
            os.rmdir(temp_dir)

    def test_clean_rel_path_utility(self):
        p1 = "D:/projects/MyGame/game/images/bg/forest.png"
        self.assertEqual(RenPyExporter.clean_rel_path(p1), "images/bg/forest.png")

        p2 = "game/sound/click.ogg"
        self.assertEqual(RenPyExporter.clean_rel_path(p2), "sound/click.ogg")


if __name__ == "__main__":
    unittest.main()
