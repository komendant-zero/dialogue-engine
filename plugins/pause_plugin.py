import tkinter as tk
from tkinter import ttk
import sys
from plugin_system import Plugin

class PausePlugin(Plugin):
    name = "Pause & Timing"
    version = "1.1"

    def __init__(self, editor):
        super().__init__(editor)
        self.edit_state = {}
        main_module = sys.modules.get('__main__')
        if not hasattr(main_module, 'ScenarioEditor'):
            main_module = sys.modules.get('main', main_module)
        self.EditorClass = getattr(main_module, 'ScenarioEditor', None)
        if self.EditorClass:
            self.original_edit_node = getattr(self.EditorClass, 'edit_node', None)

    def on_enable(self):
        plugin_self = self

        def new_edit_node(editor_self, node):
            if node.node_type == 'pause':
                PauseEditorDialog(editor_self, node, plugin_self.editor.redraw)
            else:
                plugin_self.original_edit_node(editor_self, node)

        if self.EditorClass:
            self.EditorClass.edit_node = new_edit_node

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
                node.width = 170
                node.height = 80
                node.custom_data['bg_color'] = '#4a235a'       # Глубокий пурпурный
                node.custom_data['header_color'] = '#2e113a'   # Тёмная шапка
                node.custom_data['text_color'] = '#d2b4de'     # Светло-лиловый текст
                node.custom_data['pause_mode'] = 'click'       # 'click' или 'time'
                node.custom_data['pause_duration'] = 0.0
                node.title = "Пауза"
                node.content = "Ожидание клика"
                self.editor.redraw()

        # --- 3. Отрисовка иконки в заголовке ---
        elif event_type == 'draw_node':
            node = data['node']
            canvas = data['canvas']
            if node.node_type == 'pause':
                canvas.create_text(node.x + node.width - 20, node.y + 12, text="⏸️", fill="white", tags=("node", node.id))

        # --- 4. Настройки в блоках сюжета (только выбор из списка) ---
        elif event_type == 'node_edit_dialog':
            node = data['node']
            frame = data.get('frame')
            dialog = data.get('dialog')

            if node.node_type == 'story':
                self.setup_story_pause_ui(node, frame or dialog)

        # --- 5. Сохранение настроек в блоках сюжета ---
        elif event_type == 'node_edit_save':
            node = data['node']
            if node.id in self.edit_state:
                state = self.edit_state.pop(node.id)
                try:
                    if node.node_type == 'story':
                        val = state['story_combo_var'].get()
                        if val == "Без паузы":
                            node.custom_data.pop('pause_before', None)
                            node.custom_data.pop('pause_before_mode', None)
                            node.custom_data.pop('pause_before_duration', None)
                        elif "клика" in val.lower():
                            node.custom_data['pause_before'] = True
                            node.custom_data['pause_before_mode'] = 'click'
                            node.custom_data['pause_before_duration'] = 0.0
                        else:
                            sec_str = val.replace("сек", "").strip()
                            try:
                                sec = float(sec_str)
                            except ValueError:
                                sec = 1.0
                            node.custom_data['pause_before'] = True
                            node.custom_data['pause_before_mode'] = 'time'
                            node.custom_data['pause_before_duration'] = sec
                except Exception as e:
                    print(f"[PausePlugin] Save error for node {node.id}: {e}")

        # --- 6. Экспорт в Ren'Py ---
        elif event_type == 'renpy_export_node':
            node = data['node']
            if node.node_type == 'pause':
                f = data['file']
                connections = data['connections']
                mode = node.custom_data.get('pause_mode', 'click')
                dur = node.custom_data.get('pause_duration', 0.0)
                
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

    def setup_story_pause_ui(self, node, parent):
        sp_frame = tk.LabelFrame(parent, text="⏱️ Пауза перед показом реплики", bg='#2b2b2b', fg='#d2b4de', padx=8, pady=6)
        sp_frame.pack(fill=tk.X, padx=5, pady=5)

        options = [
            "Без паузы",
            "Ожидание клика игрока",
            "0.5 сек",
            "1.0 сек",
            "1.5 сек",
            "2.0 сек",
            "3.0 сек",
            "5.0 сек"
        ]

        cur_enabled = bool(node.custom_data.get('pause_before', False))
        cur_mode = node.custom_data.get('pause_before_mode', 'click')
        cur_dur = node.custom_data.get('pause_before_duration', 1.0)

        if not cur_enabled:
            current_val = "Без паузы"
        elif cur_mode == 'click':
            current_val = "Ожидание клика игрока"
        else:
            current_val = f"{cur_dur} сек"
            if current_val not in options:
                options.append(current_val)

        combo_var = tk.StringVar(value=current_val)
        combo = ttk.Combobox(sp_frame, textvariable=combo_var, values=options, state="readonly", font=("Segoe UI", 9))
        combo.pack(fill=tk.X, padx=10, pady=5)

        self.edit_state[node.id] = {
            'story_combo_var': combo_var
        }

