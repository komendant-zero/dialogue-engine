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


if __name__ == "__main__":
    unittest.main()
