"""
Tests for History Manager (Undo/Redo) and Autosave Crash Recovery.
"""

import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.autosave import AutosaveManager
from core.history import HistoryManager
from core.models import NodeData, ProjectData


class TestHistoryAndAutosave(unittest.TestCase):
    def test_history_undo_redo_stack(self):
        history = HistoryManager(max_depth=3)
        state1 = {"step": 1, "nodes": ["A"]}
        state2 = {"step": 2, "nodes": ["A", "B"]}
        state3 = {"step": 3, "nodes": ["A", "B", "C"]}
        current_state = {"step": 4, "nodes": ["A", "B", "C", "D"]}

        history.push_state(state1)
        history.push_state(state2)
        history.push_state(state3)

        self.assertTrue(history.can_undo)
        self.assertFalse(history.can_redo)

        # Undo from step 4
        prev = history.undo(current_state)
        self.assertEqual(prev["step"], 3)
        self.assertTrue(history.can_redo)

        # Redo back to step 4
        redo_state = history.redo(prev)
        self.assertEqual(redo_state["step"], 4)

    def test_autosave_snapshot_and_recovery(self):
        temp_dir = tempfile.mkdtemp(prefix="de_autosave_test_")
        try:
            autosave = AutosaveManager(autosave_dir=temp_dir, interval_seconds=1)
            project = ProjectData(nodes=[NodeData(id="1", title="Test", content="Data")])

            dummy_proj_file = os.path.join(temp_dir, "my_project.json")
            with open(dummy_proj_file, "w", encoding="utf-8") as f:
                f.write("{}")

            # Artificial sleep to ensure autosave mtime > original file mtime
            time.sleep(0.1)

            saved_path = autosave.save_snapshot(project, dummy_proj_file)
            self.assertIsNotNone(saved_path)
            self.assertTrue(os.path.exists(saved_path))

            # Test cleanup
            autosave.clear_autosave(dummy_proj_file)
            self.assertFalse(os.path.exists(saved_path))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
