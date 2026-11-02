"""
Unit tests for Cowork Server, Session, and Auto-Updater.
"""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import NodeData, ProjectData
from core.updater import EngineUpdater
from cowork.session import CoworkSession


class TestEngineUpdater(unittest.TestCase):
    def test_get_local_commit(self):
        sha = EngineUpdater.get_local_commit()
        self.assertIsNotNone(sha)
        self.assertTrue(len(sha) >= 7)

    def test_check_for_updates_structure(self):
        # В песочнице сеть отключена, метод должен вернуть offline=True или error без падения
        res = EngineUpdater.check_for_updates(timeout_sec=1.0)
        self.assertIn("available", res)
        self.assertIn("local_sha", res)
        self.assertIn("offline", res)


class TestCoworkSession(unittest.TestCase):
    def setUp(self):
        self.test_save_file = os.path.join(os.getcwd(), "Save", "test_cowork_proj.json")
        self.session = CoworkSession(project_path=self.test_save_file)

    def tearDown(self):
        if os.path.exists(self.test_save_file):
            try:
                os.remove(self.test_save_file)
            except Exception:
                pass

    def test_create_and_move_node(self):
        async def run_test():
            # Добавление ноды
            node_payload = {
                "id": "test_node_1",
                "x": 150.0,
                "y": 250.0,
                "title": "Тестовый узел",
                "content": "Текст диалога",
                "type": "story",
                "mode": "standard"
            }
            await self.session.handle_message("client1", json.dumps({
                "type": "node_create",
                "node": node_payload
            }))

            # Проверяем наличие узла
            found = [n for n in self.session.project_data.nodes if n.id == "test_node_1"]
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].title, "Тестовый узел")

            # Перемещение узла
            await self.session.handle_message("client1", json.dumps({
                "type": "node_move",
                "id": "test_node_1",
                "x": 300.0,
                "y": 400.0
            }))

            self.assertEqual(found[0].x, 300.0)
            self.assertEqual(found[0].y, 400.0)

            # Создание связи
            await self.session.handle_message("client1", json.dumps({
                "type": "connection_create",
                "connection": {"from": "test_node_1", "out_idx": 0, "to": "start_node"}
            }))
            self.assertTrue(any(c.from_node == "test_node_1" for c in self.session.project_data.connections))

            # Удаление узла
            await self.session.handle_message("client1", json.dumps({
                "type": "node_delete",
                "id": "test_node_1"
            }))
            self.assertFalse(any(n.id == "test_node_1" for n in self.session.project_data.nodes))
            # Связи также должны быть удалены
            self.assertFalse(any(c.from_node == "test_node_1" for c in self.session.project_data.connections))

        asyncio.run(run_test())

    def test_save_to_disk(self):
        saved_path = self.session.save_to_disk()
        self.assertTrue(os.path.exists(saved_path))


class TestWebFiles(unittest.TestCase):
    def test_static_files_exist(self):
        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cowork", "static")
        self.assertTrue(os.path.exists(os.path.join(static_dir, "index.html")))
        self.assertTrue(os.path.exists(os.path.join(static_dir, "style.css")))
        self.assertTrue(os.path.exists(os.path.join(static_dir, "app.js")))

    def test_html_content(self):
        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cowork", "static")
        with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Dialogue Engine", content)
        self.assertIn("canvasContainer", content)
        self.assertIn("mobile-bottom-bar", content)


if __name__ == "__main__":
    unittest.main()
