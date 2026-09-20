import tkinter as tk
from plugin_system import Plugin
import os

class PausePlugin(Plugin):
    name = "Pause & Timing"
    version = "1.0"

    def __init__(self, editor):
        super().__init__(editor)
        self.edit_state = {}

    def on_event(self, event_type, data=None):
        # --- 1. Меню компонентов ---
        if event_type == 'setup_ui':
            toolbar = data
            if hasattr(self.editor, 'plugin_menu'):
                self.editor.plugin_menu.add_command(
                    label="⏸️ Пауза (Задержка)",
                    command=self.create_pause_node
                )
            else:
                if not hasattr(self.editor, 'plugin_menu_btn'):
                    self.editor.plugin_menu_btn = tk.Menubutton(
                        toolbar, text="🧩 Компоненты ▾", bg='#444', fg='white',
                        relief='flat', font=('Segoe UI', 9, 'bold'), padx=10, pady=5
                    )
                    self.editor.plugin_menu_btn.pack(side=tk.LEFT, padx=5, pady=5)
                    self.editor.plugin_menu = tk.Menu(self.editor.plugin_menu_btn, tearoff=0, bg='#444', fg='white')
                    self.editor.plugin_menu_btn["menu"] = self.editor.plugin_menu

                self.editor.plugin_menu.add_command(
                    label="⏸️ Пауза (Задержка)",
                    command=self.create_pause_node
                )

        # --- 2. Инициализация нового узла ---
        elif event_type == 'node_added':
            node = data
            if getattr(node, 'is_new', True) and node.node_type == 'pause':
                node.width = 180
                node.height = 90
                node.custom_data['bg_color'] = '#4a235a'       # Глубокий пурпурный
                node.custom_data['header_color'] = '#2e113a'   # Тёмная шапка
                node.custom_data['text_color'] = '#d2b4de'     # Светло-лиловый текст
                node.custom_data['pause_mode'] = 'click'       # 'click' или 'time'
                node.custom_data['pause_duration'] = 1.0
                node.title = "Пауза"
                node.content = "Ожидание клика"
                self.editor.redraw()

        # --- 3. Отрисовка иконки в заголовке ---
        elif event_type == 'draw_node':
            node = data['node']
            canvas = data['canvas']
            if node.node_type == 'pause':
                canvas.create_text(node.x + node.width - 20, node.y + 12, text="⏸️", fill="white", tags=("node", node.id))

        # --- 4. Интерфейс редактирования (включая настройки в нодах сюжета) ---
        elif event_type == 'node_edit_dialog':
            node = data['node']
            frame = data.get('frame')
            dialog = data.get('dialog')

            if node.node_type == 'pause':
                self.setup_pause_node_ui(node, frame or dialog)
            elif node.node_type == 'story':
                self.setup_story_pause_ui(node, frame or dialog)

        # --- 5. Сохранение настроек ---
        elif event_type == 'node_edit_save':
            node = data['node']
            if node.id in self.edit_state:
                state = self.edit_state.pop(node.id)
                try:
                    if node.node_type == 'pause':
                        mode = state['mode'].get()
                        node.custom_data['pause_mode'] = mode
                        try:
                            dur = float(state['duration'].get().strip())
                        except ValueError:
                            dur = 1.0
                        node.custom_data['pause_duration'] = dur
                        if mode == 'time':
                            node.content = f"Задержка: {dur} сек"
                        else:
                            node.content = "Ожидание клика"
                        node.calculate_size()

                    elif node.node_type == 'story':
                        enabled = state['enabled'].get()
                        node.custom_data['pause_before'] = enabled
                        if enabled:
                            mode = state['mode'].get()
                            node.custom_data['pause_before_mode'] = mode
                            try:
                                dur = float(state['duration'].get().strip())
                            except ValueError:
                                dur = 1.0
                            node.custom_data['pause_before_duration'] = dur
                        else:
                            node.custom_data.pop('pause_before', None)
                            node.custom_data.pop('pause_before_mode', None)
                            node.custom_data.pop('pause_before_duration', None)
                except Exception as e:
                    print(f"[PausePlugin] Save error for node {node.id}: {e}")

        # --- 6. Экспорт в Ren'Py ---
        elif event_type == 'renpy_export_node':
            node = data['node']
            if node.node_type == 'pause':
                f = data['file']
                connections = data['connections']
                mode = node.custom_data.get('pause_mode', 'click')
                dur = node.custom_data.get('pause_duration', 1.0)
                
                if mode == 'time' and float(dur) > 0:
                    f.write(f'    pause {dur}\n')
                else:
                    f.write('    pause\n')

                out_conns = [c for c in connections if c['from'] == node.id]
                if out_conns:
                    f.write(f'    jump node_{out_conns[0]["to"]}\n')
                else:
                    f.write('    return\n')

                data['handled'] = True

    def create_pause_node(self):
        self.editor.add_node(
            ntype='pause',
            title="Пауза",
            content="Ожидание клика"
        )

    def setup_pause_node_ui(self, node, parent):
        p_frame = tk.LabelFrame(parent, text="⏸️ Настройки паузы", bg='#2b2b2b', fg='#d2b4de', padx=8, pady=8)
        p_frame.pack(fill=tk.X, padx=5, pady=5)

        cur_mode = node.custom_data.get('pause_mode', 'click')
        cur_dur = str(node.custom_data.get('pause_duration', 1.0))

        mode_var = tk.StringVar(value=cur_mode)
        dur_entry = tk.Entry(p_frame, bg='#333', fg='white', insertbackground='white', width=8)
        dur_entry.insert(0, cur_dur)

        self.edit_state[node.id] = {
            'mode': mode_var,
            'duration': dur_entry
        }

        r_style = {'bg': '#2b2b2b', 'fg': 'white', 'selectcolor': '#444', 
                   'activebackground': '#2b2b2b', 'activeforeground': 'white'}

        def update_entry_state():
            if mode_var.get() == 'time':
                dur_entry.config(state='normal')
            else:
                dur_entry.config(state='disabled')

        rb_click = tk.Radiobutton(p_frame, text="Ожидание клика игрока", variable=mode_var, 
                                  value="click", command=update_entry_state, **r_style)
        rb_click.pack(anchor='w', pady=2)

        row_time = tk.Frame(p_frame, bg='#2b2b2b')
        row_time.pack(fill=tk.X, pady=2)

        rb_time = tk.Radiobutton(row_time, text="Задержка по времени (сек):", variable=mode_var, 
                                 value="time", command=update_entry_state, **r_style)
        rb_time.pack(side=tk.LEFT)
        dur_entry.pack(side=tk.LEFT, padx=5)

        update_entry_state()

    def setup_story_pause_ui(self, node, parent):
        sp_frame = tk.LabelFrame(parent, text="⏱️ Пауза перед показом реплики", bg='#2b2b2b', fg='#d2b4de', padx=8, pady=6)
        sp_frame.pack(fill=tk.X, padx=5, pady=5)

        cur_enabled = bool(node.custom_data.get('pause_before', False))
        cur_mode = node.custom_data.get('pause_before_mode', 'click')
        cur_dur = str(node.custom_data.get('pause_before_duration', 1.0))

        enabled_var = tk.BooleanVar(value=cur_enabled)
        mode_var = tk.StringVar(value=cur_mode)
        dur_entry = tk.Entry(sp_frame, bg='#333', fg='white', insertbackground='white', width=8)
        dur_entry.insert(0, cur_dur)

        self.edit_state[node.id] = {
            'enabled': enabled_var,
            'mode': mode_var,
            'duration': dur_entry
        }

        r_style = {'bg': '#2b2b2b', 'fg': 'white', 'selectcolor': '#444', 
                   'activebackground': '#2b2b2b', 'activeforeground': 'white'}

        opts_frame = tk.Frame(sp_frame, bg='#2b2b2b')

        def toggle_enabled():
            if enabled_var.get():
                opts_frame.pack(fill=tk.X, pady=(4, 0))
            else:
                opts_frame.pack_forget()

        def update_entry_state():
            if mode_var.get() == 'time':
                dur_entry.config(state='normal')
            else:
                dur_entry.config(state='disabled')

        cb = tk.Checkbutton(sp_frame, text="Добавить паузу перед этой репликой", variable=enabled_var,
                            command=toggle_enabled, **r_style)
        cb.pack(anchor='w')

        rb_click = tk.Radiobutton(opts_frame, text="Ждать клика игрока", variable=mode_var, 
                                  value="click", command=update_entry_state, **r_style)
        rb_click.pack(anchor='w', pady=2)

        row_time = tk.Frame(opts_frame, bg='#2b2b2b')
        row_time.pack(fill=tk.X, pady=2)

        rb_time = tk.Radiobutton(row_time, text="Таймер задержки (сек):", variable=mode_var, 
                                 value="time", command=update_entry_state, **r_style)
        rb_time.pack(side=tk.LEFT)
        dur_entry.pack(side=tk.LEFT, padx=5)

        update_entry_state()
        toggle_enabled()
