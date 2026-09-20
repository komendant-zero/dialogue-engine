import tkinter as tk
from plugin_system import Plugin

class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tip_window = None
        self.text = ""
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def set_text(self, text):
        self.text = text
        if self.tip_window:
            for child in self.tip_window.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(text=self.text)

    def show_tip(self, event=None):
        if not self.text or self.tip_window:
            return
        try:
            x = self.widget.winfo_rootx() + 5
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)
            label = tk.Label(
                tw,
                text=self.text,
                justify=tk.LEFT,
                background="#1e1e1e",
                foreground="#e0e0e0",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 8),
                padx=8,
                pady=5
            )
            label.pack()
        except Exception:
            pass

    def hide_tip(self, event=None):
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


class WordCountPlugin(Plugin):
    name = "Word Counter"
    version = "1.2"

    def __init__(self, editor):
        super().__init__(editor)
        self.label = None
        self.tooltip = None
        self.running = True
        self.show_only_story = False  # По умолчанию показывает все слова, клик переключает на только сюжет/текст

    def on_enable(self):
        self.update_loop()

    def on_event(self, event_type, data):
        if event_type == 'setup_ui':
            parent = getattr(self.editor, 'toolbar_right', data)
            tk.Label(parent, text="|", bg='#1e1e1e', fg='#555555').pack(side=tk.RIGHT, padx=4)
            self.label = tk.Label(
                parent, 
                text="Слов: 0", 
                bg='#282828', 
                fg='#2ecc71',
                padx=6,
                pady=2,
                relief='flat',
                font=("Segoe UI", 9, "bold"),
                cursor='hand2'
            )
            self.label.pack(side=tk.RIGHT, padx=4)
            self.tooltip = Tooltip(self.label)
            self.label.bind("<Button-1>", self.toggle_mode)
            self.update_count()

        elif event_type in ['node_added', 'node_edit_save']:
            self.update_count()

    def toggle_mode(self, event=None):
        self.show_only_story = not self.show_only_story
        self.update_count()

    def update_count(self):
        """Подсчитывает слова во всех узлах с разделением по типам"""
        if not self.label:
            return

        total_words = 0
        story_words = 0
        choice_words = 0
        system_words = 0
        
        # Перебираем все узлы редактора
        for node in self.editor.nodes:
            if not node.content:
                continue
            
            cnt = len(node.content.split())
            total_words += cnt
            
            ntype = getattr(node, 'node_type', '')
            if ntype == 'story':
                story_words += cnt
            elif ntype == 'choice':
                choice_words += cnt
            else:
                system_words += cnt

        lit_words = story_words + choice_words
        
        if self.show_only_story:
            self.label.config(text=f"Текст: {lit_words} сл.")
        else:
            self.label.config(text=f"Слов: {total_words}")

        if self.tooltip:
            mode_hint = "текст (клик: всё)" if self.show_only_story else "всё (клик: только текст)"
            tip = (
                f"📊 Статистика слов:\n"
                f" • Сюжет (story): {story_words}\n"
                f" • Выборы (choice): {choice_words}\n"
                f" • Служебные (JSON/код): {system_words}\n"
                f" • Всего: {total_words}\n\n"
                f"Режим: {mode_hint}"
            )
            self.tooltip.set_text(tip)

    def update_loop(self):
        if not self.running:
            return
            
        try:
            if self.editor.winfo_exists():
                self.update_count()
                self.editor.after(500, self.update_loop)
        except Exception:
            pass