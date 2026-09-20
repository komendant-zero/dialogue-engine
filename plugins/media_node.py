import tkinter as tk
from tkinter import filedialog, ttk
from plugin_system import Plugin
import json
import os
import sys
import time

# Попытка импорта PIL (Pillow) для поддержки JPG и качественного ресайза
try:
    from PIL import Image, ImageTk, ImageSequence
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[MediaBlock] Warning: 'pillow' library not found. JPG support is disabled.")

# Глобальный кэш изображений (хранит {path: ImageTk/PhotoImage})
IMAGE_CACHE = {}
# Кэш анимаций кадров (хранит {cache_key: {"frames": [tk_img, ...], "durations": [ms, ...]}})
ANIM_CACHE = {}
# Кэш размеров изображений для calculate_size (хранит {path: (width, height)})
SIZE_CACHE = {}


def load_media_frames(resolved_img_path, target_w):
    """
    Загружает кадры и длительности для изображения (включая анимированные GIF).
    Возвращает (frames, durations), где:
      - frames: список PhotoImage / ImageTk.PhotoImage
      - durations: список задержек в миллисекундах для каждого кадра
    Для статичных картинок возвращает ([photo_img], [0]).
    """
    ext_lower = os.path.splitext(resolved_img_path)[1].lower()

    if HAS_PIL:
        try:
            from PIL import Image as _Image, ImageTk as _ImageTk, ImageSequence as _ImageSequence
            with _Image.open(resolved_img_path) as pil_img:
                orig_w, orig_h = pil_img.size
                aspect = (orig_h / orig_w) if orig_w > 0 else 1.0
                target_h = max(1, int(target_w * aspect))
                if target_h > 300:
                    target_h = 300

                is_animated = getattr(pil_img, 'is_animated', False) and getattr(pil_img, 'n_frames', 1) > 1
                if is_animated:
                    frames = []
                    durations = []
                    for frame in _ImageSequence.Iterator(pil_img):
                        dur = frame.info.get('duration', 100)
                        if not dur or dur < 20:
                            dur = 100
                        f_rgba = frame.convert('RGBA')
                        f_resized = f_rgba.resize((target_w, target_h), _Image.Resampling.LANCZOS)
                        frames.append(_ImageTk.PhotoImage(f_resized))
                        durations.append(int(dur))
                    if frames:
                        return frames, durations

                # Статичное изображение через PIL
                f_resized = pil_img.convert('RGBA').resize((target_w, target_h), _Image.Resampling.LANCZOS)
                return [_ImageTk.PhotoImage(f_resized)], [0]
        except Exception as e:
            print(f"[MediaBlock] PIL load error for {resolved_img_path}: {e}")

    # Fallback без PIL (tk.PhotoImage)
    if ext_lower == '.gif':
        frames = []
        idx = 0
        while True:
            try:
                img = tk.PhotoImage(file=resolved_img_path, format=f'gif -index {idx}')
                if img.width() > target_w:
                    factor = max(1, int(img.width() / target_w))
                    img = img.subsample(factor, factor)
                frames.append(img)
                idx += 1
            except tk.TclError:
                break
        if frames:
            return frames, [100] * len(frames)

    if ext_lower in ('.png', '.gif'):
        img = tk.PhotoImage(file=resolved_img_path)
        if img.width() > target_w:
            factor = max(1, int(img.width() / target_w))
            img = img.subsample(factor, factor)
        return [img], [0]

    raise RuntimeError(
        f"Pillow not installed or failed to load — format {ext_lower} not supported. "
        f"Run: pip install pillow"
    )


