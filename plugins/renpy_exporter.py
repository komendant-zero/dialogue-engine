import tkinter as tk
from tkinter import filedialog, messagebox
from plugin_system import Plugin
import os
import json

class RenpyExporterPlugin(Plugin):
    name = "Renpy Exporter"
    version = "2.1"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            self.add_toolbar_button(data)

    def add_toolbar_button(self, toolbar):
        parent = getattr(self.editor, 'toolbar_right', toolbar)
        tk.Button(
            parent,
            text="⚙ Экспорт Ren'Py",
            command=self.export_project,
            bg='#8a2318',
            activebackground='#a93226',
            fg='white',
            activeforeground='white',
            relief='flat',
            font=('Segoe UI', 9, 'bold'),
            padx=8,
            pady=3,
            cursor='hand2'
        ).pack(side=tk.RIGHT, padx=3)

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
            nodes_map = {n.id: n for n in nodes}
            with open(rpy_path, 'w', encoding='utf-8') as f:
                f.write("# --- Сгенерировано визуальным редактором (v2.0) ---\n\n")
                
                # ПЫТАЕМСЯ ДЕЛЕГИРОВАТЬ ЭКСПОРТ INIT БЛОКОВ (Анимации, ATL, настройки)
                init_data = {'file': f, 'nodes': nodes, 'connections': connections, 'export_dir': export_dir}
                self.editor.plugin_manager.notify('renpy_export_init', init_data)
                
                # Поиск стартового узла
                to_ids = set(c['to'] for c in connections)
                start_nodes = [n for n in nodes if n.id not in to_ids]
                
                if not start_nodes:
                    start_nodes = [nodes[0]]
                
                start_node = next((n for n in start_nodes if (n.node_type == 'label' or n.node_type == 'story') and n.title.lower() == 'start'), start_nodes[0])
                
                f.write("label start:\n")
                f.write(f"    jump node_{start_node.id}\n\n")
                
                for node in nodes:
                    check_data = {'node': node, 'skip': False}
                    self.editor.plugin_manager.notify('renpy_export_check', check_data)
                    if check_data['skip']:
                        continue
                        
                    f.write(f"# --- {node.title} ({node.node_type}) ---\n")
                    f.write(f"label node_{node.id}:\n")
                    
                    # ПЫТАЕМСЯ ДЕЛЕГИРОВАТЬ ЭКСПОРТ ПЛАГИНАМ
                    export_data = {'node': node, 'file': f, 'connections': connections, 'export_dir': export_dir, 'handled': False}
                    self.editor.plugin_manager.notify('renpy_export_node', export_data)
                    
                    if not export_data['handled']:
                        # Стандартная логика (фоллбэк)
                        self.write_node_content_default(f, node, connections, export_dir=export_dir, nodes_map=nodes_map)
                    
                    f.write("\n")
                
            return True, f"Скрипт успешно экспортирован:\n{rpy_path}"
        except Exception as e:
            return False, f"Ошибка экспорта:\n{e}"

    def clean_rel_path(self, path, export_dir=""):
        if not path:
            return ""
        path = path.replace('\\', '/')
        
        # 1. Если путь содержит /game/ (типично для проектов Ren'Py), извлекаем относительный путь
        path_lower = path.lower()
        if "/game/" in path_lower:
            idx = path_lower.find("/game/")
            path = path[idx + 6:]
        elif path_lower.startswith("game/"):
            path = path[5:]
        elif export_dir and os.path.isabs(path):
            try:
                rel = os.path.relpath(path, export_dir).replace('\\', '/')
                if not rel.startswith('..'):
                    path = rel
            except ValueError:
                pass
        return path.lstrip('/')

    def should_pause_after_media(self, node, connections, nodes_map=None):
        if not nodes_map:
            return False
        out_conns = [c for c in connections if c['from'] == node.id]
        if not out_conns:
            return True  # Тупиковый узел в конце сценария — нужна пауза перед return

        curr_id = out_conns[0]['to']
        visited = set()
        while curr_id and curr_id not in visited:
            visited.add(curr_id)
            target = nodes_map.get(curr_id)
            if not target:
                break
            # Если следующий узел — диалог (story) или выбор (choice), пауза не нужна (диалог сам ждёт игрока)
            if target.node_type in ('story', 'choice'):
                return False
            # Если на пути встречается другое медиа или анимация — обязательно нужна пауза,
            # иначе текущее медиа моментально перекроется следующим!
            if target.node_type in ('media', 'animation'):
                return True
            next_outs = [c for c in connections if c['from'] == curr_id]
            if not next_outs:
                break
            curr_id = next_outs[0]['to']

        return False

    def write_node_content_default(self, f, node, connections, export_dir="", nodes_map=None):
        # 1. Текстовый узел (Story)
        if node.node_type == 'story':
            # Пауза перед показом текста реплики (если включена в плагине паузы)
            if node.custom_data.get('pause_before'):
                p_mode = node.custom_data.get('pause_before_mode', 'click')
                p_dur = node.custom_data.get('pause_before_duration', 1.0)
                try:
                    if p_mode == 'time' and float(p_dur) > 0:
                        f.write(f'    pause {p_dur}\n')
                    else:
                        f.write('    pause\n')
                except (ValueError, TypeError):
                    f.write('    pause\n')

            char_name = node.title.replace('"', '\\"')
            text = node.content.replace('"', '\\"').replace('\n', '\\n')
            
            # Окраска текста
            if 'highlights' in node.custom_data:
                for word, color in node.custom_data['highlights'].items():
                    if word: 
                        text = text.replace(word, f"{{color={color}}}{word}{{/color}}")

            # Окраска имени персонажа
            header_color = node.custom_data.get('header_text_color', '')
            if header_color and header_color.lower() not in ('#ffffff', 'white'):
                char_name = f"{{color={header_color}}}{char_name}{{/color}}"

            if getattr(node, 'mode', 'standard') == 'continue':
                if not text.startswith(' ') and not text.startswith('\\n'):
                    text = ' ' + text
                f.write(f'    extend "{text}"\n')
            elif char_name.startswith('#') or not char_name or char_name == f"{{color={header_color}}}#{{/color}}":
                f.write(f'    "{text}"\n')
            else:
                f.write(f'    "{char_name}" "{text}"\n')
            self.write_jump(f, node.id, connections)

        # 2. Узел Музыки/Звука
        elif node.node_type == 'music':
            mode = node.custom_data.get('music_mode', 'bg')
            path = self.clean_rel_path(node.custom_data.get('music_file', ''), export_dir)
            if path:
                if mode == 'bg':
                    f.write(f'    play music "{path}"\n')
                elif mode == 'sfx':
                    f.write(f'    play sound "{path}"\n')
                else:
                    f.write(f'    voice "{path}"\n')
            self.write_jump(f, node.id, connections)

        # 3. Узел Медиа (Фон / Спрайт)
        elif node.node_type == 'media':
            try:
                data = json.loads(node.content)
                mode = data.get("mode", "sprite")
                path = self.clean_rel_path(data.get("image_path", ""), export_dir)
                
                anim = data.get("animation", "none")
                dur = data.get("animation_duration", 0.5)
                with_clause = ""
                
                if anim.lower() != "none":
                    if anim[0].isupper():
                        with_clause = f" with {anim}({dur})"
                    else:
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

                # Проверяем, нужна ли пауза (явная или автоматическая перед следующим медиа)
                if data.get("pause", False) or self.should_pause_after_media(node, connections, nodes_map):
                    f.write('    pause\n')
            except: pass
            self.write_jump(f, node.id, connections)

        # 4. Узел Выбора (Choice)
        elif node.node_type == 'choice':
            options = node.content.split('\n')
            f.write("    menu:\n")
            out_conns = [c for c in connections if c['from'] == node.id]
            for i, opt in enumerate(options):
                if not opt.strip(): continue
                clean_opt = opt.replace('"', '\\"')
                
                # У выборов красим не текст, а добавляем аргумент обводки при наведении
                hover_color = None
                if 'highlights' in node.custom_data:
                    for word, color in node.custom_data['highlights'].items():
                        if word and word in opt: 
                            hover_color = color
                            break # берем первый найденный цвет для всей опции
                
                if hover_color:
                    f.write(f'        "{clean_opt}" (hover_outlines=[(2, "{hover_color}", 0, 0)]):\n')
                else:
                    f.write(f'        "{clean_opt}":\n')
                    
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
