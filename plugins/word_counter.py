import tkinter as tk
from plugin_system import Plugin

class WordCountPlugin(Plugin):
    name = "Word Counter"
    version = "1.1"

    def __init__(self, editor):
        super().__init__(editor)
        self.label = None
        self.running = True

    def on_enable(self):
        # Запускаем фоновый цикл проверки (на случай удаления нод,
        # так как main.py не отправляет событие при удалении)
        self.update_loop()

    def on_event(self, event_type, data):
        # При создании интерфейса добавляем лейбл в тулбар
        if event_type == 'setup_ui':
            toolbar = data
            # Создаем разделитель и сам лейбл
            tk.Label(toolbar, text="|", bg='#444', fg='#666').pack(side=tk.RIGHT, padx=2)
            self.label = tk.Label(
                toolbar, 
                text="Слов: 0", 
                bg='#444', 
                fg='#00ff00',  # Ярко-зеленый цвет
                font=("Segoe UI", 9, "bold")
            )
            self.label.pack(side=tk.RIGHT, padx=10)
            self.update_count()

        # Обновляем сразу при добавлении или сохранении изменений
        elif event_type in ['node_added', 'node_edit_save']:
            self.update_count()

    def update_count(self):
        """Подсчитывает слова во всех узлах"""
        if not self.label:
            return

        total_words = 0
        
        # Перебираем все узлы редактора
        for node in self.editor.nodes:
            # Считаем слова в контенте
            if node.content:
                # split() без аргументов делит по пробелам и переносам строк
                words = node.content.split()
                total_words += len(words)
            
            # Опционально: можно считать слова в заголовках, 
            # если они не являются комментариями (не начинаются с #)
            # if node.title and not node.title.startswith('#'):
            #     total_words += len(node.title.split())

        self.label.config(text=f"Слов: {total_words}")

    def update_loop(self):
        """
        Фоновый цикл обновления. Нужен для отлова ситуаций, 
        которые не имеют событий (например, удаление ноды).
        """
        if not self.running:
            return
            
        try:
            # Если окно редактора существует
            if self.editor.winfo_exists():
                self.update_count()
                # Проверяем каждые 500 мс (0.5 сек)
                self.editor.after(500, self.update_loop)
        except Exception:
            pass