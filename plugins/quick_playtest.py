import tkinter as tk
from tkinter import messagebox
from plugin_system import Plugin

class QuickPlaytestPlugin(Plugin):
    name = "Quick Playtest (In-Editor)"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            parent = getattr(self.editor, 'toolbar_right', data)
            tk.Button(
                parent,
                text="▶ Быстрый тест",
                command=self.start_playtest,
                bg='#27ae60',
                activebackground='#2ecc71',
                fg='white',
                activeforeground='white',
                relief='flat',
                font=('Segoe UI', 9, 'bold'),
                padx=8,
                pady=3,
                cursor='hand2'
            ).pack(side=tk.RIGHT, padx=3)

    def start_playtest(self):
        nodes = self.editor.nodes
        connections = self.editor.connections

        if not nodes:
            messagebox.showinfo("Быстрый тест", "Холст пуст! Добавьте ноды для тестирования.", parent=self.editor)
            return

        # Стартовая нода: если выбрана одна нода - начинаем с неё, иначе ищем 'start'
        start_node = None
        if len(self.editor.selected_nodes) == 1:
            start_node = self.editor.selected_nodes[0]
        else:
            start_node = next((n for n in nodes if n.title.lower().strip() == 'start'), None)
            if not start_node:
                # Нода без входящих
                incoming = {c['to'] for c in connections}
                zero_in = [n for n in nodes if n.id not in incoming]
                start_node = zero_in[0] if zero_in else nodes[0]

        runner = PlaytestWindow(self.editor, start_node, nodes, connections)

