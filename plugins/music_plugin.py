import tkinter as tk
from tkinter import filedialog
import os
from plugin_system import Plugin

class MusicPlugin(Plugin):
    name = "Music & Audio"
    version = "1.6"

    def on_enable(self):
        # Хранилище состояния редактирования для каждого узла
        self.edit_state = {}

    def on_event(self, event_type, data=None):
        # --- 1. Регистрация в меню ---
        if event_type == 'setup_ui':
            toolbar = data
            if not hasattr(self.editor, 'plugin_menu'):
                self.editor.plugin_menu_btn = tk.Menubutton(toolbar, text="🧩 Компоненты ▾", bg='#444', fg='white', 
                                                           relief='flat', font=('Segoe UI', 9, 'bold'), padx=10, pady=5)
                self.editor.plugin_menu_btn.pack(side=tk.LEFT, padx=5, pady=5)
                self.editor.plugin_menu = tk.Menu(self.editor.plugin_menu_btn, tearoff=0, bg='#444', fg='white')
                self.editor.plugin_menu_btn["menu"] = self.editor.plugin_menu
            
            self.editor.plugin_menu.add_command(label="🎵 Звук / Музыка", command=lambda: self.editor.add_node('music'))
        
        # --- 2. Инициализация нового узла ---
        elif event_type == 'node_added':
            node = data
            if getattr(node, 'is_new', True) and node.node_type == 'music':
                # ЦВЕТА: Делаем заголовок темнее
                node.custom_data['bg_color'] = '#196f3d'      # Темно-зеленый фон (основной)
                node.custom_data['header_color'] = '#0d4528'  # Очень темный зеленый (заголовок)
                node.custom_data['text_color'] = '#ffffff'    # Белый текст
                
                self.editor.redraw()

        # --- 3. Отрисовка иконки ---
        elif event_type == 'draw_node':
            node = data['node']
            canvas = data['canvas']
            if getattr(node, 'is_new', True) and node.node_type == 'music':
                canvas.create_text(node.x + node.width - 20, node.y + 12, text="🎵", fill="white", tags=("node", node.id))

        # --- 4. Интерфейс редактирования ---
        elif event_type == 'node_edit_dialog':
            node = data['node']
            frame = data['frame']
            # Получаем ссылку на само окно диалога, чтобы управлять его фокусом
            dialog_window = data.get('dialog')
            
            if getattr(node, 'is_new', True) and node.node_type == 'music':
                music_frame = tk.LabelFrame(frame, text="Настройки Аудио", bg=frame['bg'], fg='white', padx=5, pady=5)
                music_frame.pack(fill=tk.X, pady=10)

                current_mode = node.custom_data.get('music_mode', 'bg')
                current_file = node.custom_data.get('music_file', '')

                self.edit_state[node.id] = {}

                # Тип воспроизведения
                tk.Label(music_frame, text="Тип воспроизведения:", bg=frame['bg'], fg='#aaa').pack(anchor='w')
                mode_var = tk.StringVar(value=current_mode)
                self.edit_state[node.id]['mode'] = mode_var
                
                rb_frame = tk.Frame(music_frame, bg=frame['bg'])
                rb_frame.pack(fill=tk.X, pady=2)
                
                rb_style = {'bg': frame['bg'], 'fg': 'white', 'selectcolor': '#444', 
                            'activebackground': frame['bg'], 'activeforeground': 'white'}
                
                tk.Radiobutton(rb_frame, text="Фоновая музыка (Loop)", variable=mode_var, value="bg", **rb_style).pack(side=tk.LEFT)
                tk.Radiobutton(rb_frame, text="Озвучка (Voice)", variable=mode_var, value="voice", **rb_style).pack(side=tk.LEFT, padx=10)

                # Выбор файла
                tk.Label(music_frame, text="Путь к файлу:", bg=frame['bg'], fg='#aaa').pack(anchor='w', pady=(5,0))
                
                file_container = tk.Frame(music_frame, bg=frame['bg'])
                file_container.pack(fill=tk.X)
                
                file_entry = tk.Entry(file_container, bg='#222', fg='white', insertbackground='white')
                file_entry.insert(0, current_file)
                file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                
                self.edit_state[node.id]['file_entry'] = file_entry
                
                def browse_file():
                    # parent=dialog_window привязывает диалог выбора файла к окну редактирования
                    path = filedialog.askopenfilename(
                        parent=dialog_window,
                        filetypes=[("Audio Files", "*.mp3 *.wav *.ogg")]
                    )
                    
                    # ПРИНУДИТЕЛЬНО ВОЗВРАЩАЕМ ФОКУС ОКНУ РЕДАКТИРОВАНИЯ
                    if dialog_window:
                        dialog_window.lift()
                        dialog_window.focus_force()

                    if path:
                        file_entry.delete(0, tk.END)
                        file_entry.insert(0, path)
                        
                        # Авто-сохранение и обновление цвета
                        mode = mode_var.get()
                        
                        node.custom_data['music_mode'] = mode
                        node.custom_data['music_file'] = path
                        
                        # Подтверждаем темный заголовок
                        node.custom_data['bg_color'] = '#196f3d'
                        node.custom_data['header_color'] = '#0d4528'
                        
                        icon = "🔁" if mode == 'bg' else "🗣️"
                        filename = os.path.basename(path)
                        node.content = f"{icon} {mode.upper()}\n📂: {filename}"
                        
                        node.calculate_size()
                        self.editor.redraw()

                tk.Button(file_container, text="📂", command=browse_file, 
                         bg='#27ae60', fg='white', relief='flat', width=3).pack(side=tk.LEFT, padx=5)

        # --- 5. Сохранение данных (кнопка Сохранить) ---
        elif event_type == 'node_edit_save':
            node = data['node']
            if getattr(node, 'is_new', True) and node.node_type == 'music' and node.id in self.edit_state:
                state = self.edit_state[node.id]
                try:
                    mode = state['mode'].get()
                    path = state['file_entry'].get()
                    
                    node.custom_data['music_mode'] = mode
                    node.custom_data['music_file'] = path
                    
                    icon = "🔁" if mode == 'bg' else "🗣️"
                    filename = os.path.basename(path) if path else "[Нет файла]"
                    node.content = f"{icon} {mode.upper()}\n📂: {filename}"
                    
                    # Сохраняем цвета
                    node.custom_data['bg_color'] = '#196f3d'
                    node.custom_data['header_color'] = '#0d4528'
                    
                except Exception as e:
                    print(f"[MusicPlugin] Error saving node {node.id}: {e}")
                
                del self.edit_state[node.id]