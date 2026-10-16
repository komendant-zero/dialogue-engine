"""
Unit tests for Russian Cyrillic keyboard layout hotkeys in Dialogue Engine.
"""

import unittest
import tkinter as tk
from ui.editor import ScenarioEditor


class MockKeyEvent:
    def __init__(self, state: int, keycode: int, keysym: str):
        self.state = state
        self.keycode = keycode
        self.keysym = keysym


class TestRussianHotkeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.app = ScenarioEditor()
            cls.app.withdraw()
        except tk.TclError:
            cls.app = None

    @classmethod
    def tearDownClass(cls):
        if cls.app:
            cls.app.destroy()

    def setUp(self):
        if not self.app:
            self.skipTest("Headless environment without display")
        self.app.nodes.clear()
        self.app.connections.clear()
        self.app.selected_nodes.clear()
        self.app.clipboard.clear()
        self.app._last_hotkey_time = 0.0

    def test_hotkey_registration_and_cyrillic_keysyms(self):
        """Проверяет, что все основные хоткеи зарегистрированы как по keycode, так и по кириллическим keysyms."""
        # Keycode checks (layout-independent Windows VK codes)
        self.assertIn((True, False, 67), self.app._hotkey_actions)  # Ctrl+C
        self.assertIn((True, False, 86), self.app._hotkey_actions)  # Ctrl+V
        self.assertIn((True, False, 90), self.app._hotkey_actions)  # Ctrl+Z
        self.assertIn((True, False, 89), self.app._hotkey_actions)  # Ctrl+Y
        self.assertIn((True, False, 83), self.app._hotkey_actions)  # Ctrl+S
        self.assertIn((True, False, 79), self.app._hotkey_actions)  # Ctrl+O
        self.assertIn((True, False, 70), self.app._hotkey_actions)  # Ctrl+F
        self.assertIn((True, False, 68), self.app._hotkey_actions)  # Ctrl+D
        self.assertIn((True, False, 65), self.app._hotkey_actions)  # Ctrl+A
        self.assertIn((True, False, 76), self.app._hotkey_actions)  # Ctrl+L (AutoLayout)
        self.assertIn((False, False, 46), self.app._hotkey_actions)  # Delete

        # Cyrillic keysym checks
        self.assertIn((True, False, "Cyrillic_es"), self.app._hotkey_actions)
        self.assertIn((True, False, "Cyrillic_em"), self.app._hotkey_actions)
        self.assertIn((True, False, "Cyrillic_ya"), self.app._hotkey_actions)
        self.assertIn((True, False, "Cyrillic_de"), self.app._hotkey_actions)

    def test_russian_layout_node_operations(self):
        """Проверяет выполнение операций с нодами через русские сочетания клавиш."""
        node = self.app.add_node("story", x=100, y=100, title="Node 1", content="Text 1")
        self.assertEqual(len(self.app.nodes), 1)

        # 1. Ctrl+A (Выделить все): keycode 65, state 4
        self.app.on_key_press(MockKeyEvent(state=4, keycode=65, keysym="??"))
        self.assertEqual(len(self.app.selected_nodes), 1)
        self.assertEqual(self.app.selected_nodes[0], node)

        # 2. Ctrl+C (Копировать): keycode 67, state 4
        self.app._last_hotkey_time = 0.0
        self.app.on_key_press(MockKeyEvent(state=4, keycode=67, keysym="??"))
        self.assertIsNotNone(self.app.clipboard.get("nodes"))
        self.assertEqual(len(self.app.clipboard["nodes"]), 1)

        # 3. Ctrl+V (Вставить): keycode 86, state 4
        self.app._last_hotkey_time = 0.0
        self.app.on_key_press(MockKeyEvent(state=4, keycode=86, keysym="??"))
        self.assertEqual(len(self.app.nodes), 2)

        # 4. Ctrl+Z (Отмена): keycode 90, state 4
        self.app._last_hotkey_time = 0.0
        self.app.on_key_press(MockKeyEvent(state=4, keycode=90, keysym="??"))
        self.assertEqual(len(self.app.nodes), 1)

        # 5. Ctrl+Y (Повтор): keycode 89, state 4
        self.app._last_hotkey_time = 0.0
        self.app.on_key_press(MockKeyEvent(state=4, keycode=89, keysym="??"))
        self.assertEqual(len(self.app.nodes), 2)

        # 6. Delete (Удалить выделенное): keycode 46, state 0
        self.app.selected_nodes = [self.app.nodes[1]]
        self.app._last_hotkey_time = 0.0
        self.app.on_key_press(MockKeyEvent(state=0, keycode=46, keysym="Delete"))
        self.assertEqual(len(self.app.nodes), 1)

    def test_node_creation_hotkeys(self):
        """Проверяет создание нод по горячим клавишам (1 - Сюжет, 2 - Выбор, 3 - Условие, 4 - Музыка)."""
        # Клавиша '1' -> Сюжет
        self.app._last_hotkey_time = 0.0
        res = self.app.on_key_press(MockKeyEvent(state=0, keycode=49, keysym="1"))
        self.assertEqual(res, "break")
        self.assertEqual(len(self.app.nodes), 1)
        self.assertEqual(self.app.nodes[0].node_type, "story")

        # Клавиша '2' -> Выбор
        self.app._last_hotkey_time = 0.0
        res = self.app.on_key_press(MockKeyEvent(state=0, keycode=50, keysym="2"))
        self.assertEqual(res, "break")
        self.assertEqual(len(self.app.nodes), 2)
        self.assertEqual(self.app.nodes[1].node_type, "choice")

        # Клавиша '3' -> Условие
        self.app._last_hotkey_time = 0.0
        res = self.app.on_key_press(MockKeyEvent(state=0, keycode=51, keysym="3"))
        self.assertEqual(res, "break")
        self.assertEqual(len(self.app.nodes), 3)
        self.assertEqual(self.app.nodes[2].node_type, "condition")

        # Клавиша '4' -> Музыка
        self.app._last_hotkey_time = 0.0
        res = self.app.on_key_press(MockKeyEvent(state=0, keycode=52, keysym="4"))
        self.assertEqual(res, "break")
        self.assertEqual(len(self.app.nodes), 4)
        self.assertEqual(self.app.nodes[3].node_type, "music")

    def test_custom_hotkeys_rebind_and_settings(self):
        """Проверяет динамическое переназначение горячих клавиш через HotkeyManager."""
        self.app.hotkey_manager.hotkeys["add_story"] = "Ctrl+Shift+S"
        self.app.reload_hotkeys()
        self.app.nodes.clear()

        # Старая клавиша '1' не должна создавать ноду
        self.app._last_hotkey_time = 0.0
        self.app.on_key_press(MockKeyEvent(state=0, keycode=49, keysym="1"))
        self.assertEqual(len(self.app.nodes), 0)

        # Новая клавиша 'Ctrl+Shift+S' (state 5, keycode 83) должна создать сюжетную ноду
        self.app._last_hotkey_time = 0.0
        res = self.app.on_key_press(MockKeyEvent(state=5, keycode=83, keysym="??"))
        self.assertEqual(res, "break")
        self.assertEqual(len(self.app.nodes), 1)
        self.assertEqual(self.app.nodes[0].node_type, "story")

        # Сброс к значениям по умолчанию
        self.app.hotkey_manager.reset_to_defaults()
        self.app.reload_hotkeys()

    def test_hotkey_settings_dialog_ui(self):
        """Проверяет открытие и поиск в окне настроек горячих клавиш."""
        from ui.dialogs.hotkey_settings import HotkeySettingsDialog
        dlg = HotkeySettingsDialog(self.app, self.app)
        self.assertIsNotNone(dlg.dialog)
        self.assertGreater(len(dlg.tree.get_children()), 10)

        # Фильтр поиска
        dlg.e_search.insert(0, "сюжет")
        dlg._populate_tree()
        children = dlg.tree.get_children()
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0], "add_story")

        dlg.dialog.destroy()


if __name__ == "__main__":
    unittest.main()
