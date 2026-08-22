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


def resolve_media_path(path, editor=None):
    """
    Разрешает относительный или абсолютный путь к медиа-файлу.
    Если путь относительный, ищет его относительно папки открытого проекта (current_file),
    затем относительно 'game/' подпапки, затем относительно cwd.
    """
    if not path:
        return ""

    path_norm = os.path.normpath(path)
    if os.path.exists(path_norm):
        return path_norm

    # Ищем относительно папки открытого проекта
    if editor and getattr(editor, 'current_file', None):
        proj_dir = os.path.dirname(editor.current_file)
        cand = os.path.normpath(os.path.join(proj_dir, path))
        if os.path.exists(cand):
            return cand

        cand_game = os.path.normpath(os.path.join(proj_dir, "game", path))
        if os.path.exists(cand_game):
            return cand_game

        cand_images = os.path.normpath(os.path.join(proj_dir, "images", path))
        if os.path.exists(cand_images):
            return cand_images

    # Ищем относительно cwd
    cand_cwd = os.path.normpath(os.path.join(os.getcwd(), path))
    if os.path.exists(cand_cwd):
        return cand_cwd

    return path


class MediaBlockPlugin(Plugin):
    name = "MediaBlock"
    version = "2.2"  # 2.2: relative path resolution & project-relative storage

    def __init__(self, editor):
        super().__init__(editor)
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

    # ------------------------------------------------------------------ #
    # on_enable вызывается РОВНО ОДИН РАЗ при загрузке плагина.           #
    # Все патчи классов должны быть здесь, НЕ в on_event!                 #
    # ------------------------------------------------------------------ #
    def on_enable(self):
        plugin_self = self  # захватываем ссылку для вложенных функций

        # --- Патч draw ---
        def new_draw(node_self, canvas):
            if node_self.node_type != 'media':
                plugin_self.original_draw(node_self, canvas)
                return

            x, y, w, h = node_self.x, node_self.y, node_self.width, node_self.height

            # Загрузка данных
            try:
                data = json.loads(node_self.content)
            except Exception:
                data = {}

            img_path = data.get("image_path", "")
            resolved_img_path = resolve_media_path(img_path, plugin_self.editor)
            mode = data.get("mode", "sprite")
            pos = data.get("position", "center")
            anim = data.get("animation", "none")

            # 1. Основной фон
            canvas.create_rectangle(
                x, y, x + w, y + h,
                fill='#4b2c5e', outline=plugin_self.COLORS.get('grid_bold', '#555'), width=2,
                tags=("node", node_self.id)
            )

            header_height = 25
            image_drawn = False

            if resolved_img_path and os.path.exists(resolved_img_path):
                ext = os.path.splitext(resolved_img_path)[1].lower()
                is_video = ext in ['.mp4', '.webm', '.mkv', '.ogv']

                try:
                    if is_video:
                        canvas.create_rectangle(
                            x + 10, y + header_height + 10, x + w - 10, y + h - 35,
                            fill='#2c3e50', outline="#ecf0f1", tags=("node", node_self.id)
                        )
                        canvas.create_text(
                            x + w / 2, y + h / 2,
                            text="VIDEO\n(Preview Unavailable)", fill="white",
                            justify="center", font=("Segoe UI", 9, "bold"),
                            tags=("node", node_self.id)
                        )
                        image_drawn = True
                    else:
                        target_w = int(w)
                        cache_key = f"{resolved_img_path}_{target_w}"

                        if cache_key not in IMAGE_CACHE:
                            # Всегда пробуем PIL первым — inline import обходит
                            # проблему HAS_PIL=False в динамически загруженном модуле
                            try:
                                from PIL import Image as _Image, ImageTk as _ImageTk
                                pil_img = _Image.open(resolved_img_path)
                                aspect = pil_img.height / pil_img.width
                                target_h = int(target_w * aspect)
                                if target_h > 300:
                                    target_h = 300
                                pil_img = pil_img.resize((target_w, target_h), _Image.Resampling.LANCZOS)
                                IMAGE_CACHE[cache_key] = _ImageTk.PhotoImage(pil_img)
                            except ImportError:
                                # PIL не установлен — tk.PhotoImage работает только для PNG/GIF
                                ext_lower = os.path.splitext(resolved_img_path)[1].lower()
                                if ext_lower in ('.png', '.gif'):
                                    img = tk.PhotoImage(file=resolved_img_path)
                                    if img.width() > target_w:
                                        factor = max(1, int(img.width() / target_w))
                                        img = img.subsample(factor, factor)
                                    IMAGE_CACHE[cache_key] = img
                                else:
                                    raise RuntimeError(
                                        f"Pillow not installed — JPG/WebP not supported. "
                                        f"Run: pip install pillow"
                                    )

                        tk_img = IMAGE_CACHE[cache_key]
                        img_h = tk_img.height()

                        # Держим жёсткую ссылку — иначе GC уничтожит PhotoImage
                        if not hasattr(canvas, '_media_image_refs'):
                            canvas._media_image_refs = []
                        canvas._media_image_refs.append(tk_img)

                        canvas.create_image(
                            x + target_w / 2, y + header_height + img_h / 2,
                            image=tk_img, tags=("node", node_self.id)
                        )
                        image_drawn = True

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[MediaBlock] Draw Error: {e}")
                    canvas.create_text(
                        x + w / 2, y + h / 2,
                        text="[FILE Error]", fill="red", tags=("node", node_self.id)
                    )

            # 2. Заголовок
            canvas.create_rectangle(
                x, y, x + w, y + header_height,
                fill='#9b59b6', outline="", tags=("node", node_self.id)
            )
            canvas.create_text(
                x + 10, y + 12,
                text=f"[IMG] {node_self.title}", fill="white", anchor="w",
                font=("Segoe UI", 9, "bold"), tags=("node", node_self.id)
            )

            # 3. Инфо-панель
            if image_drawn:
                info_bg_y = y + h - 25
                canvas.create_rectangle(
                    x, info_bg_y, x + w, y + h,
                    fill='#2c3e50', outline="", tags=("node", node_self.id)
                )
                info_text = f"{mode.upper()}"
                if mode == 'sprite':
                    info_text += f" : {pos.upper()}"
                if anim.lower() != "none":
                    info_text += f" ({anim})"
                canvas.create_text(
                    x + w / 2, info_bg_y + 12,
                    text=info_text, fill="#ecf0f1",
                    font=("Segoe UI", 8, "bold"), justify="center",
                    tags=("node", node_self.id)
                )
            else:
                canvas.create_text(
                    x + w / 2, y + 60,
                    text="[No Image]", fill="#aaa", tags=("node", node_self.id)
                )
                canvas.create_text(
                    x + w / 2, y + 115,
                    text=f"{mode.upper()}", fill="white", tags=("node", node_self.id)
                )

            # 4. Порты
            node_self.draw_input_port(canvas, x, y + h / 2)
            node_self.draw_port(canvas, x + w, y + h / 2, 0)

        # --- Патч calculate_size ---
        def new_calculate_size(node_self):
            if node_self.node_type != 'media':
                plugin_self.original_calculate_size(node_self)
                return

            fixed_width = 180
            header_h = 25
            footer_h = 25

            node_self.width = fixed_width

            try:
                data = json.loads(node_self.content)
                path = data.get("image_path", "")
                resolved_path = resolve_media_path(path, plugin_self.editor)

                if resolved_path and os.path.exists(resolved_path):
                    if HAS_PIL:
                        if resolved_path not in SIZE_CACHE:
                            with Image.open(resolved_path) as img:
                                SIZE_CACHE[resolved_path] = img.size
                        orig_w, orig_h = SIZE_CACHE[resolved_path]
                        aspect = orig_h / orig_w
                        img_display_h = int(fixed_width * aspect)
                        if img_display_h > 300:
                            img_display_h = 300
                        node_self.height = header_h + img_display_h + footer_h
                    else:
                        node_self.height = 200
                else:
                    node_self.height = 140
            except Exception:
                node_self.height = 140

        # --- Патч edit_node ---
        def new_edit_node(editor_self, node):
            if node.node_type == 'media':
                MediaEditorDialog(editor_self, node, plugin_self.editor.redraw, editor=plugin_self.editor)
            else:
                plugin_self.original_edit_node(editor_self, node)

        # --- Патчи координат портов ---
        def new_get_input_pos(node_self):
            if node_self.node_type == 'media':
                return node_self.x, node_self.y + node_self.height / 2
            if plugin_self.original_get_input_pos:
                return plugin_self.original_get_input_pos(node_self)
            return node_self.x, node_self.y

        def new_get_output_pos(node_self, index):
            if node_self.node_type == 'media':
                return node_self.x + node_self.width, node_self.y + node_self.height / 2
            if plugin_self.original_get_output_pos:
                return plugin_self.original_get_output_pos(node_self, index)
            return node_self.x + node_self.width, node_self.y

        # Применяем патчи (ровно один раз)
        self.NodeClass.draw = new_draw
        self.NodeClass.calculate_size = new_calculate_size
        self.EditorClass.edit_node = new_edit_node

        if self.original_get_input_pos:
            self.NodeClass.get_input_pos = new_get_input_pos
            print(f"[{self.name}] Patched get_input_pos")

        if self.original_get_output_pos:
            self.NodeClass.get_output_pos = new_get_output_pos
            print(f"[{self.name}] Patched get_output_pos")

        print(f"[{self.name}] Logic injected (v{self.version}).")

    def on_event(self, event_type, data=None):
        # Только UI-кнопка — всё остальное НЕ должно быть здесь
        if event_type == 'setup_ui':
            self.add_toolbar_button(data)

    def add_toolbar_button(self, toolbar):
        if not hasattr(self.editor, 'plugin_menu'):
            self.editor.plugin_menu_btn = tk.Menubutton(
                toolbar, text="Components", bg='#444', fg='white',
                relief='flat', font=('Segoe UI', 9, 'bold'), padx=10, pady=5
            )
            self.editor.plugin_menu_btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.editor.plugin_menu = tk.Menu(
                self.editor.plugin_menu_btn, tearoff=0, bg='#444', fg='white'
            )
            self.editor.plugin_menu_btn["menu"] = self.editor.plugin_menu

        self.editor.plugin_menu.add_command(label="[IMG] Media Block", command=self.create_media_node)

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
    def __init__(self, parent, node, callback, editor=None):
        self.parent = parent
        self.node = node
        self.callback = callback
        self.editor = editor

        try:
            self.data = json.loads(node.content)
        except Exception:
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
        self.win.title("Media Settings")
        self.win.geometry("400x550")
        self.win.configure(bg='#2b2b2b')
        self.win.transient(parent)
        self.win.grab_set()

        lbl_style = {'bg': '#2b2b2b', 'fg': 'white', 'font': ('Segoe UI', 10)}

        tk.Label(self.win, text="Scene name:", **lbl_style).pack(pady=5)
        self.e_title = tk.Entry(self.win, bg='#444', fg='white')
        self.e_title.insert(0, node.title)
        self.e_title.pack(fill=tk.X, padx=20)

        # --- Выбор файла ---
        tk.Label(self.win, text="Image / Video file:", **lbl_style).pack(pady=(15, 5))

        current_path = self.data.get("image_path", "")
        self.path_var = tk.StringVar(value=current_path if current_path else "No file selected")

        self.lbl_path = tk.Label(
            self.win, textvariable=self.path_var,
            fg="#aaa", bg="#2b2b2b", wraplength=350, justify="center"
        )
        self.lbl_path.pack(pady=2)

        tk.Button(self.win, text="Browse...", command=self.browse_file,
                  bg='#8e44ad', fg='white').pack(pady=5)

        # --- Режим ---
        tk.Label(self.win, text="Display type:", **lbl_style).pack(pady=(15, 5))

        self.var_mode = tk.StringVar(value=self.data["mode"])
        frame_mode = tk.Frame(self.win, bg='#2b2b2b')
        frame_mode.pack()

        r_style = {
            'bg': '#2b2b2b', 'fg': 'white', 'selectcolor': '#444',
            'activebackground': '#2b2b2b', 'activeforeground': 'white'
        }

        tk.Radiobutton(frame_mode, text="Character (Sprite)", variable=self.var_mode,
                       value="sprite", command=self.update_ui_state, **r_style).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(frame_mode, text="Background", variable=self.var_mode,
                       value="background", command=self.update_ui_state, **r_style).pack(side=tk.LEFT, padx=10)

        # --- Позиция ---
        self.lbl_pos = tk.Label(self.win, text="Sprite position:", **lbl_style)
        self.lbl_pos.pack(pady=(15, 5))

        self.var_pos = tk.StringVar(value=self.data["position"])
        self.frame_pos = tk.Frame(self.win, bg='#2b2b2b')
        self.frame_pos.pack()

        self.pos_radios = []
        for val, txt in [("left", "Left"), ("center", "Center"), ("right", "Right")]:
            rb = tk.Radiobutton(self.frame_pos, text=txt, variable=self.var_pos, value=val, **r_style)
            rb.pack(side=tk.LEFT, padx=5)
            self.pos_radios.append(rb)

        # --- Анимация ---
        tk.Label(self.win, text="Transition animation:", **lbl_style).pack(pady=(15, 5))

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

        tk.Label(self.win, text="Duration (sec):", **lbl_style).pack(pady=(5, 5))
        self.e_duration = tk.Entry(self.win, bg='#444', fg='white')
        self.e_duration.insert(0, str(self.data["animation_duration"]))
        self.e_duration.pack(fill=tk.X, padx=20)

        tk.Button(self.win, text="Save", command=self.save,
                  bg='#27ae60', fg='white', width=20).pack(side=tk.BOTTOM, pady=20)

        self.update_ui_state()

    def update_ui_state(self):
        mode = self.var_mode.get()
        state = "normal" if mode == "sprite" else "disabled"
        color = "white" if mode == "sprite" else "#555"

        self.lbl_pos.config(fg=color)
        for rb in self.pos_radios:
            rb.config(state=state, fg=color if state == "normal" else "#555")

    def browse_file(self):
        init_dir = None
        if self.editor and getattr(self.editor, 'current_file', None):
            init_dir = os.path.dirname(self.editor.current_file)

        path = filedialog.askopenfilename(
            initialdir=init_dir,
            filetypes=[
                ("All Media", "*.png;*.jpg;*.jpeg;*.webp;*.mp4;*.webm;*.ogv;*.mkv"),
                ("Images", "*.png;*.jpg;*.jpeg;*.webp"),
                ("Video", "*.mp4;*.webm;*.ogv;*.mkv"),
                ("All Files", "*.*")
            ]
        )
        if path:
            path = path.replace("\\", "/")

            # Инвалидируем кэш СТАРОГО пути перед сменой
            old_path = self.data.get("image_path", "")
            if old_path:
                resolved_old = resolve_media_path(old_path, self.editor)
                if old_path in SIZE_CACHE:
                    del SIZE_CACHE[old_path]
                if resolved_old in SIZE_CACHE:
                    del SIZE_CACHE[resolved_old]
                old_keys = [k for k in IMAGE_CACHE if k.startswith(old_path + "_") or k.startswith(resolved_old + "_")]
                for k in old_keys:
                    del IMAGE_CACHE[k]

            # Преобразуем путь в относительный, если файл внутри папки проекта
            if self.editor and getattr(self.editor, 'current_file', None):
                proj_dir = os.path.dirname(self.editor.current_file).replace("\\", "/")
                try:
                    rel = os.path.relpath(path, proj_dir).replace("\\", "/")
                    if not rel.startswith(".."):
                        path = rel
                except ValueError:
                    pass

            self.data["image_path"] = path
            self.path_var.set(path)

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