class PlaytestWindow(tk.Toplevel):
    def __init__(self, editor, start_node, nodes, connections):
        super().__init__(editor)
        self.editor = editor
        self.nodes = nodes
        self.connections = connections
        self.current_node = start_node
        self.state_vars = {}

        self.title("▶ Быстрый тест сценария")
        self.geometry("700x520")
        self.minsize(500, 400)
        self.configure(bg='#181818')
        self.transient(editor)

        self.setup_ui()
        self.bind("<space>", lambda e: self.advance())
        self.bind("<Return>", lambda e: self.advance())

        self.render_current_node()

    def setup_ui(self):
        # Верхняя панель: статус и навигация
        self.top_bar = tk.Frame(self, bg='#222222', height=36, padx=10)
        self.top_bar.pack(side=tk.TOP, fill=tk.X)

        self.lbl_node_info = tk.Label(self.top_bar, text="", bg='#222222', fg='#888888', font=("Segoe UI", 9))
        self.lbl_node_info.pack(side=tk.LEFT, pady=6)

        btn_restart = tk.Button(self.top_bar, text="🔄 Заново", command=self.restart, 
                                bg='#333333', fg='white', relief='flat', font=("Segoe UI", 8), padx=6, pady=2)
        btn_restart.pack(side=tk.RIGHT, pady=4)

        # Переменные / Лог состояния (сворачиваемый статус)
        self.var_bar = tk.Label(self, text="Переменные: {}", bg='#1a1a1a', fg='#666666', font=("Consolas", 8), anchor='w', padx=10)
        self.var_bar.pack(side=tk.TOP, fill=tk.X)

        # Основная сцена (текстовое поле / фон)
        self.scene_frame = tk.Frame(self, bg='#181818', padx=25, pady=20)
        self.scene_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Имя говорящего
        self.lbl_speaker = tk.Label(self.scene_frame, text="", bg='#181818', fg='#5dade2', font=("Segoe UI", 13, "bold"), anchor='w')
        self.lbl_speaker.pack(fill=tk.X, pady=(0, 8))

        # Текст диалога
        self.lbl_dialogue = tk.Label(self.scene_frame, text="", bg='#252526', fg='#e0e0e0', font=("Segoe UI", 11), 
                                     wraplength=640, justify='left', anchor='nw', padx=18, pady=16, relief='flat')
        self.lbl_dialogue.pack(fill=tk.BOTH, expand=True)

        # Нижняя панель: Кнопки выбора или кнопка "Далее"
        self.bottom_frame = tk.Frame(self, bg='#181818', padx=25, pady=15)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

    def update_var_bar(self):
        txt = ", ".join(f"{k} = {repr(v)}" for k, v in self.state_vars.items())
        self.var_bar.config(text=f"Переменные: {{ {txt} }}" if txt else "Переменные: пустой пул")

    def render_current_node(self):
        # Очищаем кнопки в нижней панели
        for child in self.bottom_frame.winfo_children():
            child.destroy()

        if not self.current_node:
            self.show_ended()
            return

        node = self.current_node
        self.lbl_node_info.config(text=f"Узел: {node.title} [{node.node_type}]")

        # Обработка разных типов узлов:
        if node.node_type == 'variable' or node.node_type == 'python_code':
            # Выполняем скрипт в state_vars
            self.execute_code(node.content)
            self.update_var_bar()
            # Автоматически переходим дальше
            self.jump_to_next(0)
            return

        elif node.node_type == 'condition':
            # Вычисляем условие
            cond_res = self.evaluate_condition(node.content)
            target_idx = 0 if cond_res else 1
            self.jump_to_next(target_idx)
            return

        elif node.node_type == 'music':
            mode = node.custom_data.get('music_mode', 'bg')
            mode_names = {'bg': 'Фоновая музыка (Loop)', 'sfx': 'Звуковой эффект (SFX)', 'voice': 'Озвучка (Voice)'}
            mode_label = mode_names.get(mode, mode.upper())
            file_path = node.custom_data.get('music_file', '')
            self.lbl_speaker.config(text=f"🎵 Аудио ({mode_label})")
            file_name = file_path if file_path else "[Файл не выбран]"
            self.lbl_dialogue.config(text=f"Режим: {mode_label}\nФайл: {file_name}")
            self.show_next_button(0)

        elif node.node_type == 'media':
            self.lbl_speaker.config(text="🖼️ Медиа (Фон / Спрайт)")
            try:
                import json
                mdata = json.loads(node.content)
                img_path = mdata.get("image_path", "")
                mode = mdata.get("mode", "sprite")
                anim = mdata.get("animation", "none")
                dur = mdata.get("animation_duration", 0.5)
                desc = f"Тип: {mode.upper()}\nФайл: {img_path or '[Без файла]'}"
                if anim != 'none':
                    desc += f"\nПереход: {anim} ({dur} сек)"
                self.lbl_dialogue.config(text=desc)
            except Exception:
                self.lbl_dialogue.config(text=f"Медиа-узел: {node.content}")
            self.show_next_button(0)

        elif node.node_type == 'animation':
            self.lbl_speaker.config(text="✨ Анимация / Переход экрана")
            try:
                import json
                adata = json.loads(node.content)
                anim = adata.get("animation", "fade")
                dur = adata.get("duration", 0.5)
                target = adata.get("target", "screen")
                self.lbl_dialogue.config(text=f"Переход: {anim}\nЦель: {target}\nДлительность: {dur} сек")
            except Exception:
                self.lbl_dialogue.config(text=f"Анимация: {node.content}")
            self.show_next_button(0)

        elif node.node_type == 'choice':
            speaker = node.title if not node.title.startswith('#') else ""
            self.lbl_speaker.config(text=speaker)
            self.lbl_dialogue.config(text="Сделайте выбор:")

            options = [opt for opt in node.content.split('\n') if opt.strip()]
            for idx, opt in enumerate(options):
                btn = tk.Button(
                    self.bottom_frame,
                    text=f"▸ {opt}",
                    command=lambda i=idx: self.jump_to_next(i),
                    bg='#2c3e50',
                    activebackground='#34495e',
                    fg='white',
                    font=("Segoe UI", 10),
                    relief='flat',
                    padx=12,
                    pady=6,
                    cursor='hand2'
                )
                btn.pack(fill=tk.X, pady=3)

        else: # story или любой другой текстовый узел
            speaker = node.title if not node.title.startswith('#') else ""
            self.lbl_speaker.config(text=speaker)
            display_text = node._get_display_text(node.content)
            self.lbl_dialogue.config(text=display_text)
            self.show_next_button(0)

    def show_next_button(self, out_idx):
        btn_next = tk.Button(
            self.bottom_frame,
            text="Далее ▸ (Пробел / Enter)",
            command=lambda: self.jump_to_next(out_idx),
            bg='#007acc',
            activebackground='#0098ff',
            fg='white',
            font=("Segoe UI", 10, "bold"),
            relief='flat',
            padx=16,
            pady=8,
            cursor='hand2'
        )
        btn_next.pack(side=tk.RIGHT)

    def advance(self):
        # Если есть кнопка "Далее" - нажимаем её
        if self.bottom_frame.winfo_children():
            for child in self.bottom_frame.winfo_children():
                if isinstance(child, tk.Button) and "Далее" in child.cget("text"):
                    child.invoke()
                    return

    def jump_to_next(self, out_idx):
        if not self.current_node:
            return

        conn = next((c for c in self.connections if c['from'] == self.current_node.id and c['out_idx'] == out_idx), None)
        if conn:
            target_node = next((n for n in self.nodes if n.id == conn['to']), None)
            self.current_node = target_node
            self.render_current_node()
        else:
            prev_node = self.current_node
            self.current_node = None
            if prev_node and prev_node.node_type == 'choice':
                self.show_ended(reason="⚠️ Выбранный вариант не имеет следующего узла (ветка не достроена на холсте).")
            else:
                self.show_ended()

    def show_ended(self, reason=None):
        self.lbl_speaker.config(text="🏁 Конец сценария")
        msg = reason or "Сюжетная линия дошла до финала. Нет следующих связей."
        self.lbl_dialogue.config(text=msg)
        for child in self.bottom_frame.winfo_children():
            child.destroy()
        tk.Button(self.bottom_frame, text="Закрыть", command=self.destroy, 
                  bg='#333333', fg='white', relief='flat', padx=15, pady=6).pack(side=tk.RIGHT)
        tk.Button(self.bottom_frame, text="🔄 Начать заново", command=self.restart, 
                  bg='#27ae60', fg='white', relief='flat', padx=15, pady=6).pack(side=tk.LEFT)

    def restart(self):
        self.state_vars.clear()
        self.update_var_bar()
        start_node = next((n for n in self.nodes if n.title.lower().strip() == 'start'), self.nodes[0] if self.nodes else None)
        self.current_node = start_node
        self.render_current_node()

    def execute_code(self, code_text):
        for line in code_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                # Безопасное присвоение переменных a = b или a += b
                if '=' in line:
                    parts = line.split('=', 1)
                    var_name = parts[0].strip().rstrip('+').rstrip('-').rstrip('*').rstrip('/')
                    op = '='
                    if '+=' in line: op = '+='
                    elif '-=' in line: op = '-='
                    
                    val = eval(parts[1].strip(), {}, dict(self.state_vars))
                    if op == '+=':
                        self.state_vars[var_name] = self.state_vars.get(var_name, 0) + val
                    elif op == '-=':
                        self.state_vars[var_name] = self.state_vars.get(var_name, 0) - val
                    else:
                        self.state_vars[var_name] = val
                else:
                    eval(line, {}, self.state_vars)
            except Exception as e:
                print(f"[Playtest] Error executing line '{line}': {e}")

    def evaluate_condition(self, expr):
        expr = expr.strip()
        if not expr:
            return True
        try:
            return bool(eval(expr, {}, dict(self.state_vars)))
        except Exception as e:
            print(f"[Playtest] Condition eval failed for '{expr}': {e}")
            return False
