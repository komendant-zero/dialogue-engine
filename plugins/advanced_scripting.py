import tkinter as tk
from plugin_system import Plugin

class AdvancedScriptingPlugin(Plugin):
    name = "Advanced Scripting"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            self.add_toolbar_menu(data)
        
        elif event_type == 'node_added':
            node = data
            if getattr(node, 'is_new', True) and node.node_type == 'python_code':
                node.custom_data['bg_color'] = '#2c3e50'
                node.custom_data['header_color'] = '#34495e'
                node.custom_data['text_color'] = '#2ecc71' # Зеленый (код)
                node.title = "Python Block"
                node.content = "# Пишите код здесь\npass"
                self.editor.redraw()
            elif getattr(node, 'is_new', True) and node.node_type == 'raw_rpy':
                node.custom_data['bg_color'] = '#16a085'
                node.custom_data['header_color'] = '#1abc9c'
                node.custom_data['text_color'] = '#ffffff'
                node.title = "Raw Ren'Py"
                node.content = "show expression \"bg/room.jpg\" with dissolve"
                self.editor.redraw()

        elif event_type == 'draw_node':
            node = data['node']
            canvas = data['canvas']
            if getattr(node, 'is_new', True) and node.node_type == 'python_code':
                canvas.create_text(node.x + node.width - 20, node.y + 12, text="🐍", fill="white", tags=("node", node.id))
            elif getattr(node, 'is_new', True) and node.node_type == 'raw_rpy':
                canvas.create_text(node.x + node.width - 20, node.y + 12, text="📄", fill="white", tags=("node", node.id))

        elif event_type == 'renpy_export_node':
            node = data['node']
            f = data['file']
            conns = data['connections']
            
            if getattr(node, 'is_new', True) and node.node_type == 'python_code':
                f.write("    python:\n")
                lines = node.content.split('\n')
                for line in lines:
                    f.write(f"        {line}\n")
                self.write_jump(f, node.id, conns)
                data['handled'] = True
                
            elif getattr(node, 'is_new', True) and node.node_type == 'raw_rpy':
                lines = node.content.split('\n')
                for line in lines:
                    f.write(f"    {line}\n")
                self.write_jump(f, node.id, conns)
                data['handled'] = True

    def add_toolbar_menu(self, toolbar):
        # Используем Menubutton для экономии места
        mb = tk.Menubutton(toolbar, text="📜 Скрипты ▾", bg='#34495e', fg='white', 
                          relief='flat', font=('Segoe UI', 9, 'bold'), padx=10, pady=5)
        mb.pack(side=tk.LEFT, padx=5, pady=5)
        
        menu = tk.Menu(mb, tearoff=0, bg='#34495e', fg='white', activebackground='#2c3e50')
        menu.add_command(label="🐍 Python Блок", command=lambda: self.editor.add_node('python_code'))
        menu.add_command(label="📄 Сырой Ren'Py", command=lambda: self.editor.add_node('raw_rpy'))
        mb["menu"] = menu

    def write_jump(self, f, node_id, connections):
        out_conns = [c for c in connections if c['from'] == node_id]
        if out_conns:
            target_id = out_conns[0]['to']
            f.write(f'    jump node_{target_id}\n')
        else:
            f.write('    return\n')
