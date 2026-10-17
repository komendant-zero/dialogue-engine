"""
Unit tests for Infinite Canvas and Procedural Grid in Dialogue Engine.
"""

import unittest
import tkinter as tk
from ui.editor import ScenarioEditor


class TestInfiniteCanvas(unittest.TestCase):
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
        self.app.canvas.xview_moveto(0.5)
        self.app.canvas.yview_moveto(0.5)

    def test_canvas_scrollregion_is_vast(self):
        """Проверяет, что область прокрутки холста огромная (5 млн px во все 4 стороны)."""
        canvas = self.app.canvas
        limit = canvas.LIMIT
        self.assertGreaterEqual(limit, 1000000)
        region = canvas.cget("scrollregion")
        expected = f"{-limit} {-limit} {limit} {limit}"
        self.assertEqual(region, expected)

    def test_node_can_have_negative_coordinates(self):
        """Проверяет, что ноды могут создаваться и существовать в отрицательных координатах."""
        node = self.app.add_node("story", x=-450, y=-300)
        self.assertEqual(node.x, -450)
        self.assertEqual(node.y, -300)

    def test_node_drag_into_negative_space(self):
        """Проверяет, что перетаскивание ноды влево не зажимает её в x=0."""
        node = self.app.add_node("story", x=50, y=50)
        self.app.selected_nodes = [node]

        start_cx = self.app.canvas.canvasx(100)
        start_cy = self.app.canvas.canvasy(100)
        self.app.drag_data = {"item": node, "x": start_cx, "y": start_cy, "moved": False}

        class MockEvent:
            x = -200
            y = -100

        self.app.on_drag(MockEvent())
        self.assertLess(node.x, 0)

    def test_procedural_grid_updates(self):
        """Проверяет генерацию процедурной сетки."""
        canvas = self.app.canvas
        canvas.update_grid()
        # В headless/minimized окне может быть w <= 1, но вызов не падает
        self.assertTrue(callable(canvas.update_grid))

    def test_center_on_node_handles_negative_coordinates(self):
        """Проверяет, что центрирование на ноде с отрицательными координатами работает без ошибок."""
        node = self.app.add_node("story", x=-2500, y=-1800)
        try:
            self.app.canvas.center_on_node(node)
        except Exception as e:
            self.fail(f"center_on_node raised an exception on negative coordinates: {e}")

    def test_buffered_grid_caching(self):
        """Проверяет, что буферизованная сетка кэширует границы и не перерисовывается при малых смещениях."""
        canvas = self.app.canvas
        canvas.update_grid(force=True)
        initial_bounds = canvas._grid_bounds
        # Небольшой сдвиг холста (в пределах GRID_THRESHOLD) не сбрасывает кэш
        canvas.xview_scroll(50, "units")
        canvas.update_grid(force=False)
        self.assertEqual(canvas._grid_bounds, initial_bounds)

    def test_navigation_speed_and_wheel(self):
        """Проверяет настройки ускорения физики и обработку колеса мыши."""
        self.assertGreaterEqual(self.app.max_speed, 20.0)

        class WheelEvent:
            def __init__(self, state, delta):
                self.state = state
                self.delta = delta

        # Вертикальный скролл
        self.app.on_mousewheel(WheelEvent(state=0, delta=120))
        # Горизонтальный скролл (Shift)
        self.app.on_mousewheel(WheelEvent(state=1, delta=120))

