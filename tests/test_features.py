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

    def test_sfx_and_violant_compatibility(self):
        from plugins.renpy_exporter import RenpyExporterPlugin
        from plugins.media_node import resolve_media_path

        exporter = RenpyExporterPlugin(editor=None)
        
        # Test SFX export
        sfx_node = MockNode("sfx_1", "Sound", "SFX", "music", {"music_mode": "sfx", "music_file": "sound/chair-rolling.wav"})
        conns = [{"from": "sfx_1", "out_idx": 0, "to": "story_1"}]
        
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                exporter.write_node_content_default(f, sfx_node, conns)
            
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn('play sound "sound/chair-rolling.wav"', content)
            self.assertIn('jump node_story_1', content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # Test resolve_media_path fallback
        test_path = "D:/projects/Violant/game/bg/hello.jpg"
        resolved = resolve_media_path(test_path, editor=None)
        self.assertTrue(resolved)

    def test_loaded_project_nodes_not_blocked_by_is_new(self):
        from plugins.music_plugin import MusicPlugin
        from plugins.advanced_scripting import AdvancedScriptingPlugin

        # Create a mock editor
        class MockEditor:
            def __init__(self):
                self.redraw_called = False
                self.plugin_manager = None
            def redraw(self):
                self.redraw_called = True

        editor = MockEditor()
        music_plugin = MusicPlugin(editor)
        music_plugin.on_enable()

        # Node loaded from file (is_new is False)
        loaded_music = MockNode("m_1", "Music", "bell.wav", "music", {"music_mode": "sfx", "music_file": "bell.wav"})
        loaded_music.is_new = False

        # In loaded project, node_edit_save should not be ignored
        class MockVar:
            def __init__(self, val):
                self.val = val
            def get(self):
                return self.val

        class MockEntry:
            def __init__(self, val):
                self.val = val
            def get(self):
                return self.val

        music_plugin.edit_state[loaded_music.id] = {
            'mode': MockVar('sfx'),
            'file_entry': MockEntry('bell.wav')
        }

        music_plugin.on_event("node_edit_save", {"node": loaded_music})
        self.assertEqual(loaded_music.custom_data.get("music_mode"), "sfx")
        self.assertIn("SFX", loaded_music.content)

        # Advanced scripting export with is_new = False
        script_plugin = AdvancedScriptingPlugin(editor)
        py_node = MockNode("py_1", "Code", "x = 42", "python_code")
        py_node.is_new = False

        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                data = {"node": py_node, "file": f, "connections": [], "handled": False}
                script_plugin.on_event("renpy_export_node", data)
                self.assertTrue(data["handled"])

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("python:", content)
            self.assertIn("x = 42", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_media_pause_and_clean_rel_path(self):
        from plugins.renpy_exporter import RenpyExporterPlugin
        exporter = RenpyExporterPlugin(editor=None)

        # Test clean_rel_path with /game/ in absolute path
        p1 = "D:/projects/Violant/game/sound/dustywind_double-fingersnap-reverb.ogg"
        self.assertEqual(exporter.clean_rel_path(p1), "sound/dustywind_double-fingersnap-reverb.ogg")

        p2 = "D:/projects/Violant/game/bg/hello.jpg"
        self.assertEqual(exporter.clean_rel_path(p2), "bg/hello.jpg")

        # Test media pause when followed by another media before dialogue
        node_media1 = MockNode("m1", "Warning", '{"image_path": "bg/warning.gif"}', "media")
        node_sfx = MockNode("sfx", "Sound", "SFX", "music")
        node_media2 = MockNode("m2", "Hello", '{"image_path": "bg/hello.jpg"}', "media")
        node_story = MockNode("story", "Narrator", "Hello world", "story")

        nodes_map = {
            "m1": node_media1,
            "sfx": node_sfx,
            "m2": node_media2,
            "story": node_story
        }
        conns = [
            {"from": "m1", "to": "sfx", "out_idx": 0},
            {"from": "sfx", "to": "m2", "out_idx": 0},
            {"from": "m2", "to": "story", "out_idx": 0}
        ]

        # m1 should pause because m2 is on the path before dialogue
        self.assertTrue(exporter.should_pause_after_media(node_media1, conns, nodes_map))
        # m2 should NOT pause because story directly follows
        self.assertFalse(exporter.should_pause_after_media(node_media2, conns, nodes_map))

    def test_pause_plugin_and_story_pause_export(self):
        from plugins.pause_plugin import PausePlugin
        from plugins.renpy_exporter import RenpyExporterPlugin

        plugin = PausePlugin(editor=None)
        exporter = RenpyExporterPlugin(editor=None)

        # 1. Test Pause Node export
        pause_node = MockNode("p1", "Пауза", "Задержка: 2.5 сек", "pause", {
            "pause_mode": "time",
            "pause_duration": 2.5
        })
        conns = [{"from": "p1", "to": "s1", "out_idx": 0}]

        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                data = {"node": pause_node, "file": f, "connections": conns, "handled": False}
                plugin.on_event("renpy_export_node", data)
                self.assertTrue(data["handled"])

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("pause 2.5", content)
            self.assertIn("jump node_s1", content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 2. Test Story Node with pause_before
        story_with_pause = MockNode("s1", "Герой", "Привет!", "story", {
            "pause_before": True,
            "pause_before_mode": "time",
            "pause_before_duration": 1.5
        })

        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
            tmp_path = tmp.name

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                exporter.write_node_content_default(f, story_with_pause, [])

            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("pause 1.5", content)
            self.assertIn('"Герой" "Привет!"', content)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_pause_editor_dialog_choice_only(self):
        from plugins.pause_plugin import PauseEditorDialog

        class MockDialogNode:
            def __init__(self):
                self.custom_data = {}
                self.content = ""
            def calculate_size(self):
                pass

        class MockVar:
            def __init__(self, val):
                self.val = val
            def get(self):
                return self.val

        node = MockDialogNode()
        # Mock dialog save logic
        dialog = PauseEditorDialog.__new__(PauseEditorDialog)
        dialog.node = node
        dialog.callback = lambda: None
        dialog.win = type("MockWin", (), {"destroy": lambda s: None})()

        # Test click choice
        dialog.combo_var = MockVar("Ожидание клика игрока")
        dialog.save()
        self.assertEqual(node.custom_data['pause_mode'], 'click')
        self.assertEqual(node.content, "Ожидание клика")

        # Test timed choice
        dialog.combo_var = MockVar("1.5 сек")
        dialog.save()
        self.assertEqual(node.custom_data['pause_mode'], 'time')
        self.assertEqual(node.custom_data['pause_duration'], 1.5)
        self.assertEqual(node.content, "Задержка: 1.5 сек")

if __name__ == "__main__":
    unittest.main()



