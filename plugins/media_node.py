import tkinter as tk
from tkinter import filedialog, ttk
from plugin_system import Plugin
import json
import os
import sys

# Попытка импорта PIL (Pillow) для поддержки JPG и качественного ресайза
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[MediaBlock] Warning: 'pillow' library not found. JPG support is disabled.")

# Глобальный кэш изображений (хранит {path: ImageTk/PhotoImage})
IMAGE_CACHE = {}
# Кэш размеров изображений для calculate_size (хранит {path: (width, height)})
SIZE_CACHE = {}

class MediaBlockPlugin(Plugin):
    name = "MediaBlock"
    version = "2.0"  # Версия 2.0: Animations support

    def __init__(self, editor):
        super().__init__(editor)
        import sys
        main_module = sys.modules['__main__']
        self.NodeClass = getattr(main_module, 'Node', None)
        self.EditorClass = getattr(main_module, 'ScenarioEditor', None)
        self.COLORS = getattr(main_module, 'COLORS', {})
        
        if self.NodeClass:
            self.original_draw = self.NodeClass.draw
            self.original_calculate_size = self.NodeClass.calculate_size
            self.original_get_input_pos = getattr(self.NodeClass, 'get_input_pos', None)
            self.original_get_output_pos = getattr(self.NodeClass, 'get_output_pos', None)
        if self.EditorClass:
            self.original_edit_node = self.EditorClass.edit_node

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            self.add_toolbar_button(data)

        def new_draw(node_self, canvas):
            if node_self.node_type != 'media':
                self.original_draw(node_self, canvas)
                return

            x, y, w, h = node_self.x, node_self.y, node_self.width, node_self.height
            
            # Загрузка данных
            try:
                data = json.loads(node_self.content)
            except:
                data = {}

            img_path = data.get("image_path", "")
            mode = data.get("mode", "sprite")
            pos = data.get("position", "center")
            anim = data.get("animation", "none")

            # -- ЛОГИКА ОТРИСОВКИ --

            # 1. Основной фон
            canvas.create_rectangle(x, y, x+w, y+h, fill='#4b2c5e', outline=self.COLORS['grid_bold'], width=2, tags=("node", node_self.id))
            
            header_height = 25
            image_drawn = False
            
            if img_path and os.path.exists(img_path):
                ext = os.path.splitext(img_path)[1].lower()
                is_video = ext in ['.mp4', '.webm', '.mkv', '.ogv']
                
                try:
                    if is_video:
                        # Отрисовка заглушки для видео
                        canvas.create_rectangle(x + 10, y + header_height + 10, x + w - 10, y + h - 35, fill='#2c3e50', outline="#ecf0f1", tags=("node", node_self.id))
                        canvas.create_text(x + w/2, y + h/2, text="🎥 VIDEO\n(Preview Unavailable)", fill="white", justify="center", font=("Segoe UI", 9, "bold"), tags=("node", node_self.id))
                        image_drawn = True
                    else:
                        # Нормализуем ширину до int для стабильного кэш-ключа
                        target_w = int(w)
                        cache_key = f"{img_path}_{target_w}"
                        
                        if cache_key not in IMAGE_CACHE:
                            if HAS_PIL:
                                pil_img = Image.open(img_path)
                                aspect = pil_img.height / pil_img.width
                                target_h = int(target_w * aspect)
                                if target_h > 300: target_h = 300
                                
                                pil_img = pil_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                                tk_img = ImageTk.PhotoImage(pil_img)
                                IMAGE_CACHE[cache_key] = tk_img
                            else:
                                img = tk.PhotoImage(file=img_path)
                                if img.width() > target_w:
                                    factor = int(img.width() / target_w)
                                    if factor < 1: factor = 1
                                    img = img.subsample(factor, factor)
                                IMAGE_CACHE[cache_key] = img

                        tk_img = IMAGE_CACHE[cache_key]
                        img_h = tk_img.height()
                        
                        # Отрисовка картинки
                        # ВАЖНО: держим жёсткую ссылку на объект на canvas,
                        # иначе GC может уничтожить PhotoImage до/после перерисовки
                        if not hasattr(canvas, '_media_image_refs'):
                            canvas._media_image_refs = []
                        canvas._media_image_refs.append(tk_img)
                        
                        canvas.create_image(x + target_w / 2, y + header_height + img_h / 2, image=tk_img, tags=("node", node_self.id))
                        image_drawn = True

                except Exception as e:
                    print(f"Draw Error: {e}")
                    canvas.create_text(x + w/2, y + h/2, text="[FILE Error]", fill="red", tags=("node", node_self.id))

            # 2. Заголовок
            canvas.create_rectangle(x, y, x+w, y+header_height, fill='#9b59b6', outline="", tags=("node", node_self.id))
            canvas.create_text(x+10, y+12, text=f"🖼️ {node_self.title}", fill="white", anchor="w", font=("Segoe UI", 9, "bold"), tags=("node", node_self.id))

            # 3. Инфо-панель
            if image_drawn:
                info_bg_y = y + h - 25
                canvas.create_rectangle(x, info_bg_y, x+w, y+h, fill='#2c3e50', outline="", tags=("node", node_self.id))
                
                info_text = f"{mode.upper()}"
                if mode == 'sprite':
                    info_text += f" : {pos.upper()}"
                
                if anim.lower() != "none":
                    info_text += f" ({anim})"
                
                canvas.create_text(x + w/2, info_bg_y + 12, text=info_text, fill="#ecf0f1", font=("Segoe UI", 8, "bold"), justify="center", tags=("node", node_self.id))
            else:
                canvas.create_text(x + w/2, y + 60, text="[No Image]", fill="#aaa", tags=("node", node_self.id))
                canvas.create_text(x + w/2, y + 115, text=f"{mode.upper()}", fill="white", tags=("node", node_self.id))

            # 4. Порты (Визуальные точки)
            node_self.draw_input_port(canvas, x, y + h/2)
            node_self.draw_port(canvas, x+w, y + h/2, 0)

        def new_calculate_size(node_self):
            if node_self.node_type != 'media':
                self.original_calculate_size(node_self)
                return

            fixed_width = 180
            header_h = 25
            footer_h = 25

            node_self.width = fixed_width

            try:
                data = json.loads(node_self.content)
                path = data.get("image_path", "")
                
                if path and os.path.exists(path):
                    if HAS_PIL:
                        if path not in SIZE_CACHE:
                            with Image.open(path) as img:
                                SIZE_CACHE[path] = img.size
                        
                        orig_w, orig_h = SIZE_CACHE[path]
                        aspect = orig_h / orig_w
                        
                        img_display_h = int(fixed_width * aspect)
                        if img_display_h > 300: img_display_h = 300
                        
                        node_self.height = header_h + img_display_h + footer_h
                    else:
                        node_self.height = 200
                else:
                    node_self.height = 140
            except:
                node_self.height = 140

        def new_edit_node(editor_self, node):
            if node.node_type == 'media':
                MediaEditorDialog(editor_self, node, self.editor.redraw)
            else:
                self.original_edit_node(editor_self, node)

        # --- НОВЫЕ МЕТОДЫ ДЛЯ КООРДИНАТ СВЯЗЕЙ ---
        
        def new_get_input_pos(node_self):
            if node_self.node_type == 'media':
                # Центр порта входа по вертикали
                return node_self.x, node_self.y + node_self.height / 2
            
            if self.original_get_input_pos:
                return self.original_get_input_pos(node_self)
            return node_self.x, node_self.y

        def new_get_output_pos(node_self, index):
            if node_self.node_type == 'media':
                # Центр порта выхода по вертикали
                return node_self.x + node_self.width, node_self.y + node_self.height / 2
            
            if self.original_get_output_pos:
                return self.original_get_output_pos(node_self, index)
            return node_self.x + node_self.width, node_self.y

        # Применяем патчи
        self.NodeClass.draw = new_draw
        self.NodeClass.calculate_size = new_calculate_size
        self.EditorClass.edit_node = new_edit_node
        
        # Патчим методы получения координат, если они существуют в классе Node
        if self.original_get_input_pos:
            self.NodeClass.get_input_pos = new_get_input_pos
            print(f"[{self.name}] Patched get_input_pos")
            
        if self.original_get_output_pos:
            self.NodeClass.get_output_pos = new_get_output_pos
            print(f"[{self.name}] Patched get_output_pos")

        print(f"[{self.name}] Logic injected.")

    def add_toolbar_button(self, toolbar):
        # Если меню уже создано другим плагином, добавляемся туда, иначе создаем свое
        if not hasattr(self.editor, 'plugin_menu'):
            self.editor.plugin_menu_btn = tk.Menubutton(toolbar, text="🧩 Компоненты ▾", bg='#444', fg='white', 
                                                       relief='flat', font=('Segoe UI', 9, 'bold'), padx=10, pady=5)
            self.editor.plugin_menu_btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.editor.plugin_menu = tk.Menu(self.editor.plugin_menu_btn, tearoff=0, bg='#444', fg='white')
            self.editor.plugin_menu_btn["menu"] = self.editor.plugin_menu
        
        self.editor.plugin_menu.add_command(label="🖼️ Медиа блок", command=self.create_media_node)

    def create_media_node(self):
        default_data = {
            "image_path": "",
            "mode": "sprite",
            "position": "center",
            "animation": "none",
            "animation_duration": 0.5
        }
        self.editor.add_node(
            ntype='media',
            title="Media Event",
            content=json.dumps(default_data)
        )