class PauseEditorDialog:
    """
    Специализированное окно настроек блока паузы без текстового ввода контента — только выбор из списка.
    """
    def __init__(self, parent, node, callback):
        self.node = node
        self.callback = callback

        self.win = tk.Toplevel(parent)
        self.win.title("Настройки Паузы")
        self.win.geometry("340x260")
        self.win.configure(bg='#222222')
        self.win.transient(parent)
        self.win.grab_set()

        lbl_style = {'bg': '#222222', 'fg': 'white', 'font': ('Segoe UI', 9)}

        tk.Label(self.win, text="Выберите тип паузы / задержки:", **lbl_style).pack(pady=(20, 8))

        cur_mode = self.node.custom_data.get('pause_mode', 'click')
        cur_dur = self.node.custom_data.get('pause_duration', 0.0)

        options = [
            "Ожидание клика игрока",
            "0.5 сек",
            "1.0 сек",
            "1.5 сек",
            "2.0 сек",
            "3.0 сек",
            "5.0 сек"
        ]

        if cur_mode == 'click' or float(cur_dur) == 0.0:
            selected_opt = "Ожидание клика игрока"
        else:
            selected_opt = f"{cur_dur} сек"
            if selected_opt not in options:
                options.append(selected_opt)

        self.combo_var = tk.StringVar(value=selected_opt)
        self.combo = ttk.Combobox(self.win, textvariable=self.combo_var, values=options, state="readonly", font=("Segoe UI", 10))
        self.combo.pack(fill=tk.X, padx=30, pady=5)

        lbl_hint = tk.Label(
            self.win,
            text="• «Ожидание клика» — ждёт нажатия игрока\n• «X.X сек» — автоматический переход по таймеру",
            bg='#222222', fg='#888888', font=("Segoe UI", 8), justify="left"
        )
        lbl_hint.pack(pady=12)

        tk.Button(
            self.win, text="💾 Сохранить", command=self.save,
            bg='#6c3483', activebackground='#8e44ad', fg='white',
            font=("Segoe UI", 9, "bold"), relief='flat', padx=20, pady=6, cursor='hand2'
        ).pack(side=tk.BOTTOM, pady=20)

    def save(self):
        val = self.combo_var.get()
        if "клика" in val.lower():
            self.node.custom_data['pause_mode'] = 'click'
            self.node.custom_data['pause_duration'] = 0.0
            self.node.content = "Ожидание клика"
        else:
            sec_str = val.replace("сек", "").strip()
            try:
                sec = float(sec_str)
            except ValueError:
                sec = 1.0
            self.node.custom_data['pause_mode'] = 'time'
            self.node.custom_data['pause_duration'] = sec
            self.node.content = f"Задержка: {sec} сек"

        self.node.calculate_size()
        self.callback()
        self.win.destroy()
