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

    def test_special_node_types_export(self):
        exporter = RenPyExporter(plugin_manager=None)

        n_start = NodeData(id="start_node", title="start", content="Start", node_type="story")
        n_pause = NodeData(id="p_node", title="Pause", content="", node_type="pause", custom_data={"pause_mode": "time", "pause_duration": 3.5})
        n_anim = NodeData(id="a_node", title="Anim", content='{"animation": "fade to black", "duration": 1.0}', node_type="animation")
        n_cond = NodeData(id="c_node", title="Cond", content="score > 10", node_type="condition")
        n_py = NodeData(id="py_node", title="Code", content="x = 42\ny = 100", node_type="python_code")
        n_end1 = NodeData(id="end1", title="End1", content="End 1", node_type="story")
        n_end2 = NodeData(id="end2", title="End2", content="End 2", node_type="story")

        conns = [
            ConnectionData(from_node="start_node", out_idx=0, to_node="p_node"),
            ConnectionData(from_node="p_node", out_idx=0, to_node="a_node"),
            ConnectionData(from_node="a_node", out_idx=0, to_node="py_node"),
            ConnectionData(from_node="py_node", out_idx=0, to_node="c_node"),
            ConnectionData(from_node="c_node", out_idx=0, to_node="end1"),
            ConnectionData(from_node="c_node", out_idx=1, to_node="end2"),
        ]

        project = ProjectData(nodes=[n_start, n_pause, n_anim, n_cond, n_py, n_end1, n_end2], connections=conns)

        temp_dir = tempfile.mkdtemp(prefix="de_special_test_")
        try:
            success, msg = exporter.export(project, temp_dir)
            self.assertTrue(success)

            rpy_file = os.path.join(temp_dir, "script.rpy")
            with open(rpy_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("stop music fadeout 1.0", content)
            self.assertIn("pause 3.5", content)
            self.assertIn("scene black with Fade(0.50, 0.1, 0.50)", content)
            self.assertIn("python:\n        x = 42\n        y = 100", content)
            self.assertIn("if score > 10:\n        jump node_end1\n    else:\n        jump node_end2", content)
        finally:
            if os.path.exists(os.path.join(temp_dir, "script.rpy")):
                os.remove(os.path.join(temp_dir, "script.rpy"))
            os.rmdir(temp_dir)


if __name__ == "__main__":
    unittest.main()
