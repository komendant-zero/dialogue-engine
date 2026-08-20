import tkinter as tk
from plugin_system import Plugin

class FlowNodesPlugin(Plugin):
    name = "Flow & Variables"
    version = "1.0"

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
