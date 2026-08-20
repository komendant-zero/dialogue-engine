import tkinter as tk
from tkinter import filedialog, messagebox
from plugin_system import Plugin
import os
import json

class RenpyExporterPlugin(Plugin):
    name = "Renpy Exporter"
    version = "2.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            self.add_toolbar_button(data)

    def add_toolbar_button(self, toolbar):
        tk.Button(
            toolbar,
            text="▶ Экспорт в Ren'Py",
            command=self.export_project,
            bg='#c0392b',
            fg='white',
            relief='flat',
            font=('Segoe UI', 9, 'bold'),
            padx=10,
            pady=5
        ).pack(side=tk.RIGHT, padx=5, pady=5)

    def export_project(self):
        nodes = self.editor.nodes
        connections = self.editor.connections

        if not nodes:
            messagebox.showwarning("Пусто", "Проект пуст! Добавьте блоки для экспорта.")
            return

        export_dir = filedialog.askdirectory(title="Выберите папку game вашего проекта Ren'Py")
        if not export_dir:
            return

        success, msg = self.do_export(export_dir, nodes, connections)
        if success:
            messagebox.showinfo("Успех", msg)
        else:
            messagebox.showerror("Ошибка", msg)

    def do_export(self, export_dir, nodes, connections):
        try:
            rpy_path = os.path.join(export_dir, "script.rpy")
            with open(rpy_path, 'w', encoding='utf-8') as f:
                f.write("# --- Сгенерировано визуальным редактором (v2.0) ---\n\n")
                
                # Поиск стартового узла
                to_ids = set(c['to'] for c in connections)
                start_nodes = [n for n in nodes if n.id not in to_ids]
                
                if not start_nodes:
                    start_nodes = [nodes[0]]
                
                start_node = next((n for n in start_nodes if (n.node_type == 'label' or n.node_type == 'story') and n.title.lower() == 'start'), start_nodes[0])
                
                f.write("label start:\n")
                f.write(f"    jump node_{start_node.id}\n\n")
                
                for node in nodes:
                    f.write(f"# --- {node.title} ({node.node_type}) ---\n")
                    f.write(f"label node_{node.id}:\n")
                    
                    # ПЫТАЕМСЯ ДЕЛЕГИРОВАТЬ ЭКСПОРТ ПЛАГИНАМ
                    export_data = {'node': node, 'file': f, 'connections': connections, 'handled': False}
                    self.editor.plugin_manager.notify('renpy_export_node', export_data)
                    
                    if not export_data['handled']:
                        # Стандартная логика (фоллбэк)
                        self.write_node_content_default(f, node, connections)
                    
                    f.write("\n")
                
            return True, f"Скрипт успешно экспортирован:\n{rpy_path}"
        except Exception as e:
            return False, f"Ошибка экспорта:\n{e}"

    def write_node_content_default(self, f, node, connections):
        # 1. Текстовый узел (Story)
        if node.node_type == 'story':
            char_name = node.title
            text = node.content.replace('"', '\\"').replace('\n', '\\n')
            if 'highlights' in node.custom_data:
                for word, color in node.custom_data['highlights'].items():
                    if word: text = text.replace(word, f"{{color={color}}}{word}{{/color}}")

            if getattr(node, 'mode', 'standard') == 'continue':
                f.write(f'    extend "{text}"\n')
            elif char_name.startswith('#') or not char_name:
                f.write(f'    "{text}"\n')
            else:
                f.write(f'    "{char_name}" "{text}"\n')
            self.write_jump(f, node.id, connections)

        # 2. Узел Музыки/Звука
        elif node.node_type == 'music':
            mode = node.custom_data.get('music_mode', 'bg')
            path = node.custom_data.get('music_file', '').replace('\\', '/')
            if path:
                if mode == 'bg': f.write(f'    play music "{path}"\n')
                else: f.write(f'    voice "{path}"\n')
            self.write_jump(f, node.id, connections)

        # 3. Узел Медиа (Фон / Спрайт)
        elif node.node_type == 'media':
            try:
                data = json.loads(node.content)
                mode = data.get("mode", "sprite")
                path = data.get("image_path", "").replace('\\', '/')
                
                anim = data.get("animation", "none")
                dur = data.get("animation_duration", 0.5)
                with_clause = ""
                
                if anim.lower() != "none":
                    if anim[0].isupper():
                        with_clause = f" with {anim}({dur})"
                    else:
                        # Попытка определить, нужно ли использовать класс для кастомной длительности
                        if dur != 0.5:
                            with_clause = f" with {anim.capitalize()}({dur})"
                        else:
                            with_clause = f" with {anim}"

                if path:
                    if mode == "background": 
                        f.write(f'    scene expression "{path}"{with_clause}\n')
                    else:
                        align = data.get("position", "center")
                        f.write(f'    show expression "{path}" at {align}{with_clause}\n')
            except: pass
            self.write_jump(f, node.id, connections)

        # 4. Узел Выбора (Choice)
        elif node.node_type == 'choice':
            options = node.content.split('\n')
            f.write("    menu:\n")
            out_conns = [c for c in connections if c['from'] == node.id]
            for i, opt in enumerate(options):
                if not opt.strip(): continue
                f.write(f'        "{opt}":\n')
                target_conn = next((c for c in out_conns if c['out_idx'] == i), None)
                if target_conn: f.write(f'            jump node_{target_conn["to"]}\n')
                else: f.write('            pass\n')
                    
        # 5. Узел Label (Логическая метка)
        elif node.node_type == 'label':
            f.write(f'    # Метка: {node.title}\n')
            self.write_jump(f, node.id, connections)

        # 6. Узел Переменных (Variable)
        elif node.node_type == 'variable':
            lines = node.content.split('\n')
            for line in lines:
                if line.strip(): f.write(f'    $ {line.strip()}\n')
            self.write_jump(f, node.id, connections)

    def write_jump(self, f, node_id, connections):
        out_conns = [c for c in connections if c['from'] == node_id]
        if out_conns:
            target_id = out_conns[0]['to']
            f.write(f'    jump node_{target_id}\n')
        else:
            f.write('    return\n')
