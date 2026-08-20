import os
import sys

# --- ПУТИ ДЛЯ СТАБИЛЬНОГО ЗАПУСКА (Double-Click Fix) ---
# Определяем директорию скрипта и делаем её рабочей
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

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
        
        # ЛОГИКА ОТОБРАЖЕНИЯ ИМЕНИ:
        final_title = display_title
        if display_title.startswith('#'):
            final_title = ""
            
        canvas.create_text(x+10, y+12, text=final_title, fill=header_text_col, anchor="w", font=("Segoe UI", 9, "bold"), tags=("node", self.id))

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
        if self.node_type == 'choice':
            return (self.x + self.width, self.y + 35 + (index * 25))
        return (self.x + self.width, self.y + self.height/2)

    def get_input_pos(self):
        y_pos = self.y + 25 if self.node_type == 'choice' else self.y + self.height/2
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

        # --- Новые переменные ---
        self.selected_nodes = []
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
        self.toolbar = tk.Frame(self, bg=COLORS['bg'], height=40)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        
        # --- ПАНЕЛЬ НАВИГАЦИИ (Breadcrumbs) ---
        self.nav_bar = tk.Frame(self, bg='#333', height=30)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X)
        self.lbl_path = tk.Label(self.nav_bar, text="Root", bg='#333', fg='#4a90e2', font=("Segoe UI", 9, "bold"))
        self.lbl_path.pack(side=tk.LEFT, padx=10)
        
        btn_cfg = {'bg': '#444', 'fg': 'white', 'relief': 'flat', 'padx': 10, 'pady': 5}
        
        tk.Button(self.toolbar, text="Новый Сюжет", command=lambda: self.add_node('story'), **btn_cfg).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(self.toolbar, text="Новый Выбор", command=lambda: self.add_node('choice'), **btn_cfg).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(self.toolbar, text="Очистить", command=self.clear_all, **btn_cfg).pack(side=tk.LEFT, padx=20, pady=5)
        
        tk.Button(self.toolbar, text="Поиск/Замена", command=self.open_search_replace, **btn_cfg).pack(side=tk.RIGHT, padx=5, pady=5)
        tk.Button(self.toolbar, text="Загрузить JSON", command=self.load_project, **btn_cfg).pack(side=tk.RIGHT, padx=5, pady=5)
        tk.Button(self.toolbar, text="Сохранить JSON", command=self.save_project, **btn_cfg).pack(side=tk.RIGHT, padx=5, pady=5)

        self.canvas = tk.Canvas(self, bg=COLORS['canvas_bg'], highlightthickness=0, xscrollincrement=1, yscrollincrement=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        
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
        self.clear_all()
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
        if not self.selected_nodes: return
        self.save_state()
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
            title = "Сцена" if ntype == 'story' else ("Выбор" if ntype == 'choice' else "Музыка")
        if content is None: 
            content = "Текст..." if ntype == 'story' else ("Вар 1\nВар 2" if ntype == 'choice' else "Нет файла")
        
        node = Node(self, x, y, title, content, ntype, custom_data, mode)
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
            self.draw_bezier(start, end)

    def draw_bezier(self, start, end):
        x1, y1 = start; x2, y2 = end
        dist = abs(x2 - x1) * 0.5
        self.canvas.create_line(x1, y1, x1+dist, y1, x2-dist, y2, x2, y2, 
                                smooth=True, width=2, fill=COLORS['line'], arrow=tk.LAST, tags="conn")

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
                
        for node in reversed(self.nodes):
            if node.is_inside(x, y):
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
        dialog.geometry("500x700") # Увеличили высоту
        dialog.configure(bg=COLORS['bg'])
        dialog.attributes('-topmost', True) 

        # --- Заголовок ---
        tk.Label(dialog, text="Заголовок (Имя персонажа, # - скрыть):", bg=COLORS['bg'], fg='white').pack(pady=5)
        e_title = tk.Entry(dialog, bg='#333', fg='white')
        e_title.insert(0, node.title)
        e_title.pack(fill=tk.X, padx=10)

        # Кнопка: Цвет заголовка
        def pick_header_text_color():
            current_color = node.custom_data.get('header_text_color', 'white')
            color = colorchooser.askcolor(color=current_color, title="Цвет текста заголовка", parent=dialog)
            if color[1]:
                node.custom_data['header_text_color'] = color[1]
                self.redraw()

        # --- Кнопки цветов ---
        btn_frame = tk.Frame(dialog, bg=COLORS['bg'])
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        btn_h_color = tk.Button(btn_frame, text="Цвет Заголовка", command=pick_header_text_color, bg='#555', fg='white', width=20)
        btn_h_color.grid(row=0, column=0, padx=2, pady=2)

        # --- Режим (Только для Story) ---
        mode_var = None
        if node.node_type == 'story':
            mode_frame = tk.LabelFrame(dialog, text="Режим узла", bg=COLORS['bg'], fg='white', padx=5, pady=5)
            mode_frame.pack(fill=tk.X, padx=10, pady=5)
            mode_var = tk.StringVar(value=getattr(node, 'mode', 'standard'))
            tk.Radiobutton(mode_frame, text="Стандарт", variable=mode_var, value="standard",
                           bg=COLORS['bg'], fg='white', selectcolor='#555').pack(side=tk.LEFT, padx=5)
            tk.Radiobutton(mode_frame, text="Продолжение", variable=mode_var, value="continue",
                           bg=COLORS['bg'], fg='white', selectcolor='#555').pack(side=tk.LEFT, padx=5)

        # --- Контент ---
        tk.Label(dialog, text="Текст / Контент:", bg=COLORS['bg'], fg='white').pack(pady=5)
        t_content = tk.Text(dialog, height=8, bg='#333', fg='white', insertbackground='white')
        t_content.insert("1.0", node.content)
        t_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # --- Фрейм для плагинов ---
        plugin_frame = tk.Frame(dialog, bg=COLORS['bg'])
        plugin_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.plugin_manager.notify('node_edit_dialog', {'node': node, 'frame': plugin_frame, 'dialog': dialog})

        # --- АВТОСОХРАНЕНИЕ ---
        def auto_save(event=None):
            node.title = e_title.get()
            node.content = t_content.get("1.0", tk.END).strip()
            if node.node_type == 'story' and mode_var is not None:
                node.mode = mode_var.get()
            node.calculate_size()
            self.redraw()

        e_title.bind("<KeyRelease>", auto_save)
        t_content.bind("<KeyRelease>", auto_save)
        # Для Radiobutton bind сложнее, поэтому обновление при закрытии или сохранении

        def save():
            node.title = e_title.get()
            node.content = t_content.get("1.0", tk.END).strip()
            if node.node_type == 'story' and mode_var is not None:
                node.mode = mode_var.get()
            
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

    def find_node_by_id(self, nid):
        for n in self.nodes:
            if n.id == nid: return n
        return None
    
    def clear_all(self):
        self.nodes = []; self.connections = []; self.selected_nodes = []; self.redraw()

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

    def load_project(self, file_path=None):
        f = file_path or filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if f:
            self.clear_all()
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
    app = ScenarioEditor()
    app.mainloop()