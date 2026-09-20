import tkinter as tk
from tkinter import colorchooser
from plugin_system import Plugin

# Пресеты цветов для меток (название, цвет фона, цвет шапки)
LABEL_COLOR_PRESETS = [
    ("🟠 Оранжевый (Дефолт)", "#d35400", "#a04000"),
    ("🟢 Зелёный (Старт / Успех)", "#27ae60", "#1e8449"),
    ("🔵 Синий (Глава / Сюжет)", "#2980b9", "#1f618d"),
    ("🟣 Фиолетовый (Квест / Тайна)", "#8e44ad", "#71368a"),
    ("🔴 Красный (Опасность / Финал)", "#c0392b", "#922b21"),
    ("💠 Бирюзовый (Локация)", "#16a085", "#117a65"),
    ("🟡 Золотой (Особый момент)", "#d4ac0d", "#b7950b"),
    ("⚫ Тёмный (Служебный)", "#34495e", "#2c3e50"),
]

def darken_color(hex_color, factor=0.75):
    """Генерирует более тёмный оттенок для заголовка."""
    try:
        hex_clean = hex_color.lstrip('#')
        if len(hex_clean) == 6:
            r = int(hex_clean[0:2], 16)
            g = int(hex_clean[2:4], 16)
            b = int(hex_clean[4:6], 16)
            r = max(0, min(255, int(r * factor)))
            g = max(0, min(255, int(g * factor)))
            b = max(0, min(255, int(b * factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        pass
    return hex_color

class FlowNodesPlugin(Plugin):
    name = "Flow & Variables"
    version = "1.1"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            toolbar = data
            if not hasattr(self.editor, 'plugin_menu'):
                self.editor.plugin_menu_btn = tk.Menubutton(toolbar, text="🧩 Компоненты ▾", bg='#444', fg='white', 
                                                           relief='flat', font=('Segoe UI', 9, 'bold'), padx=10, pady=5)
                self.editor.plugin_menu_btn.pack(side=tk.LEFT, padx=5, pady=5)
                self.editor.plugin_menu = tk.Menu(self.editor.plugin_menu_btn, tearoff=0, bg='#444', fg='white')
                self.editor.plugin_menu_btn["menu"] = self.editor.plugin_menu
            
            self.editor.plugin_menu.add_command(label="🔖 Метка (Label)", command=lambda: self.editor.add_node('label'))
            self.editor.plugin_menu.add_command(label="💲 Переменные (Variable)", command=lambda: self.editor.add_node('variable'))
        
        elif event_type == 'node_added':
            node = data
            if getattr(node, 'is_new', True) and node.node_type == 'label':
                node.custom_data['bg_color'] = '#d35400'       # Оранжевый фон
                node.custom_data['header_color'] = '#a04000'   # Темно-оранжевый заголовок
                node.custom_data['text_color'] = '#ffffff'
                node.title = "Имя метки (start)"
                node.content = "Оставьте пустым или добавьте комментарий."
                self.editor.redraw()
            elif getattr(node, 'is_new', True) and node.node_type == 'variable':
                node.custom_data['bg_color'] = '#2980b9'       # Синий фон
                node.custom_data['header_color'] = '#1f618d'   # Темно-синий заголовок
                node.custom_data['text_color'] = '#f4d03f'     # Желтоватый текст (код)
                node.title = "# Установка переменных"          # # скрывает заголовок при отрисовке, если нужно
                node.content = "money = 100\nhas_key = True"
                self.editor.redraw()

        elif event_type == 'draw_node':
            node = data['node']
            canvas = data['canvas']
            # Добавим иконки к заголовку
            if getattr(node, 'is_new', True) and node.node_type == 'label':
                canvas.create_text(node.x + node.width - 20, node.y + 12, text="🔖", fill="white", tags=("node", node.id))
            elif getattr(node, 'is_new', True) and node.node_type == 'variable':
                canvas.create_text(node.x + node.width - 20, node.y + 12, text="💲", fill="white", tags=("node", node.id))

        elif event_type == 'context_menu':
            target = data.get('target')
            menu = data.get('menu')
            if target and getattr(target, 'node_type', None) == 'label':
                color_menu = tk.Menu(menu, tearoff=0, bg='#252526', fg='white', activebackground='#094771')
                for name, bg_col, head_col in LABEL_COLOR_PRESETS:
                    color_menu.add_command(
                        label=name,
                        command=lambda b=bg_col, h=head_col: self.set_label_color(target, b, h)
                    )
                color_menu.add_separator()
                color_menu.add_command(
                    label="🎨 Выбрать свой цвет...",
                    command=lambda: self.pick_custom_color(target)
                )
                menu.add_cascade(label="🎨 Цвет метки", menu=color_menu)

        elif event_type == 'node_edit_dialog':
            node = data.get('node')
            frame = data.get('frame')
            dialog = data.get('dialog')
            if node and node.node_type == 'label':
                color_box = tk.LabelFrame(frame, text="🎨 Цвет метки", bg=frame['bg'], fg='white', padx=8, pady=8)
                color_box.pack(fill=tk.X, pady=5)

                # Превью текущего цвета
                curr_bg = node.custom_data.get('bg_color', '#d35400')
                lbl_preview = tk.Label(color_box, text="  Текущий цвет  ", bg=curr_bg, fg='white', 
                                       font=("Segoe UI", 9, "bold"), relief='solid', bd=1)
                lbl_preview.pack(side=tk.LEFT, padx=(0, 10))

                # Палитра быстрых пресетов (кнопочки)
                preset_frame = tk.Frame(color_box, bg=frame['bg'])
                preset_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

                for _, bg_col, head_col in LABEL_COLOR_PRESETS:
                    btn_color = tk.Button(
                        preset_frame,
                        bg=bg_col,
                        activebackground=head_col,
                        width=2,
                        height=1,
                        relief='flat',
                        cursor='hand2',
                        command=lambda b=bg_col, h=head_col: self.apply_dialog_color(node, b, h, lbl_preview)
                    )
                    btn_color.pack(side=tk.LEFT, padx=2)

                # Кнопка выбора своего цвета
                btn_custom = tk.Button(
                    color_box,
                    text="Свой цвет...",
                    command=lambda: self.pick_custom_color(node, lbl_preview, dialog),
                    bg='#333333',
                    fg='white',
                    relief='flat',
                    padx=6,
                    pady=2,
                    cursor='hand2'
                )
                btn_custom.pack(side=tk.RIGHT, padx=5)

    def set_label_color(self, node, bg_color, header_color):
        if self.editor:
            self.editor.save_state()
            node.custom_data['bg_color'] = bg_color
            node.custom_data['header_color'] = header_color
            self.editor.redraw()
            self.editor.set_dirty(True)

    def apply_dialog_color(self, node, bg_color, header_color, preview_widget=None):
        node.custom_data['bg_color'] = bg_color
        node.custom_data['header_color'] = header_color
        if preview_widget:
            preview_widget.config(bg=bg_color)
        if self.editor:
            self.editor.redraw()

    def pick_custom_color(self, node, preview_widget=None, parent=None):
        current = node.custom_data.get('bg_color', '#d35400')
        color = colorchooser.askcolor(color=current, title="Выберите цвет метки", parent=parent or self.editor)
        if color and color[1]:
            bg_col = color[1]
            head_col = darken_color(bg_col, 0.75)
            self.set_label_color(node, bg_col, head_col)
            if preview_widget:
                preview_widget.config(bg=bg_col)
