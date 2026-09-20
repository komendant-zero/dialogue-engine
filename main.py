import os
import sys

# --- ПУТИ ДЛЯ СТАБИЛЬНОГО ЗАПУСКА (Double-Click Fix) ---
# Определяем директорию скрипта и делаем её рабочей
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# --- DPI AWARENESS (Windows Fix for Crisp Fonts and Coordinates) ---
if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, colorchooser
import tkinter.font as tkfont
import json
import os
import sys
import math
import getpass

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
def get_pc_user():
    """Пытается получить имя пользователя (Full Name для Windows, иначе логин)."""
    import getpass
    username = getpass.getuser()
    
    if sys.platform == 'win32':
        try:
            import ctypes
            # ExtendedNameFormat.NameDisplay = 3
            # Получает "Отображаемое имя" (обычно Имя Фамилия из учетки Microsoft)
            GetUserNameEx = ctypes.windll.secur32.GetUserNameExW
            size = ctypes.c_ulong(512)
            buffer = ctypes.create_unicode_buffer(size.value)
            if GetUserNameEx(3, buffer, ctypes.byref(size)):
                if buffer.value:
                    return buffer.value
        except Exception:
            pass
    return username

PC_USER = get_pc_user()

# Попытка импорта системы плагинов
try:
    from plugin_system import PluginManager
except ImportError:
    # Заглушка, если плагинов нет
    class PluginManager:
        def __init__(self, editor): pass
        def load_plugins_from_folder(self, path): pass
        def notify(self, event, data=None): pass

# --- КОНФИГУРАЦИЯ ЦВЕТОВ ---
COLORS = {
    'bg': '#1e1e1e',           
    'canvas_bg': '#2b2b2b',    
    'grid_light': '#333333',   
    'grid_bold': '#3a3a3a',    
    'node_story': '#3c3f41',   
    'node_choice': '#2d4a57',
    'node_music': '#8e44ad',   # Фиолетовый для музыки
    'header_story': '#4a90e2', 
    'header_choice': '#e67e22',
    'header_music': '#9b59b6',
    'text': '#dcdcdc',         
    'port': '#888888',         
    'line': '#a9b7c6',         
    'line_active': '#ffcc00',  
    'boundary_line': '#e74c3c', # Цвет границы (красный)
}

# --- ПРЕСЕТЫ ЦВЕТОВ ДЛЯ БЛОКОВ ---
NODE_COLOR_PRESETS = [
    ("🟠 Оранжевый", "#d35400", "#a04000"),
    ("🟢 Зелёный", "#27ae60", "#1e8449"),
    ("🔵 Синий", "#2980b9", "#1f618d"),
    ("🟣 Фиолетовый", "#8e44ad", "#71368a"),
    ("🔴 Красный", "#c0392b", "#922b21"),
    ("💠 Бирюзовый", "#16a085", "#117a65"),
    ("🟡 Золотой", "#d4ac0d", "#b7950b"),
    ("🟤 Коричневый", "#795548", "#5d4037"),
    ("⚫ Тёмно-серый", "#34495e", "#2c3e50"),
]

def darken_color(hex_color, factor=0.75):
    """Генерирует гармоничный тёмный оттенок для заголовка блока."""
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

# --- КЛАСС БЛОКА ---

