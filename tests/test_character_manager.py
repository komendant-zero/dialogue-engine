"""
Dialogue Engine - Unit Tests for Character Manager (v2.2 Roadmap Feature).
Проверяет модель данных персонажей, бизнес-логику CharacterManager,
сканирование, пакетное переименование, окрашивание и сериализацию.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.characters import CharacterManager, DEFAULT_EMOTIONS
from core.models import CharacterData, ConnectionData, NodeData, ProjectData
from core.serialization import ProjectSerializer
from export.renpy_exporter import RenPyExporter


class TestCharacterManager(unittest.TestCase):
    def setUp(self):
        self.manager = CharacterManager()

    def test_character_data_serialization(self):
        char = CharacterData(
            name="Ривер",
            color="#0080ff",
            header_color="#0050aa",
            bg_color="#1a2530",
            avatar_path="sprites/river.png",
            emotions=["обычный", "радость", "злость"],
            description="Главный герой истории"
        )
        d = char.to_dict()
        self.assertEqual(d["name"], "Ривер")
        self.assertEqual(d["color"], "#0080ff")
        self.assertEqual(d["avatar_path"], "sprites/river.png")
        self.assertEqual(len(d["emotions"]), 3)

        restored = CharacterData.from_dict(d)
        self.assertEqual(restored.name, "Ривер")
        self.assertEqual(restored.color, "#0080ff")
        self.assertEqual(restored.description, "Главный герой истории")
        self.assertEqual(restored.emotions, ["обычный", "радость", "злость"])

    def test_manager_crud_operations(self):
        c1 = CharacterData(name="Ника", color="#00ffff")
        c2 = CharacterData(name="Джен", color="#ffff00")

        self.assertTrue(self.manager.add(c1))
        self.assertTrue(self.manager.add(c2))
        self.assertFalse(self.manager.add(CharacterData(name="Ника")))  # Дубликат не должен добавляться

        self.assertEqual(len(self.manager.list()), 2)
        self.assertIn("Ника", self.manager.names())
        self.assertIn("Джен", self.manager.names())

        # Поиск (включая регистронезависимый)
        found = self.manager.get("ника")
        self.assertIsNotNone(found)
        self.assertEqual(found.color, "#00ffff")

        # Обновление
        c1_updated = CharacterData(name="Вероника", color="#00e5ff", description="Сестра")
        self.assertTrue(self.manager.update("Ника", c1_updated))
        self.assertIsNone(self.manager.get("Ника"))
        self.assertIsNotNone(self.manager.get("Вероника"))
        self.assertEqual(self.manager.get("Вероника").description, "Сестра")

        # Удаление
        self.assertTrue(self.manager.delete("Вероника"))
        self.assertIsNone(self.manager.get("Вероника"))
        self.assertEqual(len(self.manager.list()), 1)

    def test_scan_from_nodes(self):
        nodes = [
            NodeData(id="1", title="Ривер", content="Привет!", node_type="story", custom_data={"header_text_color": "#0080ff"}),
            NodeData(id="2", title="Ника", content="Здравствуй!", node_type="story", custom_data={"header_text_color": "#00ffff"}),
            NodeData(id="3", title="Ривер", content="Как дела?", node_type="story"),
            NodeData(id="4", title="# Мысли", content="Она молчит", node_type="story"),  # Комментарий автора
            NodeData(id="5", title="Выбор", content="Ответить\nУйти", node_type="choice"),  # Не story
        ]

        added = self.manager.scan_from_nodes(nodes)
        self.assertEqual(len(added), 2)
        self.assertIn("Ривер", self.manager.names())
        self.assertIn("Ника", self.manager.names())
        self.assertNotIn("# Мысли", self.manager.names())
        self.assertNotIn("Выбор", self.manager.names())

        river = self.manager.get("Ривер")
        self.assertEqual(river.color, "#0080ff")

        # Повторное сканирование не дублирует
        added_second = self.manager.scan_from_nodes(nodes)
        self.assertEqual(len(added_second), 0)

    def test_batch_rename(self):
        nodes = [
            NodeData(id="1", title="Джен", content="Привет!", node_type="story"),
            NodeData(id="2", title="Ника", content="Привет!", node_type="story"),
            NodeData(id="3", title="Джен", content="Пойдем?", node_type="story"),
            NodeData(id="4", title="Джен", content="Выбор пути", node_type="choice"),  # Choice узел не должен переименовываться
        ]
        self.manager.add(CharacterData(name="Джен", color="#ffff00"))

        updated_count = self.manager.batch_rename("Джен", "Дженнифер", nodes)
        self.assertEqual(updated_count, 2)
        self.assertEqual(nodes[0].title, "Дженнифер")
        self.assertEqual(nodes[1].title, "Ника")
        self.assertEqual(nodes[2].title, "Дженнифер")
        self.assertEqual(nodes[3].title, "Джен")  # Не story

        # Проверяем, что в менеджере персонаж тоже переименован
        self.assertIsNone(self.manager.get("Джен"))
        self.assertIsNotNone(self.manager.get("Дженнифер"))

    def test_apply_color_to_nodes(self):
        nodes = [
            NodeData(id="1", title="Энджи", content="1", node_type="story", custom_data={}),
            NodeData(id="2", title="Энджи", content="2", node_type="story", custom_data={}),
            NodeData(id="3", title="Ника", content="3", node_type="story", custom_data={}),
        ]

        count = self.manager.apply_color_to_nodes("Энджи", "#c060f8", nodes)
        self.assertEqual(count, 2)
        self.assertEqual(nodes[0].custom_data.get("header_text_color"), "#c060f8")
        self.assertEqual(nodes[1].custom_data.get("header_text_color"), "#c060f8")
        self.assertNotIn("header_text_color", nodes[2].custom_data)

    def test_project_serialization_with_characters(self):
        char1 = CharacterData(name="Ривер", color="#0080ff", emotions=["обычный", "радость"])
        char2 = CharacterData(name="Ника", color="#00ffff", emotions=["обычный", "грусть"])

        node = NodeData(id="n1", title="Ривер", content="Привет", node_type="story")
        project = ProjectData(nodes=[node], connections=[], characters=[char1, char2])

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            ProjectSerializer.save_to_file(project, tmp_path)
            loaded = ProjectSerializer.load_from_file(tmp_path)

            self.assertEqual(len(loaded.characters), 2)
            c_river = next(c for c in loaded.characters if c.name == "Ривер")
            self.assertEqual(c_river.color, "#0080ff")
            self.assertEqual(c_river.emotions, ["обычный", "радость"])
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if os.path.exists(f"{tmp_path}.bak"):
                os.remove(f"{tmp_path}.bak")

    def test_backward_compatibility_old_project_without_characters(self):
        # Старый JSON без ключа 'characters'
        old_json = """
        {
            "metadata": {"title": "Старый проект"},
            "nodes": [
                {"id": "n1", "x": 0, "y": 0, "title": "Ривер", "content": "Текст", "type": "story"}
            ],
            "connections": []
        }
        """
        project = ProjectSerializer.load_from_json(old_json)
        self.assertEqual(len(project.characters), 0)
        self.assertEqual(len(project.nodes), 1)

    def test_renpy_export_character_definitions(self):
        exporter = RenPyExporter()
        char1 = CharacterData(name="Ривер", color="#0080ff")
        char2 = CharacterData(name="Ника", color="#00ffff")

        n1 = NodeData(id="start_node", title="start", content="Start", node_type="story")
        project = ProjectData(nodes=[n1], connections=[], characters=[char1, char2])

        temp_dir = tempfile.mkdtemp(prefix="de_char_export_")
        try:
            success, msg = exporter.export(project, temp_dir)
            self.assertTrue(success)

            rpy_file = os.path.join(temp_dir, "script.rpy")
            with open(rpy_file, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn('define river = Character("Ривер", color="#0080ff")', content)
            self.assertIn('define nika = Character("Ника", color="#00ffff")', content)
            self.assertIn("label start:", content)
        finally:
            if os.path.exists(os.path.join(temp_dir, "script.rpy")):
                os.remove(os.path.join(temp_dir, "script.rpy"))
            os.rmdir(temp_dir)


if __name__ == "__main__":
    unittest.main()
