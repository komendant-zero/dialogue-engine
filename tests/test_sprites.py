"""
Dialogue Engine - Unit Tests for Auto Sprite Resolver and Export.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.models import ConnectionData, NodeData, ProjectData
from core.sprites import SpriteResolver
from export.renpy_exporter import RenPyExporter


class TestSpriteResolver(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="de_sprite_test_")
        # Создаем структуру:
        # temp_dir/
        #   enjie_neutral.png
        #   river_happy.png
        #   nika/
        #     nika_pose_01.png
        #     nika_pose_02.png
        #     pose_03.png
        open(os.path.join(self.temp_dir, "enjie_neutral.png"), "w").close()
        open(os.path.join(self.temp_dir, "river_happy.png"), "w").close()

        nika_dir = os.path.join(self.temp_dir, "nika")
        os.makedirs(nika_dir, exist_ok=True)
        open(os.path.join(nika_dir, "nika_pose_01.png"), "w").close()
        open(os.path.join(nika_dir, "nika_pose_02.png"), "w").close()
        open(os.path.join(nika_dir, "pose_03.png"), "w").close()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_transliterate(self):
        self.assertEqual(SpriteResolver.transliterate("Ника"), "nika")
        self.assertEqual(SpriteResolver.transliterate("Ривер"), "river")
        self.assertEqual(SpriteResolver.transliterate("Энджи"), "endzhi")

    def test_name_variants(self):
        variants_enjie = SpriteResolver.get_name_variants("Энджи")
        self.assertIn("enjie", variants_enjie)
        self.assertIn("энджи", variants_enjie)

        variants_nika = SpriteResolver.get_name_variants("Ника")
        self.assertIn("nika", variants_nika)
        self.assertIn("ника", variants_nika)

    def test_find_all_character_sprites(self):
        nika_sprites = SpriteResolver.find_all_character_sprites("Ника", sprites_root=self.temp_dir)
        self.assertEqual(len(nika_sprites), 3)
        labels = [s[0] for s in nika_sprites]
        self.assertIn("pose_01", labels)
        self.assertIn("pose_02", labels)
        self.assertIn("pose_03", labels)

        enjie_sprites = SpriteResolver.find_all_character_sprites("Энджи", sprites_root=self.temp_dir)
        self.assertEqual(len(enjie_sprites), 1)
        self.assertEqual(enjie_sprites[0][0], "neutral")

    def test_resolve_sprite(self):
        # 1. Поиск по подпапке с эмоцией
        spr1 = SpriteResolver.resolve_sprite("Ника", "pose_02", sprites_root=self.temp_dir)
        self.assertIsNotNone(spr1)
        self.assertTrue(spr1.endswith("nika_pose_02.png"))

        # 2. Поиск по плоскому файлу с русским синонимом "обычный" -> "neutral"
        spr2 = SpriteResolver.resolve_sprite("Энджи", "обычный", sprites_root=self.temp_dir)
        self.assertIsNotNone(spr2)
        self.assertTrue(spr2.endswith("enjie_neutral.png"))

        # 3. Дефолтный поиск без эмоции
        spr3 = SpriteResolver.resolve_sprite("Ривер", "", sprites_root=self.temp_dir)
        self.assertIsNotNone(spr3)
        self.assertTrue(spr3.endswith("river_happy.png"))

    def test_renpy_export_auto_sprite(self):
        exporter = RenPyExporter()

        # Создаем 3 реплики подряд:
        # Реплика 1: Ника (pose_01) -> должен быть show expression
        # Реплика 2: Ника (pose_01) -> НЕ должно быть дублирующего show expression
        # Реплика 3: Ника (pose_02) -> смена эмоции, должен быть show expression
        n1 = NodeData(id="1", title="Ника", content="Привет!", node_type="story",
                      custom_data={"sprite_path": os.path.join(self.temp_dir, "nika", "nika_pose_01.png")})
        n2 = NodeData(id="2", title="Ника", content="Как дела?", node_type="story",
                      custom_data={"sprite_path": os.path.join(self.temp_dir, "nika", "nika_pose_01.png")})
        n3 = NodeData(id="3", title="Ника", content="Смотри сюда!", node_type="story",
                      custom_data={"sprite_path": os.path.join(self.temp_dir, "nika", "nika_pose_02.png")})

        c1 = ConnectionData(from_node="1", out_idx=0, to_node="2")
        c2 = ConnectionData(from_node="2", out_idx=0, to_node="3")
        project = ProjectData(nodes=[n1, n2, n3], connections=[c1, c2])

        out_export = tempfile.mkdtemp(prefix="de_rpy_sprite_")
        try:
            success, _ = exporter.export(project, out_export)
            self.assertTrue(success)

            with open(os.path.join(out_export, "script.rpy"), "r", encoding="utf-8") as f:
                content = f.read()

            # Должно быть ровно 2 show expression (один для pose_01, один для pose_02), без дубля на второй реплике
            count_show = content.count("show expression")
            self.assertEqual(count_show, 2)
            self.assertIn("nika_pose_01.png", content)
            self.assertIn("nika_pose_02.png", content)
        finally:
            if os.path.exists(out_export):
                shutil.rmtree(out_export)


if __name__ == "__main__":
    unittest.main()