class Node:
    def __init__(self, editor, x, y, title, content, node_type, custom_data=None, mode="standard"):
        self.editor = editor
        self.id = str(id(self))
        self.x = x
        self.y = y
        self.width = 180
        self.height = 100
        self.title = title
        self.content = content
        self.node_type = node_type 
        self.mode = mode

        self.custom_data = custom_data if custom_data is not None else {}
        
        self.outputs = [] 
        self.font_content = tkfont.Font(family="Segoe UI", size=9)
        self.calculate_size()

    def _get_display_text(self, text):
        """Заменяет плейсхолдеры на реальные данные."""
        if not text:
            return ""
        return text.replace("[ИГРОК]", PC_USER)

    def calculate_size(self):
        base_h = 40
        display_content = self._get_display_text(self.content)
        
        calc_data = {'node': self, 'base_h': base_h, 'display_content': display_content, 'height': None, 'handled': {'done': False}}
        if self.editor:
            self.editor.plugin_manager.notify('calculate_node_size', calc_data)
        
        if calc_data['handled']['done']:
            self.height = calc_data['height']
        else:
            if self.editor and self.editor.canvas:
                text_val = display_content if display_content else " "
                temp_text = self.editor.canvas.create_text(0, 0, text=text_val, width=self.width - 20, font=self.font_content, anchor="nw")
                bbox = self.editor.canvas.bbox(temp_text)
                self.editor.canvas.delete(temp_text)
                text_h = (bbox[3] - bbox[1]) if bbox else 20
                self.height = base_h + text_h + 15
            else:
                self.height = 100


    def draw(self, canvas):
        x, y, w, h = self.x, self.y, self.width, self.height
        
        display_title = self._get_display_text(self.title)
        display_content = self._get_display_text(self.content)
        
        # Получаем цвета из custom_data (если заданы плагином) или берем стандартные
        default_bg = COLORS.get(f'node_{self.node_type}', COLORS['node_story'])
        default_head = COLORS.get(f'header_{self.node_type}', COLORS['header_story'])
        
        bg_col = self.custom_data.get('bg_color', default_bg)
        head_col = self.custom_data.get('header_color', default_head)
        
        # Цвет основного текста (из custom_data или дефолт)
        text_col = self.custom_data.get('text_color', COLORS['text'])
        
        # Цвет заголовка (по умолчанию белый)
        header_text_col = self.custom_data.get('header_text_color', 'white')
        
        # 1. Тело блока
        is_selected = getattr(self.editor, 'selected_nodes', []) and self in self.editor.selected_nodes
        outline_color = '#00ff00' if is_selected else COLORS['grid_bold']
        outline_width = 3 if is_selected else 2
        canvas.create_rectangle(x, y, x+w, y+h, fill=bg_col, outline=outline_color, width=outline_width, tags=("node", self.id))
        
        # 2. Заголовок
        canvas.create_rectangle(x, y, x+w, y+25, fill=head_col, outline="", tags=("node", self.id))
        
        # ЛОГИКА ОТОБРАЖЕНИЯ ИМЕНИ ПЕРСОНАЖА:
        final_title = display_title
        title_font = ("Segoe UI", 9, "bold")
        title_fill = header_text_col

        if display_title.startswith('#') or not display_title.strip():
            if self.node_type == 'story':
                comment = display_title.lstrip('#').strip()
                final_title = f"💭 {comment}" if comment else "💭 Слова автора"
                title_font = ("Segoe UI", 8, "italic")
                title_fill = "#aaaaaa"
            else:
                final_title = ""
        else:
            if self.node_type == 'story':
                final_title = f"👤 {display_title}"
            
        canvas.create_text(x+10, y+12, text=final_title, fill=title_fill, anchor="w", font=title_font, tags=("node", self.id))

        # Индикатор режима (Standard / Continue)
        if self.node_type == 'story' and self.mode == 'continue':
             canvas.create_text(x+w-10, y+12, text="[+]", fill="#fff", anchor="e", font=("Segoe UI", 8, "bold"), tags=("node", self.id))

                # 3. Контент
        draw_data = {'node': self, 'canvas': canvas, 'handled': False}
        self.editor.plugin_manager.notify('draw_node_content', draw_data)
        
        if not draw_data['handled']:
            display_content = self._get_display_text(self.content)
            canvas.create_text(
                x+10, y+35, 
                text=display_content, 
                fill=text_col, 
                anchor="nw", 
                width=w-20,
                font=self.font_content, 
                tags=("node", self.id)
            )
            self.draw_port(canvas, x+w, y + math.floor(h/2), 0)

        # Входной порт
        port_data = {'node': self, 'canvas': canvas, 'handled': False}
        self.editor.plugin_manager.notify('draw_node_ports', port_data)
        if not port_data['handled']:
            self.draw_input_port(canvas, x, y + math.floor(h/2))

        # Hook для плагинов
        self.editor.plugin_manager.notify('draw_node', {'node': self, 'canvas': canvas})

    def draw_rich_text(self, canvas, start_x, start_y, max_width, default_color, highlights, display_content):
        """Ручная отрисовка текста с поддержкой цвета для фрагментов."""
        font = self.font_content
        lines = display_content.split('\n')
        
        cur_y = start_y
        line_height = font.metrics("linespace")
        space_width = font.measure(" ")
        
        for paragraph in lines:
            # 1. Карта цветов для параграфа (по умолчанию базовый цвет)
            text_colors = [default_color] * len(paragraph)
            
            # Накладываем цвета фрагментов
            for phrase, color in highlights.items():
                if not phrase: continue
                # Заменяем плейсхолдер в фразе выделения, если он там есть
                display_phrase = self._get_display_text(phrase)
                start = 0
                while True:
                    idx = paragraph.find(display_phrase, start)
                    if idx == -1: break
                    for i in range(idx, idx + len(display_phrase)):
                        text_colors[i] = color
                    start = idx + 1
            
            # 2. Посимвольная/пословесная отрисовка с переносом
            cur_x = start_x
            word_start_idx = 0
            
            for i, char in enumerate(paragraph):
                if char == ' ':
                    # Обработка слова перед пробелом
                    if i > word_start_idx:
                        word_str = paragraph[word_start_idx:i]
                        word_w = font.measure(word_str)
                        
                        # Проверка переноса строки (по ширине всего слова)
                        if cur_x + word_w > start_x + max_width and cur_x > start_x:
                            cur_x = start_x
                            cur_y += line_height
                        
                        # Рисуем слово по чанкам (группам одинакового цвета)
                        chunk_text = ""
                        chunk_color = text_colors[word_start_idx]
                        
                        for k in range(len(word_str)):
                            c = word_str[k]
                            c_col = text_colors[word_start_idx + k]
                            
                            if c_col == chunk_color:
                                chunk_text += c
                            else:
                                # Отрисовка накопленного куска
                                canvas.create_text(cur_x, cur_y, text=chunk_text, fill=chunk_color, anchor="nw", font=font, tags=("node", self.id))
                                cur_x += font.measure(chunk_text)
                                # Новый кусок
                                chunk_text = c
                                chunk_color = c_col
                        
                        # Отрисовка последнего куска слова
                        if chunk_text:
                            canvas.create_text(cur_x, cur_y, text=chunk_text, fill=chunk_color, anchor="nw", font=font, tags=("node", self.id))
                            cur_x += font.measure(chunk_text)

                    # Рисуем/пропускаем пробел (сдвигаем курсор)
                    cur_x += space_width
                    word_start_idx = i + 1
            
            # 3. Рисуем последнее слово в параграфе (если есть)
            if word_start_idx < len(paragraph):
                word_str = paragraph[word_start_idx:]
                word_w = font.measure(word_str)
                
                if cur_x + word_w > start_x + max_width and cur_x > start_x:
                    cur_x = start_x
                    cur_y += line_height
                
                chunk_text = ""
                chunk_color = text_colors[word_start_idx]
                
                for k in range(len(word_str)):
                    c = word_str[k]
                    c_col = text_colors[word_start_idx + k]
                    
                    if c_col == chunk_color:
                        chunk_text += c
                    else:
                        canvas.create_text(cur_x, cur_y, text=chunk_text, fill=chunk_color, anchor="nw", font=font, tags=("node", self.id))
                        cur_x += font.measure(chunk_text)
                        chunk_text = c
                        chunk_color = c_col
                
                if chunk_text:
                    canvas.create_text(cur_x, cur_y, text=chunk_text, fill=chunk_color, anchor="nw", font=font, tags=("node", self.id))
                    cur_x += font.measure(chunk_text)

            cur_y += line_height

    def draw_port(self, canvas, px, py, index):
        r = 5
        tag = f"port_out_{self.id}_{index}"
        canvas.create_oval(px-r, py-r, px+r, py+r, fill=COLORS['port'], outline="", tags=("port", "output", tag))
        self.outputs.append({'id': index, 'x': px, 'y': py, 'tag': tag})

    def draw_input_port(self, canvas, px, py):
        r = 5
        tag = f"port_in_{self.id}"
        canvas.create_oval(px-r, py-r, px+r, py+r, fill=COLORS['port'], outline="", tags=("port", "input", tag))

    def get_output_pos(self, index):
        if self.node_type in ('choice', 'battle', 'condition'):
            if self.node_type == 'condition':
                return (self.x + self.width, self.y + 35 + (15 if index == 0 else 40))
            return (self.x + self.width, self.y + 35 + (index * 25))
        return (self.x + self.width, self.y + self.height/2)

    def get_input_pos(self):
        if self.node_type == 'condition':
            return (self.x, self.y + 35)
        y_pos = self.y + 25 if self.node_type in ('choice', 'battle') else self.y + self.height/2
        return (self.x, y_pos)
    
    def is_inside(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height

# --- ГЛАВНЫЙ РЕДАКТОР ---

class ScenarioEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.title("Scenario Editor - Новый проект")
        self.geometry("1100x750")
        self.configure(bg=COLORS['bg'])

        self.nodes = []
        self.connections = [] 
        self.drag_data = {"x": 0, "y": 0, "item": None}
        self.conn_drag = {"active": False, "start_node": None, "start_idx": 0, "line_id": None}
        self.pressed_keys = {}

        # --- Свойства выделения ---
        self.selected_nodes = []
        self.selected_connection = None
        self.clipboard = {}
        self.undo_stack = []
        self.redo_stack = []
        self.marquee_id = None
        self.marquee_start = None

        # --- Переменные для физики перемещения ---
        self.velocity_x = 0
        self.velocity_y = 0
        self.friction = 0.9        
        self.keyboard_accel = 0.5 
        self.max_speed = 10.0      
        
        self.scroll_remainder_x = 0.0
        self.scroll_remainder_y = 0.0
        
        self.mouse_last_x = 0
        self.mouse_last_y = 0
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.is_dirty = False # Флаг изменений
        
        # --- Масштабирование (Zoom) ---
        self.zoom_level = 1.0
        self.min_zoom = 0.4
        self.max_zoom = 2.0
        # -----------------------------------------

        self.plugin_manager = PluginManager(self)
        self.setup_ui()
        self.create_grid()
        self.setup_hotkeys()
        
        self.plugin_manager.load_plugins_from_folder("plugins")
        self.plugin_manager.notify('setup_ui', self.toolbar)
        
        self.canvas.xview_moveto(0.0) 
        self.canvas.yview_moveto(0.5)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.physics_loop()

    def on_close(self):
        if self.is_dirty:
            res = messagebox.askyesnocancel("Выход", "В проекте есть несохраненные изменения. Сохранить перед выходом?")
            if res is True: # Да
                self.save_project()
                self.destroy()
            elif res is False: # Нет
                self.destroy()
            # Если Cancel - ничего не делаем
        else:
            self.destroy()

    def set_dirty(self, state=True):
        self.is_dirty = state
        fname = os.path.basename(self.current_file) if getattr(self, 'current_file', None) else "Новый проект"
        title_suffix = " * (Изменено)" if state else ""
        self.title(f"Scenario Editor - {fname}{title_suffix}")

    def setup_ui(self):
        self.toolbar = tk.Frame(self, bg=COLORS['bg'], height=42)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # Левая часть тулбара (Создание, компоненты, проект)
        self.toolbar_left = tk.Frame(self.toolbar, bg=COLORS['bg'])
        self.toolbar_left.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=3)

        # Правая часть тулбара (Инструменты, экспорт, статистика)
        self.toolbar_right = tk.Frame(self.toolbar, bg=COLORS['bg'])
        self.toolbar_right.pack(side=tk.RIGHT, fill=tk.Y, padx=4, pady=3)

        # --- ПАНЕЛЬ НАВИГАЦИИ (Breadcrumbs) ---
        self.nav_bar = tk.Frame(self, bg='#282828', height=26)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X)
        self.lbl_path = tk.Label(self.nav_bar, text="Root", bg='#282828', fg='#4a90e2', font=("Segoe UI", 9, "bold"))
        self.lbl_path.pack(side=tk.LEFT, padx=10)
        
        # --- Стили кнопок ---
        btn_action = {'bg': '#2c3e50', 'fg': 'white', 'activebackground': '#34495e', 'activeforeground': 'white', 
                      'relief': 'flat', 'font': ('Segoe UI', 9, 'bold'), 'padx': 9, 'pady': 3, 'cursor': 'hand2'}
        btn_normal = {'bg': '#333333', 'fg': '#dddddd', 'activebackground': '#444444', 'activeforeground': 'white', 
                      'relief': 'flat', 'font': ('Segoe UI', 9), 'padx': 8, 'pady': 3, 'cursor': 'hand2'}
        menu_cfg = {'bg': '#252526', 'fg': 'white', 'activebackground': '#094771', 'activeforeground': 'white', 
                    'font': ('Segoe UI', 9), 'relief': 'flat', 'tearoff': 0}

        # --- Левая группа: Добавление нод ---
        tk.Button(self.toolbar_left, text="📝 Сюжет", command=lambda: self.add_node('story'), **btn_action).pack(side=tk.LEFT, padx=3)
        tk.Button(self.toolbar_left, text="🔀 Выбор", command=lambda: self.add_node('choice'), **btn_action).pack(side=tk.LEFT, padx=3)

        # Централизованное меню компонентов (плагины добавляют свои пункты сюда)
        self.plugin_menu_btn = tk.Menubutton(self.toolbar_left, text="🧩 Компоненты ▾", **btn_action)
        self.plugin_menu_btn.pack(side=tk.LEFT, padx=3)
        self.plugin_menu = tk.Menu(self.plugin_menu_btn, **menu_cfg)
        self.plugin_menu_btn["menu"] = self.plugin_menu

        # Разделитель
        tk.Label(self.toolbar_left, text="|", bg=COLORS['bg'], fg='#555555').pack(side=tk.LEFT, padx=5)

        # Меню Проект
        self.project_menu_btn = tk.Menubutton(self.toolbar_left, text="📁 Проект ▾", **btn_normal)
        self.project_menu_btn.pack(side=tk.LEFT, padx=3)
        self.project_menu = tk.Menu(self.project_menu_btn, **menu_cfg)
        self.project_menu_btn["menu"] = self.project_menu

        self.project_menu.add_command(label="💾 Сохранить (Ctrl+S)", command=self.save_project)
        self.project_menu.add_command(label="📂 Загрузить (Ctrl+O)", command=self.load_project)
        self.project_menu.add_separator()
        self.project_menu.add_command(label="⚠️ Очистить холст", command=self.clear_all)

        # Поиск
        tk.Button(self.toolbar_left, text="🔍 Поиск", command=self.open_search_replace, **btn_normal).pack(side=tk.LEFT, padx=3)

        # Меню инструментов / Разработка на правой стороне
        self.dev_menu_btn = tk.Menubutton(self.toolbar_right, text="⚙️ Меню ▾", **btn_normal)
        self.dev_menu_btn.pack(side=tk.RIGHT, padx=3)
        self.dev_menu = tk.Menu(self.dev_menu_btn, **menu_cfg)
        self.dev_menu_btn["menu"] = self.dev_menu

        # Виджет масштабирования (Zoom)
        self.zoom_frame = tk.Frame(self.toolbar_right, bg=COLORS['bg'])
        self.zoom_frame.pack(side=tk.RIGHT, padx=4)
        tk.Button(self.zoom_frame, text="−", command=self.zoom_out, **btn_normal, width=2).pack(side=tk.LEFT, padx=1)
        self.lbl_zoom = tk.Label(self.zoom_frame, text="100%", bg=COLORS['bg'], fg='#aaaaaa', font=("Segoe UI", 8), width=5)
        self.lbl_zoom.pack(side=tk.LEFT, padx=1)
        tk.Button(self.zoom_frame, text="+", command=self.zoom_in, **btn_normal, width=2).pack(side=tk.LEFT, padx=1)

        self.canvas = tk.Canvas(self, bg=COLORS['canvas_bg'], highlightthickness=0, xscrollincrement=1, yscrollincrement=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)
        self.canvas.bind("<ButtonRelease-2>", self.stop_pan)

    def create_grid(self):
        limit = 50000
        step = 20
        self.canvas.config(scrollregion=(0, -limit, limit, limit))
        
        for i in range(0, limit, step):
            if i == 0: continue 
            color = COLORS['grid_bold'] if i % 100 == 0 else COLORS['grid_light']
            self.canvas.create_line(i, -limit, i, limit, tag='grid', fill=color)
        
        for i in range(-limit, limit, step):
            color = COLORS['grid_bold'] if i % 100 == 0 else COLORS['grid_light']
            self.canvas.create_line(0, i, limit, i, tag='grid', fill=color)

        self.canvas.create_line(0, -limit, 0, limit, tag='grid', fill=COLORS['boundary_line'], width=2)
            
        self.canvas.tag_lower('grid')

    def setup_hotkeys(self):
        self.bind("<KeyPress>", self.on_key_press)
        self.bind("<KeyRelease>", self.on_key_release)
        self.bind("<Control-z>", self.undo)
        self.bind("<Control-y>", self.redo)
        self.bind("<Control-c>", self.copy)
        self.bind("<Control-v>", self.paste)
        self.bind("<Control-d>", self.duplicate)
        self.bind("<Delete>", self.delete_selected)
        self.bind("<Control-s>", lambda e: self.save_project())
        self.bind("<Control-S>", lambda e: self.save_project())
        self.bind("<Control-o>", lambda e: self.load_project())
        self.bind("<Control-O>", lambda e: self.load_project())
        self.bind("<Control-f>", lambda e: self.open_search_replace())
        self.bind("<Control-F>", lambda e: self.open_search_replace())
        self.bind("<Control-plus>", lambda e: self.zoom_in())
        self.bind("<Control-equal>", lambda e: self.zoom_in())
        self.bind("<Control-minus>", lambda e: self.zoom_out())
        self.bind("<Control-0>", lambda e: self.zoom_reset())

    def on_key_press(self, event): self.pressed_keys[event.keysym] = True
    def on_key_release(self, event): self.pressed_keys[event.keysym] = False

    def physics_loop(self):
        target_vx = 0
        target_vy = 0

        if not self.is_panning: 
            if self.pressed_keys.get('Left'): target_vx = -self.max_speed
            if self.pressed_keys.get('Right'): target_vx = self.max_speed
            if self.pressed_keys.get('Up'): target_vy = -self.max_speed
            if self.pressed_keys.get('Down'): target_vy = self.max_speed

            self.velocity_x += (target_vx - self.velocity_x) * 0.05
            self.velocity_y += (target_vy - self.velocity_y) * 0.05
        
        if target_vx == 0 and not self.is_panning:
            self.velocity_x *= self.friction
        if target_vy == 0 and not self.is_panning:
            self.velocity_y *= self.friction

        if abs(self.velocity_x) < 0.01: self.velocity_x = 0
        if abs(self.velocity_y) < 0.01: self.velocity_y = 0

        if self.velocity_x != 0 or self.velocity_y != 0:
            total_move_x = self.velocity_x + self.scroll_remainder_x
            total_move_y = self.velocity_y + self.scroll_remainder_y
            
            int_move_x = int(total_move_x)
            int_move_y = int(total_move_y)
            
            self.scroll_remainder_x = total_move_x - int_move_x
            self.scroll_remainder_y = total_move_y - int_move_y
            
            if int_move_x != 0:
                self.canvas.xview_scroll(int_move_x, "units")
            if int_move_y != 0:
                self.canvas.yview_scroll(int_move_y, "units")

        self.after(16, self.physics_loop)

    def save_state(self, clear_redo=True):
        state = {
            "nodes": [ { "id": n.id, "x": n.x, "y": n.y, "title": n.title, "content": n.content, "type": n.node_type, "mode": n.mode, "custom_data": dict(n.custom_data) } for n in self.nodes ],
            "connections": list(self.connections)
        }
        self.undo_stack.append(state)
        if len(self.undo_stack) > 50: self.undo_stack.pop(0)
        if clear_redo: self.redo_stack.clear()
        self.set_dirty(True)

    def restore_state(self, state):
        self._reset_canvas()
        id_map = {}
        for nd in state["nodes"]:
            node = Node(self, nd["x"], nd["y"], nd["title"], nd["content"], nd["type"], dict(nd.get("custom_data", {})), nd.get("mode", "standard"))
            node.id = nd["id"]
            self.nodes.append(node)
            id_map[nd["id"]] = node.id
        for c in state["connections"]:
            if c["from"] in id_map and c["to"] in id_map:
                self.connections.append({"from": id_map[c["from"]], "out_idx": c["out_idx"], "to": id_map[c["to"]]})
        self.redraw()

    def undo(self, event=None):
        if not self.undo_stack: return
        current_state = {
            "nodes": [ { "id": n.id, "x": n.x, "y": n.y, "title": n.title, "content": n.content, "type": n.node_type, "mode": n.mode, "custom_data": dict(n.custom_data) } for n in self.nodes ],
            "connections": list(self.connections)
        }
        self.redo_stack.append(current_state)
        state = self.undo_stack.pop()
        self.restore_state(state)
        self.selected_nodes = []

    def redo(self, event=None):
        if not self.redo_stack: return
        current_state = {
            "nodes": [ { "id": n.id, "x": n.x, "y": n.y, "title": n.title, "content": n.content, "type": n.node_type, "mode": n.mode, "custom_data": dict(n.custom_data) } for n in self.nodes ],
            "connections": list(self.connections)
        }
        self.undo_stack.append(current_state)
        state = self.redo_stack.pop()
        self.restore_state(state)
        self.selected_nodes = []

    def copy(self, event=None):
        if not self.selected_nodes: return
        self.clipboard = {
            "nodes": [ { "id": n.id, "x": n.x, "y": n.y, "title": n.title, "content": n.content, "type": n.node_type, "mode": n.mode, "custom_data": dict(n.custom_data) } for n in self.selected_nodes ],
            "connections": []
        }
        sel_ids = {n.id for n in self.selected_nodes}
        for c in self.connections:
            if c["from"] in sel_ids and c["to"] in sel_ids:
                self.clipboard["connections"].append(c)

    def paste(self, event=None):
        if getattr(self, 'clipboard', None) is None or not self.clipboard.get("nodes"): return
        self.save_state()
        offset_x, offset_y = 50, 50
        id_map = {}
        new_selection = []
        for nd in self.clipboard["nodes"]:
            node = Node(self, nd["x"] + offset_x, nd["y"] + offset_y, nd["title"], nd["content"], nd["type"], dict(nd.get("custom_data", {})), nd.get("mode", "standard"))
            self.nodes.append(node)
            id_map[nd["id"]] = node.id
            new_selection.append(node)
        for c in self.clipboard["connections"]:
            self.connections.append({"from": id_map[c["from"]], "out_idx": c["out_idx"], "to": id_map[c["to"]]})
        self.selected_nodes = new_selection
        self.redraw()

    def duplicate(self, event=None):
        self.copy()
        self.paste()

    def delete_selected(self, event=None):
        if not self.selected_nodes and not getattr(self, 'selected_connection', None): return
        self.save_state()
        if getattr(self, 'selected_connection', None):
            if self.selected_connection in self.connections:
                self.connections.remove(self.selected_connection)
            self.selected_connection = None
        if self.selected_nodes:
            sel_ids = {n.id for n in self.selected_nodes}
            self.nodes = [n for n in self.nodes if n not in self.selected_nodes]
            self.connections = [c for c in self.connections if c["from"] not in sel_ids and c["to"] not in sel_ids]
            self.selected_nodes = []
        self.redraw()

    def add_node(self, ntype, x=None, y=None, title=None, content=None, custom_data=None, mode="standard", save_history=True):
        if save_history:
            self.save_state()
            
        if x is None: 
            x = self.canvas.canvasx(self.winfo_width() / 2) - 90
            y = self.canvas.canvasy(self.winfo_height() / 2) - 50
        
        if x < 0: x = 10 
        
        if title is None: 
            if ntype == 'story':
                # Если в проекте уже есть персонаж, предлагаем имя последнего активного говорящего
                last_story = next((n for n in reversed(self.nodes) if n.node_type == 'story' and n.title and not n.title.startswith('#') and n.title != "Сцена"), None)
                title = last_story.title if last_story else "Персонаж"
            elif ntype == 'choice':
                title = "Выбор"
            elif ntype == 'music':
                title = "Музыка"
            elif ntype == 'condition':
                title = "Условие"
            else:
                title = ntype.capitalize()
        if content is None: 
            content = "Текст..." if ntype == 'story' else ("Вар 1\nВар 2" if ntype == 'choice' else "Нет файла")
        
        node = Node(self, x, y, title, content, ntype, custom_data, mode)
        node.width = max(80, int(180 * self.zoom_level))
        font_size = max(6, int(9 * self.zoom_level))
        node.font_content.configure(size=font_size)
        node.calculate_size()
        node.is_new = save_history
        self.nodes.append(node)
        self.redraw()
        self.plugin_manager.notify('node_added', node)
        self.set_dirty(True)
        return node

    def redraw(self):
        self.canvas.delete("node")
        self.canvas.delete("port")
        self.canvas.delete("conn")
        # Сбрасываем ссылки на изображения плагина media_node перед перерисовкой
        self.canvas._media_image_refs = []
        
        for conn in self.connections:
            self.draw_connection(conn)
        for node in self.nodes:
            node.outputs = []
            node.draw(self.canvas)

    def draw_connection(self, conn):
        from_node = self.find_node_by_id(conn['from'])
        to_node = self.find_node_by_id(conn['to'])
        if from_node and to_node:
            start = from_node.get_output_pos(conn['out_idx'])
            end = to_node.get_input_pos()
            is_selected = (getattr(self, 'selected_connection', None) == conn)
            color = COLORS['line_active'] if is_selected else COLORS['line']
            conn_tag = f"conn_{conn['from']}_{conn['out_idx']}_{conn['to']}"
            self.draw_bezier(start, end, tags=("conn", conn_tag), fill=color)

    def draw_bezier(self, start, end, tags="conn", fill=None):
        if fill is None: fill = COLORS['line']
        x1, y1 = start; x2, y2 = end
        dist = abs(x2 - x1) * 0.5
        self.canvas.create_line(x1, y1, x1+dist, y1, x2-dist, y2, x2, y2, 
                                smooth=True, width=2, fill=fill, arrow=tk.LAST, tags=tags)

    def on_click(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.drag_data["moved"] = False
        
        items = self.canvas.find_overlapping(x-5, y-5, x+5, y+5)
        for item in items:
            tags = self.canvas.gettags(item)
            if "output" in tags:
                tag_info = tags[2].split('_')
                self.conn_drag.update({"active": True, "start_node": self.find_node_by_id(tag_info[2]), "start_idx": int(tag_info[3])})
                self.conn_drag["line_id"] = self.canvas.create_line(x, y, x, y, fill=COLORS['line_active'], width=2, dash=(2,2))
                return
                
        for item in items:
            tags = self.canvas.gettags(item)
            if "conn" in tags and len(tags) > 1 and tags[1].startswith("conn_"):
                parts = tags[1].split('_')
                from_id = parts[1]
                out_idx = int(parts[2])
                to_id = parts[3]
                for conn in self.connections:
                    if conn['from'] == from_id and conn['out_idx'] == out_idx and conn['to'] == to_id:
                        self.selected_connection = conn
                        self.selected_nodes = []
                        self.redraw()
                        return
                        
        for node in reversed(self.nodes):
            if node.is_inside(x, y):
                self.selected_connection = None
                if event.state & 0x0001: # Shift held
                    if node in self.selected_nodes:
                        self.selected_nodes.remove(node)
                    else:
                        self.selected_nodes.append(node)
                else:
                    if node not in self.selected_nodes:
                        self.selected_nodes = [node]
                        
                self.drag_data.update({"item": node, "x": x, "y": y})
                self.save_state() # Save state before potential move
                self.redraw()
                return

        if not (event.state & 0x0001):
            self.selected_nodes = []
            self.selected_connection = None
            
        self.marquee_start = (x, y)
        self.marquee_id = self.canvas.create_rectangle(x, y, x, y, outline='#4a90e2', dash=(2, 2), tags="marquee")
        self.redraw()

    def on_drag(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.conn_drag["active"]:
            start = self.conn_drag["start_node"].get_output_pos(self.conn_drag["start_idx"])
            self.canvas.coords(self.conn_drag["line_id"], start[0], start[1], x, y)
        elif self.marquee_start:
            self.canvas.coords(self.marquee_id, self.marquee_start[0], self.marquee_start[1], x, y)
        elif self.drag_data.get("item"):
            self.drag_data["moved"] = True
            dx = x - self.drag_data["x"]
            dy = y - self.drag_data["y"]
            for node in self.selected_nodes:
                node.x += dx
                node.y += dy
                if node.x < 0: node.x = 0
            self.drag_data.update({"x": x, "y": y})
            self.redraw()

    def on_release(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.conn_drag["active"]:
            self.save_state()
            self.canvas.delete(self.conn_drag["line_id"])
            target = None
            items = self.canvas.find_overlapping(x-10, y-10, x+10, y+10)
            for item in items:
                tags = self.canvas.gettags(item)
                if "input" in tags:
                    target = self.find_node_by_id(tags[2].split('_')[2])
                    break
            if not target:
                for node in self.nodes:
                    if node.is_inside(x, y) and node != self.conn_drag["start_node"]:
                        target = node
                        break
            if target:
                self.connections.append({'from': self.conn_drag["start_node"].id, 'out_idx': self.conn_drag["start_idx"], 'to': target.id})
                self.redraw()
            else:
                self.undo_stack.pop() # Discard state if no connection made
            self.conn_drag["active"] = False
            
        elif self.marquee_start:
            x1, y1 = self.marquee_start
            x2, y2 = x, y
            x1, x2 = min(x1, x2), max(x1, x2)
            y1, y2 = min(y1, y2), max(y1, y2)
            for node in self.nodes:
                if (x1 <= node.x <= x2 or x1 <= node.x + node.width <= x2) and \
                   (y1 <= node.y <= y2 or y1 <= node.y + node.height <= y2):
                    if node not in self.selected_nodes:
                        self.selected_nodes.append(node)
            self.canvas.delete(self.marquee_id)
            self.marquee_start = None
            self.marquee_id = None
            self.redraw()
            
        elif self.drag_data.get("item") and not self.drag_data.get("moved", False):
            # If clicked but not moved, pop the save_state we made in on_click
            if self.undo_stack:
                self.undo_stack.pop()
                
        self.drag_data["item"] = None

    def on_double_click(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for node in reversed(self.nodes):
            if node.is_inside(x, y):
                self.edit_node(node)
                return

    def on_right_click(self, event):
        menu = tk.Menu(self, tearoff=0)
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        
        # 1. Проверяем клик по портам
        port_hit = False
        port_action = None
        port_node = None
        port_index = 0

        # Вспомогательная функция для расчета дистанции
        def dist(x1, y1, x2, y2):
            return math.hypot(x2 - x1, y2 - y1)

        for node in self.nodes:
            # Проверка входного порта
            ix, iy = node.get_input_pos()
            if dist(x, y, ix, iy) <= 10:
                port_hit = True
                port_node = node
                port_action = "input"
                break
            
            # Проверка выходных портов
            for out in node.outputs:
                if dist(x, y, out['x'], out['y']) <= 10:
                    port_hit = True
                    port_node = node
                    port_action = "output"
                    port_index = out['id']
                    break
            if port_hit: break

        if port_hit:
            if port_action == "input":
                menu.add_command(label="Удалить входящие связи", command=lambda: self.disconnect_input(port_node))
            elif port_action == "output":
                menu.add_command(label="Удалить эту связь", command=lambda: self.disconnect_output(port_node, port_index))
            menu.tk_popup(event.x_root, event.y_root)
            return

        # 2. Обычный клик по ноде или фону
        target = next((n for n in reversed(self.nodes) if n.is_inside(x, y)), None)
        
        if target:
            menu.add_command(label="Редактировать", command=lambda: self.edit_node(target))
            menu.add_separator()
            
            # --- Подменю цвета блока (работает для одного или группы выделенных) ---
            color_menu = tk.Menu(menu, tearoff=0, bg='#252526', fg='white', activebackground='#094771')
            selected_targets = self.selected_nodes if (target in self.selected_nodes and len(self.selected_nodes) > 1) else [target]
            
            for name, bg_col, head_col in NODE_COLOR_PRESETS:
                color_menu.add_command(
                    label=name,
                    command=lambda b=bg_col, h=head_col, tgts=selected_targets: self.set_nodes_color(tgts, b, h)
                )
            color_menu.add_separator()
            color_menu.add_command(
                label="🎨 Выбрать свой цвет...",
                command=lambda tgts=selected_targets: self.pick_custom_color_for_nodes(tgts)
            )
            color_menu.add_command(
                label="🔄 Сбросить к стандартному",
                command=lambda tgts=selected_targets: self.reset_nodes_color(tgts)
            )
            menu.add_cascade(label="🎨 Цвет блока", menu=color_menu)
            menu.add_separator()

            # Дополнительные опции удаления связей из самой ноды (на всякий случай)
            menu.add_command(label="Удалить все входящие", command=lambda: self.disconnect_input(target))
            menu.add_command(label="Удалить все исходящие", command=lambda: self.disconnect_output(target, -1)) # -1 значит все
            menu.add_separator()
            if len(self.selected_nodes) > 1 and target in self.selected_nodes:
                menu.add_command(label="Удалить выделенные блоки", command=self.delete_selected)
            else:
                menu.add_command(label="Удалить блок", command=lambda: self.delete_node(target))
        else:
            pass
        self.plugin_manager.notify('context_menu', {'target': target, 'x': x, 'y': y, 'menu': menu})
        
        menu.tk_popup(event.x_root, event.y_root)

    def disconnect_input(self, node):
        """Удаляет все связи, ведущие к этому узлу."""
        if any(c['to'] == node.id for c in self.connections):
            self.save_state()
            self.connections = [c for c in self.connections if c['to'] != node.id]
            self.redraw()

    def disconnect_output(self, node, out_idx):
        """Удаляет исходящую связь с конкретного индекса или все (-1)."""
        needs_update = False
        if out_idx == -1:
            needs_update = any(c['from'] == node.id for c in self.connections)
        else:
            needs_update = any(c['from'] == node.id and c['out_idx'] == out_idx for c in self.connections)
            
        if needs_update:
            self.save_state()
            if out_idx == -1:
                self.connections = [c for c in self.connections if c['from'] != node.id]
            else:
                self.connections = [c for c in self.connections if not (c['from'] == node.id and c['out_idx'] == out_idx)]
            self.redraw()

    def edit_node(self, node):
        self.save_state()
        dialog = tk.Toplevel(self)
        dialog.title("Редактор блока")
        dialog.geometry("520x760")
        dialog.configure(bg=COLORS['bg'])
        dialog.attributes('-topmost', True) 

        # --- Заголовок / Имя персонажа ---
        is_story = (node.node_type == 'story')
        title_lbl_text = "👤 Имя персонажа (# или пусто — слова автора/мысли):" if is_story else "🏷️ Заголовок блока (# — скрыть):"
        tk.Label(dialog, text=title_lbl_text, bg=COLORS['bg'], fg='white').pack(pady=5)

        title_frame = tk.Frame(dialog, bg=COLORS['bg'])
        title_frame.pack(fill=tk.X, padx=10)

        # Собираем список уже используемых персонажей в проекте
        existing_chars = sorted(list({
            n.title.strip() for n in self.nodes 
            if n.node_type == 'story' and n.title.strip() and not n.title.strip().startswith('#') and n.title.strip() not in ('Сцена', 'Персонаж')
        }))

        if is_story and existing_chars:
            from tkinter import ttk
            e_title = ttk.Combobox(title_frame, values=existing_chars, font=("Segoe UI", 9))
            e_title.set(node.title)
            e_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
            e_title.bind("<<ComboboxSelected>>", lambda e: auto_save())
        else:
            e_title = tk.Entry(title_frame, bg='#333', fg='white', insertbackground='white', font=("Segoe UI", 9))
            e_title.insert(0, node.title)
            e_title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        if is_story:
            def set_narrator():
                from tkinter import ttk
                if isinstance(e_title, ttk.Combobox):
                    e_title.set("#")
                else:
                    e_title.delete(0, tk.END)
                    e_title.insert(0, "#")
                auto_save()

            tk.Button(title_frame, text="💭 Слова автора (#)", command=set_narrator,
                      bg='#333333', fg='#aaaaaa', relief='flat', font=("Segoe UI", 8), padx=6).pack(side=tk.RIGHT, padx=(5, 0))

        # --- Блок оформления / цветов ---
        color_frame = tk.LabelFrame(dialog, text="🎨 Оформление блока", bg=COLORS['bg'], fg='white', padx=8, pady=8)
        color_frame.pack(fill=tk.X, padx=10, pady=5)

        # Превью блока
        default_bg = COLORS.get(f'node_{node.node_type}', COLORS['node_story'])
        default_head = COLORS.get(f'header_{node.node_type}', COLORS['header_story'])
        
        preview_box = tk.Frame(color_frame, bg=node.custom_data.get('bg_color', default_bg), relief='solid', bd=1, height=45)
        preview_box.pack(fill=tk.X, pady=(0, 6))
        preview_box.pack_propagate(False)

        preview_head = tk.Frame(preview_box, bg=node.custom_data.get('header_color', default_head), height=20)
        preview_head.pack(fill=tk.X, side=tk.TOP)
        preview_head.pack_propagate(False)

        lbl_head_title = tk.Label(preview_head, text=node.title or "Заголовок", 
                                  bg=node.custom_data.get('header_color', default_head),
                                  fg=node.custom_data.get('header_text_color', 'white'), 
                                  font=("Segoe UI", 8, "bold"), anchor='w', padx=5)
        lbl_head_title.pack(fill=tk.BOTH, expand=True)

        lbl_body_preview = tk.Label(preview_box, text="Образец текста блока", 
                                    bg=node.custom_data.get('bg_color', default_bg),
                                    fg=node.custom_data.get('text_color', COLORS['text']), 
                                    font=("Segoe UI", 8), anchor='w', padx=5)
        lbl_body_preview.pack(fill=tk.BOTH, expand=True)

        def update_preview():
            bg_col = node.custom_data.get('bg_color', default_bg)
            head_col = node.custom_data.get('header_color', default_head)
            txt_col = node.custom_data.get('text_color', COLORS['text'])
            head_txt_col = node.custom_data.get('header_text_color', 'white')

            preview_box.config(bg=bg_col)
            preview_head.config(bg=head_col)
            lbl_head_title.config(text=e_title.get() or "Заголовок", bg=head_col, fg=head_txt_col)
            lbl_body_preview.config(bg=bg_col, fg=txt_col)

        # Палитра быстрых пресетов
        palette_frame = tk.Frame(color_frame, bg=COLORS['bg'])
        palette_frame.pack(fill=tk.X, pady=4)

        for _, bg_c, head_c in NODE_COLOR_PRESETS:
            tk.Button(
                palette_frame,
                bg=bg_c,
                activebackground=head_c,
                width=2,
                height=1,
                relief='flat',
                cursor='hand2',
                command=lambda b=bg_c, h=head_c: apply_preset(b, h)
            ).pack(side=tk.LEFT, padx=2)

        def apply_preset(b, h):
            node.custom_data['bg_color'] = b
            node.custom_data['header_color'] = h
            update_preview()
            self.redraw()

        # Кнопки детального выбора цвета
        btn_grid = tk.Frame(color_frame, bg=COLORS['bg'])
        btn_grid.pack(fill=tk.X, pady=(4, 0))

        def pick_bg():
            cur = node.custom_data.get('bg_color', default_bg)
            col = colorchooser.askcolor(color=cur, title="Цвет фона блока", parent=dialog)
            if col and col[1]:
                node.custom_data['bg_color'] = col[1]
                node.custom_data['header_color'] = darken_color(col[1], 0.75)
                update_preview()
                self.redraw()

        def pick_header_bg():
            cur = node.custom_data.get('header_color', default_head)
            col = colorchooser.askcolor(color=cur, title="Цвет шапки блока", parent=dialog)
            if col and col[1]:
                node.custom_data['header_color'] = col[1]
                update_preview()
                self.redraw()

        def pick_header_txt():
            cur = node.custom_data.get('header_text_color', 'white')
            col = colorchooser.askcolor(color=cur, title="Цвет текста заголовка", parent=dialog)
            if col and col[1]:
                node.custom_data['header_text_color'] = col[1]
                update_preview()
                self.redraw()

        def pick_text_color():
            cur = node.custom_data.get('text_color', COLORS['text'])
            col = colorchooser.askcolor(color=cur, title="Цвет основного текста", parent=dialog)
            if col and col[1]:
                node.custom_data['text_color'] = col[1]
                update_preview()
                self.redraw()

        def reset_colors():
            node.custom_data.pop('bg_color', None)
            node.custom_data.pop('header_color', None)
            node.custom_data.pop('text_color', None)
            node.custom_data.pop('header_text_color', None)
            update_preview()
            self.redraw()

        btn_style = {'bg': '#333333', 'fg': 'white', 'relief': 'flat', 'font': ('Segoe UI', 8), 'padx': 6, 'pady': 2, 'cursor': 'hand2'}

        tk.Button(btn_grid, text="Фон...", command=pick_bg, **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_grid, text="Шапка...", command=pick_header_bg, **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_grid, text="Текст заголовка...", command=pick_header_txt, **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_grid, text="Текст...", command=pick_text_color, **btn_style).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_grid, text="🔄 Сброс", command=reset_colors, **btn_style).pack(side=tk.RIGHT, padx=2)

        # --- Контент ---
        tk.Label(dialog, text="Текст / Контент:", bg=COLORS['bg'], fg='white').pack(pady=5)
        t_content = tk.Text(dialog, height=8, bg='#333', fg='white', insertbackground='white')
        t_content.insert("1.0", node.content)
        t_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # --- Функционал выделения слов ---
        hl_frame = tk.LabelFrame(dialog, text="Выделение слов цветом", bg=COLORS['bg'], fg='white', padx=5, pady=5)
        hl_frame.pack(fill=tk.X, padx=10, pady=5)

        def highlight_selected_word():
            try:
                sel_start = t_content.index(tk.SEL_FIRST)
                sel_end = t_content.index(tk.SEL_LAST)
                selected_fragment = t_content.get(sel_start, sel_end) 
                
                if not selected_fragment:
                    return

                color = colorchooser.askcolor(title=f"Цвет для '{selected_fragment}'", parent=dialog)
                if color[1]:
                    if 'highlights' not in node.custom_data:
                        node.custom_data['highlights'] = {}
                    node.custom_data['highlights'][selected_fragment] = color[1]
                    self.redraw()
            except tk.TclError:
                messagebox.showwarning("Внимание", "Сначала выделите фрагмент в тексте мышкой!", parent=dialog)

        def clear_highlights():
            if 'highlights' in node.custom_data:
                node.custom_data['highlights'] = {}
                self.redraw()

        btn_hl_word = tk.Button(hl_frame, text="Окрасить фрагмент", command=highlight_selected_word, bg='#2d4a57', fg='white')
        btn_hl_word.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        btn_cl_hl = tk.Button(hl_frame, text="Сбросить выделение", command=clear_highlights, bg='#a93226', fg='white')
        btn_cl_hl.pack(side=tk.RIGHT, padx=5, expand=True, fill=tk.X)
        
        # --- Фрейм для плагинов ---
        plugin_frame = tk.Frame(dialog, bg=COLORS['bg'])
        plugin_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.plugin_manager.notify('node_edit_dialog', {'node': node, 'frame': plugin_frame, 'dialog': dialog})

        # --- АВТОСОХРАНЕНИЕ ---
        def auto_save(event=None):
            node.title = e_title.get()
            node.content = t_content.get("1.0", tk.END).strip()
            node.calculate_size()
            update_preview()
            self.redraw()

        e_title.bind("<KeyRelease>", auto_save)
        t_content.bind("<KeyRelease>", auto_save)
        # Для Radiobutton bind сложнее, поэтому обновление при закрытии или сохранении

        def save():
            node.title = e_title.get()
            node.content = t_content.get("1.0", tk.END).strip()
            
            self.plugin_manager.notify('node_edit_save', {'node': node})
            node.calculate_size()
            self.redraw() 
            dialog.destroy()

        tk.Button(dialog, text="Сохранить и Закрыть", command=save, bg=COLORS['header_story'], fg='white').pack(pady=10)

    def open_search_replace(self):
        dialog = tk.Toplevel(self)
        dialog.title("Поиск и Замена")
        dialog.geometry("350x250")
        dialog.configure(bg=COLORS['bg'])
        dialog.attributes('-topmost', True) 

        tk.Label(dialog, text="Найти (текст):", bg=COLORS['bg'], fg='white').pack(pady=5)
        e_find = tk.Entry(dialog, bg='#333', fg='white')
        e_find.pack(fill=tk.X, padx=10)

        tk.Label(dialog, text="Заменить на:", bg=COLORS['bg'], fg='white').pack(pady=5)
        e_replace = tk.Entry(dialog, bg='#333', fg='white')
        e_replace.pack(fill=tk.X, padx=10)
        
        lbl_info = tk.Label(dialog, text="Оставьте 'Найти' пустым ничего не произойдет", bg=COLORS['bg'], fg='#888', font=("Segoe UI", 8))
        lbl_info.pack(pady=5)

        def do_replace():
            find_str = e_find.get()
            replace_str = e_replace.get()
            
            if not find_str:
                return
            
            count = 0
            for node in self.nodes:
                changed = False
                if find_str in node.title:
                    node.title = node.title.replace(find_str, replace_str)
                    changed = True
                    count += 1
                
                if find_str in node.content:
                    node.content = node.content.replace(find_str, replace_str)
                    changed = True
                    count += 1
                
                if changed:
                    node.calculate_size()
            
            if count > 0:
                self.redraw()
                messagebox.showinfo("Успех", f"Произведено замен: {count}", parent=dialog)
                dialog.destroy()
            else:
                messagebox.showinfo("Инфо", "Совпадений не найдено", parent=dialog)

        tk.Button(dialog, text="Заменить везде", command=do_replace, bg=COLORS['header_choice'], fg='white').pack(pady=15)

    def delete_node(self, node):
        self.save_state()
        if node in self.nodes:
            self.nodes.remove(node)
            self.connections = [c for c in self.connections if c['from'] != node.id and c['to'] != node.id]
            if node in self.selected_nodes:
                self.selected_nodes.remove(node)
            self.redraw()

    def set_nodes_color(self, nodes, bg_color, header_color):
        if not nodes: return
        self.save_state()
        for node in nodes:
            node.custom_data['bg_color'] = bg_color
            node.custom_data['header_color'] = header_color
        self.redraw()
        self.set_dirty(True)

    def pick_custom_color_for_nodes(self, nodes):
        if not nodes: return
        default_bg = COLORS.get(f'node_{nodes[0].node_type}', COLORS['node_story'])
        current_bg = nodes[0].custom_data.get('bg_color', default_bg)
        color = colorchooser.askcolor(color=current_bg, title="Выберите цвет блоков", parent=self)
        if color and color[1]:
            bg_col = color[1]
            head_col = darken_color(bg_col, 0.75)
            self.set_nodes_color(nodes, bg_col, head_col)

    def reset_nodes_color(self, nodes):
        if not nodes: return
        self.save_state()
        for node in nodes:
            node.custom_data.pop('bg_color', None)
            node.custom_data.pop('header_color', None)
            node.custom_data.pop('text_color', None)
            node.custom_data.pop('header_text_color', None)
        self.redraw()
        self.set_dirty(True)

    def find_node_by_id(self, nid):
        for n in self.nodes:
            if n.id == nid: return n
        return None
    
    def _reset_canvas(self):
        """Внутренний сброс холста без диалогов (для Undo/Redo и чистой загрузки)."""
        self.nodes = []
        self.connections = []
        self.selected_nodes = []
        if hasattr(self, 'selected_connection'):
            self.selected_connection = None
        self.redraw()

    def clear_all(self):
        """Очистить холст по запросу пользователя из меню/кнопки."""
        if self.nodes or self.connections:
            res = messagebox.askyesno("Очистить холст", "Вы уверены, что хотите удалить ВСЕ ноды и связи?\nЭто действие можно будет отменить через Ctrl+Z.", parent=self)
            if not res:
                return
        self.save_state()
        self._reset_canvas()
        self.set_dirty(True)

    def start_pan(self, event):
        self.is_panning = True
        self.velocity_x = 0
        self.velocity_y = 0
        self.mouse_last_x = event.x
        self.mouse_last_y = event.y

    def do_pan(self, event):
        dx = self.mouse_last_x - event.x
        dy = self.mouse_last_y - event.y
        
        self.canvas.xview_scroll(int(dx), "units")
        self.canvas.yview_scroll(int(dy), "units")
        
        self.velocity_x = dx
        self.velocity_y = dy
        
        self.mouse_last_x = event.x
        self.mouse_last_y = event.y

    def stop_pan(self, event):
        self.is_panning = False

    def save_project(self):
        nodes_data = []
        for n in self.nodes:
            is_char = not n.title.startswith('#')
            nd = {
                "id": n.id, 
                "x": n.x, 
                "y": n.y, 
                "title": n.title, 
                "content": n.content, 
                "type": n.node_type,
                "mode": n.mode, # Сохраняем режим
                "custom_data": n.custom_data,
                "is_character": is_char  
            }
            nodes_data.append(nd)

        data = {
            "nodes": nodes_data,
            "connections": self.connections
        }
        if not getattr(self, 'current_file', None):
            f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        else:
            f = self.current_file
            
        if f:
            with open(f, 'w', encoding='utf-8') as file: json.dump(data, file, indent=4, ensure_ascii=False)
            self.current_file = f
            self.set_dirty(False)

    def zoom_in(self, event=None):
        self.apply_zoom(1.15, event)

    def zoom_out(self, event=None):
        self.apply_zoom(1 / 1.15, event)

    def zoom_reset(self, event=None):
        if self.zoom_level == 1.0:
            return
        self.apply_zoom(1.0 / self.zoom_level, event, target_zoom=1.0)

    def on_mousewheel(self, event):
        # Если зажат Ctrl - зумим
        if event.state & 0x0004 or event.state & 0x0001:
            if event.delta > 0:
                self.zoom_in(event)
            elif event.delta < 0:
                self.zoom_out(event)

    def apply_zoom(self, factor, event=None, target_zoom=None):
        new_zoom = target_zoom if target_zoom is not None else round(self.zoom_level * factor, 3)
        if new_zoom < self.min_zoom or new_zoom > self.max_zoom:
            return
        actual_factor = new_zoom / self.zoom_level
        self.zoom_level = new_zoom

        # Центр зума
        if event and hasattr(event, 'x') and hasattr(event, 'y'):
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
        else:
            cx = self.canvas.canvasx(self.canvas.winfo_width() / 2)
            cy = self.canvas.canvasy(self.canvas.winfo_height() / 2)

        # Масштабируем ноды
        for node in self.nodes:
            node.x = cx + (node.x - cx) * actual_factor
            node.y = cy + (node.y - cy) * actual_factor
            node.width = max(80, int(180 * self.zoom_level))
            font_size = max(6, int(9 * self.zoom_level))
            node.font_content.configure(size=font_size)
            node.calculate_size()

        if hasattr(self, 'lbl_zoom'):
            self.lbl_zoom.config(text=f"{int(self.zoom_level * 100)}%")
        self.redraw()

    def load_project(self, file_path=None):
        f = file_path or filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if f:
            if getattr(self, 'is_dirty', False):
                resp = messagebox.askyesnocancel("Несохранённые изменения", "В текущем проекте есть несохранённые изменения.\nСохранить их перед открытием?", parent=self)
                if resp is None:
                    return
                if resp:
                    self.save_project()
            self._reset_canvas()
            self.undo_stack.clear()
            self.redo_stack.clear()
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                id_map = {}
                for n_data in data['nodes']:
                    node = self.add_node(
                        ntype=n_data['type'],
                        x=n_data['x'],
                        y=n_data['y'],
                        title=n_data['title'],
                        content=n_data['content'],
                        custom_data=n_data.get('custom_data', {}),
                        mode=n_data.get('mode', "standard"), # Загружаем режим
                        save_history=False
                    )
                    id_map[n_data['id']] = node.id
                for c in data['connections']:
                    if c['from'] in id_map and c['to'] in id_map:
                        self.connections.append({'from': id_map[c['from']], 'out_idx': c['out_idx'], 'to': id_map[c['to']]})
                
                self.current_file = f
                self.set_dirty(False)
                self.redraw()

if __name__ == "__main__":
    import sys
    app = ScenarioEditor()
    if len(sys.argv) > 1 and sys.argv[1].endswith('.json'):
        app.after(100, lambda: app.load_project(sys.argv[1]))
    app.mainloop()