def resolve_media_path(path, editor=None):
    """
    Разрешает относительный или абсолютный путь к медиа-файлу.
    Если путь относительный, ищет его относительно папки открытого проекта (current_file),
    затем относительно 'game/' подпапки, затем относительно cwd.
    Если путь абсолютный, но файл не найден (например, проект перенесен на другой ПК),
    пытается найти файл по подпутям ('game/...', 'bg/...', 'images/...') или имени файла.
    """
    if not path:
        return ""

    path_norm = os.path.normpath(path)
    if os.path.exists(path_norm):
        return path_norm

    search_dirs = []
    if editor and getattr(editor, 'current_file', None):
        proj_dir = os.path.dirname(os.path.abspath(editor.current_file))
        search_dirs.append(proj_dir)
        search_dirs.append(os.path.join(proj_dir, "game"))
        search_dirs.append(os.path.join(proj_dir, "images"))
        search_dirs.append(os.path.join(proj_dir, "bg"))
    
    cwd = os.path.abspath(os.getcwd())
    if cwd not in search_dirs:
        search_dirs.append(cwd)
        search_dirs.append(os.path.join(cwd, "game"))
        search_dirs.append(os.path.join(cwd, "images"))
        search_dirs.append(os.path.join(cwd, "bg"))

    # Относительные кандидаты
    candidates = []
    # 1. Если путь уже относительный
    if not os.path.isabs(path):
        candidates.append(path)

    # 2. Извлекаем подпути после типовых папок (game/, bg/, images/)
    path_fwd = path.replace('\\', '/')
    for marker in ['/game/', '/images/', '/bg/']:
        if marker in path_fwd.lower():
            idx = path_fwd.lower().find(marker)
            sub = path_fwd[idx + len(marker):]
            marker_name = marker.strip('/')
            candidates.append(f"{marker_name}/{sub}")
            candidates.append(sub)

    # 3. Просто имя файла
    basename = os.path.basename(path)
    if basename:
        candidates.append(basename)
        candidates.append(f"bg/{basename}")
        candidates.append(f"images/{basename}")
        candidates.append(f"game/bg/{basename}")
        candidates.append(f"game/images/{basename}")

    for s_dir in search_dirs:
        for cand in candidates:
            full = os.path.normpath(os.path.join(s_dir, cand))
            if os.path.exists(full):
                return full

    return path