class MediaEditorDialog:
    def __init__(self, parent, node, callback):
        self.node = node
        self.callback = callback
        
        try:
            self.data = json.loads(node.content)
        except:
            self.data = {
                "image_path": "", 
                "mode": "sprite", 
                "position": "center",
                "animation": "none",
                "animation_duration": 0.5
            }

        self.data.setdefault("image_path", "")
        self.data.setdefault("mode", "sprite")
        self.data.setdefault("position", "center")
        self.data.setdefault("animation", "none")
        self.data.setdefault("animation_duration", 0.5)

        self.win = tk.Toplevel(parent)
        self.win.title("Настройки Медиа")
        self.win.geometry("400x550")
        self.win.configure(bg='#2b2b2b')
        self.win.transient(parent)
        self.win.grab_set()

        lbl_style = {'bg': '#2b2b2b', 'fg': 'white', 'font': ('Segoe UI', 10)}
        
        tk.Label(self.win, text="Название сцены:", **lbl_style).pack(pady=5)
        self.e_title = tk.Entry(self.win, bg='#444', fg='white')
        self.e_title.insert(0, node.title)
        self.e_title.pack(fill=tk.X, padx=20)

        # --- Выбор файла ---
        tk.Label(self.win, text="Изображение:", **lbl_style).pack(pady=(15, 5))
        
        current_path = self.data.get("image_path", "")
        self.path_var = tk.StringVar(value=current_path if current_path else "Файл не выбран")
        
        self.lbl_path = tk.Label(self.win, textvariable=self.path_var, fg="#aaa", bg="#2b2b2b", wraplength=350, justify="center")
        self.lbl_path.pack(pady=2)
        
        tk.Button(self.win, text="📂 Обзор...", command=self.browse_file, bg='#8e44ad', fg='white').pack(pady=5)

        # --- Режим ---
        tk.Label(self.win, text="Тип отображения:", **lbl_style).pack(pady=(15, 5))
        
        self.var_mode = tk.StringVar(value=self.data["mode"])
        frame_mode = tk.Frame(self.win, bg='#2b2b2b')
        frame_mode.pack()
        
        r_style = {'bg': '#2b2b2b', 'fg': 'white', 'selectcolor': '#444', 'activebackground': '#2b2b2b', 'activeforeground': 'white'}
        
        tk.Radiobutton(frame_mode, text="Персонаж (Sprite)", variable=self.var_mode, value="sprite", command=self.update_ui_state, **r_style).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(frame_mode, text="Фон (Background)", variable=self.var_mode, value="background", command=self.update_ui_state, **r_style).pack(side=tk.LEFT, padx=10)

        # --- Позиция ---
        self.lbl_pos = tk.Label(self.win, text="Позиция спрайта:", **lbl_style)
        self.lbl_pos.pack(pady=(15, 5))
        
        self.var_pos = tk.StringVar(value=self.data["position"])
        self.frame_pos = tk.Frame(self.win, bg='#2b2b2b')
        self.frame_pos.pack()
        
        self.pos_radios = []
        for val, txt in [("left", "Слева"), ("center", "Центр"), ("right", "Справа")]:
            rb = tk.Radiobutton(self.frame_pos, text=txt, variable=self.var_pos, value=val, **r_style)
            rb.pack(side=tk.LEFT, padx=5)
            self.pos_radios.append(rb)

        # --- Анимация ---
        tk.Label(self.win, text="Анимация появления:", **lbl_style).pack(pady=(15, 5))
        
        transitions = [
            "none", "dissolve", "fade", "pixellate", 
            "move", "moveinright", "moveinleft", "moveintop", "moveinbottom",
            "moveoutright", "moveoutleft", "moveouttop", "moveoutbottom",
            "ease", "easeinright", "easeinleft", "easeintop", "easeinbottom",
            "easeoutright", "easeoutleft", "easeouttop", "easeoutbottom",
            "zoomin", "zoomout", "zoominout", 
            "vpunch", "hpunch", 
            "blinds", "squares", 
            "wipeleft", "wiperight", "wipeup", "wipedown",
            "slideleft", "slideright", "slideup", "slidedown",
            "slideawayleft", "slideawayright", "slideawayup", "slideawaydown",
            "pushright", "pushleft", "pushup", "pushdown",
            "irisin", "irisout"
        ]
        
        self.e_anim = ttk.Combobox(self.win, values=transitions)
        self.e_anim.set(self.data["animation"])
        self.e_anim.pack(fill=tk.X, padx=20)

        tk.Label(self.win, text="Длительность (сек):", **lbl_style).pack(pady=(5, 5))
        self.e_duration = tk.Entry(self.win, bg='#444', fg='white')
        self.e_duration.insert(0, str(self.data["animation_duration"]))
        self.e_duration.pack(fill=tk.X, padx=20)

        tk.Button(self.win, text="💾 Сохранить", command=self.save, bg='#27ae60', fg='white', width=20).pack(side=tk.BOTTOM, pady=20)

        self.update_ui_state()

    def update_ui_state(self):
        mode = self.var_mode.get()
        state = "normal" if mode == "sprite" else "disabled"
        color = "white" if mode == "sprite" else "#555"
        
        self.lbl_pos.config(fg=color)
        for rb in self.pos_radios:
            rb.config(state=state, fg=color if state == "normal" else "#555")

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[
            ("All Media", "*.png;*.jpg;*.jpeg;*.webp;*.mp4;*.webm;*.ogv;*.mkv"),
            ("Images", "*.png;*.jpg;*.jpeg;*.webp"), 
            ("Video", "*.mp4;*.webm;*.ogv;*.mkv"),
            ("All Files", "*.*")
        ])
        if path:
            path = path.replace("\\", "/") 
            self.data["image_path"] = path
            self.path_var.set(path)
            if path in SIZE_CACHE:
                del SIZE_CACHE[path]

    def save(self):
        self.node.title = self.e_title.get()
        self.data["mode"] = self.var_mode.get()
        self.data["position"] = self.var_pos.get()
        self.data["animation"] = self.e_anim.get()
        try:
            self.data["animation_duration"] = float(self.e_duration.get())
        except ValueError:
            self.data["animation_duration"] = 0.5
        
        self.node.content = json.dumps(self.data, ensure_ascii=False)
        self.node.calculate_size()
        self.callback()
        self.win.destroy()