import tkinter as tk
from tkinter import messagebox, filedialog
import json
import os
from plugin_system import Plugin

class BattlePlugin(Plugin):
    name = "Deltarune Battle Plugin"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            if hasattr(self.editor, 'plugin_menu'):
                self.editor.plugin_menu.add_separator()
                self.editor.plugin_menu.add_command(
                    label="⚔️ Битва (Deltarune)", 
                    command=self.create_battle_node
                )

        elif event_type == 'node_added':
            node = data
            if getattr(node, 'is_new', True) and node.node_type == 'battle':
                node.width = 240
                node.height = 120
                node.custom_data['bg_color'] = '#4a154b'      # Глубокий фиолетово-бордовый
                node.custom_data['header_color'] = '#2c0c2d'  # Тёмный заголовок
                node.custom_data['text_color'] = '#ffeb3b'    # Золотистый акцент
                node.title = "⚔️ БИТВА"
                
                default_battle_data = {
                    "enemy_id": "shadow_stalker",
                    "enemy_name": "Тень из подворотни",
                    "music": "music/rain_ambient.wav",
                    "hp": 100,
                    "intro": "Из темноты сгущается силуэт..."
                }
                node.content = json.dumps(default_battle_data, ensure_ascii=False, indent=2)
                self.editor.redraw()

        elif event_type == 'draw_node_content':
            node = data['node']
            if node.node_type == 'battle':
                canvas = data['canvas']
                x, y, w = node.x, node.y, node.width
                
                try:
                    bdata = json.loads(node.content)
                except Exception:
                    bdata = {"enemy_name": "Неизвестный враг", "hp": 100}

                enemy_name = bdata.get("enemy_name", "Враг")
                hp = bdata.get("hp", 100)

                # Информация о враге
                canvas.create_text(
                    x + 10, y + 38,
                    text=f"👹 {enemy_name} [HP: {hp}]",
                    fill="#ffffff",
                    anchor="nw",
                    font=("Segoe UI", 9, "bold"),
                    tags=("node", node.id)
                )

                # 3 выхода: Победа, Пощада, Поражение
                out_labels = [
                    ("⚔️ Победа (Fight)", "#e74c3c", 0),
                    ("✨ Пощада (Spare)", "#2ecc71", 1),
                    ("💀 Поражение", "#95a5a6", 2)
                ]

                node.outputs = []
                for label, col, idx in out_labels:
                    opt_y = y + 62 + (idx * 20)
                    canvas.create_text(
                        x + w - 16, opt_y,
                        text=label,
                        fill=col,
                        anchor="e",
                        font=("Segoe UI", 8, "bold"),
                        tags=("node", node.id)
                    )
                    node.draw_port(canvas, x + w, opt_y, idx)

                data['handled'] = True

        elif event_type == 'draw_node_ports':
            node = data['node']
            if node.node_type == 'battle':
                canvas = data['canvas']
                in_y = node.y + 40
                node.draw_input_port(canvas, node.x, in_y)
                data['handled'] = True

        elif event_type == 'node_edit_dialog':
            node = data['node']
            if node.node_type == 'battle':
                dialog = data['dialog']
                self.setup_battle_dialog(node, dialog)

        elif event_type == 'renpy_export_node':
            node = data['node']
            if node.node_type == 'battle':
                f = data['file']
                conns = data['connections']
                
                try:
                    bdata = json.loads(node.content)
                    e_id = bdata.get("enemy_id", "enemy")
                except:
                    e_id = "enemy"

                f.write(f'    # --- БИТВА DELTARUNE: {e_id} ---\n')
                f.write(f'    # В Godot этот узел переключает сцену на боевую арену\n')
                
                # Ищем соединение для победы (порт 0) по умолчанию
                win_conn = [c for c in conns if c['from'] == node.id and c.get('out_idx', 0) == 0]
                if win_conn:
                    f.write(f'    jump node_{win_conn[0]["to"]}\n')
                else:
                    f.write('    return\n')
                data['handled'] = True

    def create_battle_node(self):
        self.editor.add_node('battle')

    def setup_battle_dialog(self, node, dialog):
        # Панель настройки параметров битвы в окне редактирования
        try:
            bdata = json.loads(node.content)
        except:
            bdata = {}

        bf_frame = tk.LabelFrame(dialog, text="Параметры битвы (Deltarune / Godot)", bg='#1e1e1e', fg='#ffeb3b', padx=10, pady=8)
        bf_frame.pack(fill=tk.X, padx=10, pady=5)

        # ID врага
        tk.Label(bf_frame, text="ID Врага (код):", bg='#1e1e1e', fg='white', font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=2)
        e_id = tk.Entry(bf_frame, bg='#333', fg='white', font=("Segoe UI", 9))
        e_id.insert(0, bdata.get("enemy_id", "stalker"))
        e_id.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        # Имя врага
        tk.Label(bf_frame, text="Имя врага (в UI):", bg='#1e1e1e', fg='white', font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=2)
        e_name = tk.Entry(bf_frame, bg='#333', fg='white', font=("Segoe UI", 9))
        e_name.insert(0, bdata.get("enemy_name", "Тень из подворотни"))
        e_name.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        # Музыка
        tk.Label(bf_frame, text="Музыка боя:", bg='#1e1e1e', fg='white', font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=2)
        e_music = tk.Entry(bf_frame, bg='#333', fg='white', font=("Segoe UI", 9))
        e_music.insert(0, bdata.get("music", "music/rain_ambient.wav"))
        e_music.grid(row=2, column=1, sticky="ew", padx=5, pady=2)

        # HP
        tk.Label(bf_frame, text="Здоровье (HP):", bg='#1e1e1e', fg='white', font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", pady=2)
        e_hp = tk.Entry(bf_frame, bg='#333', fg='white', font=("Segoe UI", 9))
        e_hp.insert(0, str(bdata.get("hp", 100)))
        e_hp.grid(row=3, column=1, sticky="ew", padx=5, pady=2)

        bf_frame.columnconfigure(1, weight=1)

        def sync_battle_content(*args):
            try:
                hp_val = int(e_hp.get().strip())
            except:
                hp_val = 100
            
            cur = {
                "enemy_id": e_id.get().strip(),
                "enemy_name": e_name.get().strip(),
                "music": e_music.get().strip(),
                "hp": hp_val
            }
            node.content = json.dumps(cur, ensure_ascii=False, indent=2)

        e_id.bind("<KeyRelease>", sync_battle_content)
        e_name.bind("<KeyRelease>", sync_battle_content)
        e_music.bind("<KeyRelease>", sync_battle_content)
        e_hp.bind("<KeyRelease>", sync_battle_content)