class MediaBlockPlugin(Plugin):
    name = "MediaBlock"
    version = "2.3"  # 2.3: animated GIF preview in editor

    def __init__(self, editor):
        super().__init__(editor)
        self.animated_nodes = {}
        self._anim_timer_id = None
        self._anim_loop_running = False
        main_module = sys.modules.get('__main__')
        if not hasattr(main_module, 'Node'):
            main_module = sys.modules.get('main', main_module)
        self.NodeClass = getattr(main_module, 'Node', None)
        self.EditorClass = getattr(main_module, 'ScenarioEditor', None)
        self.COLORS = getattr(main_module, 'COLORS', {})

        if self.NodeClass:
            self.original_draw = self.NodeClass.draw
            self.original_calculate_size = self.NodeClass.calculate_size
            self.original_get_input_pos = getattr(self.NodeClass, 'get_input_pos', None)
            self.original_get_output_pos = getattr(self.NodeClass, 'get_output_pos', None)
        if self.EditorClass:
            self.original_edit_node = getattr(self.EditorClass, 'edit_node', None)

    def ensure_anim_loop(self):
        if not self._anim_loop_running:
            self._anim_loop_running = True
            if hasattr(self, 'editor') and hasattr(self.editor, 'after'):
                self._anim_timer_id = self.editor.after(30, self._anim_tick)

    def _anim_tick(self):
        self._anim_timer_id = None
        if not hasattr(self, 'editor') or not getattr(self.editor, 'canvas', None):
            self._anim_loop_running = False
            return

        canvas = self.editor.canvas
        try:
            if not canvas.winfo_exists():
                self._anim_loop_running = False
                return
        except Exception:
            self._anim_loop_running = False
            return

        now = time.time()
        existing_nodes = getattr(self.editor, 'nodes', [])
        existing_node_ids = {n.id for n in existing_nodes}

        to_remove = []
        for node_id, state in list(self.animated_nodes.items()):
            if node_id not in existing_node_ids:
                to_remove.append(node_id)
                continue

            cache_key = state.get("cache_key")
            anim_data = ANIM_CACHE.get(cache_key)
            if not anim_data or len(anim_data.get("frames", [])) <= 1:
                to_remove.append(node_id)
                continue

            frames = anim_data["frames"]
            durations = anim_data["durations"]

            if now >= state.get("next_time", 0):
                new_idx = (state["frame_idx"] + 1) % len(frames)
                state["frame_idx"] = new_idx
                dur = durations[new_idx] if new_idx < len(durations) else 100
                state["next_time"] = now + (dur / 1000.0)

                img_tag = f"media_img_{node_id}"
                new_img = frames[new_idx]
                try:
                    canvas.itemconfig(img_tag, image=new_img)
                except Exception:
                    pass

        for nid in to_remove:
            self.animated_nodes.pop(nid, None)

        if self.animated_nodes:
            self._anim_loop_running = True
            if hasattr(self, 'editor') and hasattr(self.editor, 'after'):
                self._anim_timer_id = self.editor.after(30, self._anim_tick)
        else:
            self._anim_loop_running = False

    def on_disable(self):
        if self._anim_timer_id and hasattr(self, 'editor') and hasattr(self.editor, 'after_cancel'):
            try:
                self.editor.after_cancel(self._anim_timer_id)
            except Exception:
                pass
        self._anim_timer_id = None
        self._anim_loop_running = False
        self.animated_nodes.clear()

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

                        if cache_key not in ANIM_CACHE:
                            frames, durations = load_media_frames(resolved_img_path, target_w)
                            ANIM_CACHE[cache_key] = {"frames": frames, "durations": durations}
                            IMAGE_CACHE[cache_key] = frames[0]

                        anim_data = ANIM_CACHE[cache_key]
                        frames = anim_data.get("frames", [])
                        durations = anim_data.get("durations", [])

                        if frames:
                            if len(frames) > 1:
                                node_state = plugin_self.animated_nodes.get(node_self.id)
                                if node_state and node_state.get("cache_key") == cache_key:
                                    current_idx = node_state["frame_idx"] % len(frames)
                                else:
                                    current_idx = 0
                                    dur0 = durations[0] if durations else 100
                                    plugin_self.animated_nodes[node_self.id] = {
                                        "cache_key": cache_key,
                                        "frame_idx": 0,
                                        "next_time": time.time() + (dur0 / 1000.0)
                                    }
                                tk_img = frames[current_idx]
                                plugin_self.ensure_anim_loop()
                            else:
                                plugin_self.animated_nodes.pop(node_self.id, None)
                                tk_img = frames[0]

                            img_h = tk_img.height()

                            # Держим жёсткую ссылку — иначе GC уничтожит PhotoImage
                            if not hasattr(canvas, '_media_image_refs'):
                                canvas._media_image_refs = []
                            canvas._media_image_refs.append(tk_img)

                            img_tag = f"media_img_{node_self.id}"
                            canvas.create_image(
                                x + target_w / 2, y + header_height + img_h / 2,
                                image=tk_img, tags=("node", node_self.id, img_tag)
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
            is_gif = (os.path.splitext(resolved_img_path)[1].lower() == '.gif') if resolved_img_path else False
            header_prefix = "[GIF]" if is_gif else "[IMG]"
            canvas.create_text(
                x + 10, y + 12,
                text=f"{header_prefix} {node_self.title}", fill="white", anchor="w",
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

        if getattr(self, 'original_get_input_pos', None):
            self.NodeClass.get_input_pos = new_get_input_pos
            print(f"[{self.name}] Patched get_input_pos")

        if getattr(self, 'original_get_output_pos', None):
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
                ("All Media", "*.png;*.jpg;*.jpeg;*.webp;*.gif;*.bmp;*.mp4;*.webm;*.ogv;*.mkv"),
                ("Images", "*.png;*.jpg;*.jpeg;*.webp;*.gif;*.bmp"),
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
                old_anim_keys = [k for k in ANIM_CACHE if k.startswith(old_path + "_") or k.startswith(resolved_old + "_")]
                for k in old_anim_keys:
                    del ANIM_CACHE[k]

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