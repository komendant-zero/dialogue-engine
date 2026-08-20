import tkinter as tk
from plugin_system import Plugin
import math

class CoreNodesPlugin(Plugin):
    name = "Core Nodes"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            toolbar = data
            btn_cfg = {'bg': '#444', 'fg': 'white', 'relief': 'flat', 'padx': 10, 'pady': 5}
            tk.Button(toolbar, text="Сюжет (story)", command=lambda: self.editor.add_node('story'), **btn_cfg).pack(side=tk.LEFT, padx=5, pady=5)
            tk.Button(toolbar, text="Выбор (choice)", command=lambda: self.editor.add_node('choice'), **btn_cfg).pack(side=tk.LEFT, padx=5, pady=5)
            
        elif event_type == 'context_menu':
            if not data['target']:
                menu = data['menu7]
                menu.add_command(label="Сцена", command=lambda: self.editor.add_node('story', data['x'], data['y7]))
                menu.add_command(label="Выбор", command=lambda: self.editor.add_node('choice', data['x'], data['y7]))

        elif event_type == 'node_added':
            node = data
            if getattr(node, 'is_new', True):
                if node.node_type == 'story':
                    node.title = "ПерсонаѶ"
                    node.content = "Текст..."
                elif node.node_type == 'choice':
                    node.title = "Выбор"
                    node.content = "Вариант 1\nВариант 2"

        elif event_type == 'calculate_node_size':
            node = data['node']
            if node.node_type == 'choice':
                display_content = data['display_content']
                options = display_content.split('\n')
                data['height'] = data['base_h'] + (len(options) * 25) + 10
                data['handled']['done'] = True

        elif event_type == 'draw_node_content':
            node = data['node']
            canvas = data['canvas']
            x, y, w, h = node.x, node.y, node.width, node.height
            text_col = node.custom_data.get('text_color', '#dcdcdc')
            display_content = node._get_display_text(node.content)
            
            if node.node_type == 'choice':
                highlights = node.custom_data.get('highlights', {})
                options = display_content.split('\n')
                for i, opt in enumerate(options):
                    opt_y = y + 35 + (i * 25)
                    if highlights:
                        text_colors = [text_col] * len(opt)
                        for phrase, color in highlights.items():
                            if not phrase: continue
                            display_phrase = node._get_display_text(phrase)
                            start = 0
                            while True:
                                idx = opt.find(display_phrase, start)
                                if idx == -1: break
                                for j in range(idx, idx + len(display_phrase)):
                                    text_colors[j] = color
                                start = idx + 1
                        chunks = []
                        if opt:
                            chunk_color = text_colors[0]
                            chunk_text = opt[0]
                            for k in range(1, len(opt)):
                                c_col = text_colors[k]
                                if c_col == chunk_color:
                                    chunk_text += opt[k]
                                else:
                                    chunks.append((chunk_text, chunk_color))
                                    chunk_text = opt[k]
                                    chunk_color = c_col
                            chunks.append((chunk_text, chunk_color))
                        cur_x = x + w - 15
                        for text_chunk, color in reversed(chunks):
                            canvas.create_text(cur_x, opt_y, text=text_chunk, fill=color, anchor="e", font=node.font_content, tags=("node", node.id))
                            cur_x -= node.font_content.measure(text_chunk)
                    else:
                        canvas.create_text(x+w-15, opt_y, text=opt, fill=text_col, anchor="e", font=node.font_content, tags=("node", node.id))
                    
                    node.draw_port(canvas, x+w, opt_y, i)
                    
                data['handled'] = True
                
            elif node.node_type == 'story':
                if node.mode == 'continue':
                    canvas.create_text(x+w-10, y+12, text="[+]", fill="#fff", anchor="e", font=("Segoe UI", 8, "bold"), tags=("node", node.id))

        elif event_type == 'draw_node_ports':
            node = data['node']
            canvas = data['canvas']
            if node.node_type == 'choice':
                in_y = node.y + 25
                node.draw_input_port(canvas, node.x, in_y)
                data['handled'] = True

        elif event_type == 'node_edit_dialog':
            node = data['node']
            dialog = data['dialog']
            if node.node_type == 'story':
                mode_frame = tk.LabelFrame(dialog, text="Режим отображения", bg='#1e1e1e', fg='white')
                mode_frame.pack(fill=tk.X, padx=10, pady=5)
                
                mode_var = tk.StringVar(value=node.mode)
                self.edit_state = mode_var
                
                rb_std = tk.Radiobutton(mode_frame, text="Стандартный", variable=mode_var, value="standard", 
                                        bg='#1e1e1e', fg='white', selectcolor='#1e1e1e', activebackground='#1e1e1e', activeforeground='white')
                rb_cont = tk.Radiobutton(mode_frame, text="Продолжение (сшивание)", variable=mode_var, value="continue", 
                                        bg='#1e1e1e', fg='white', selectcolor='#1e1e1e', activebackground='#1e1e1e', activeforeground='white')
                
                rb_std.pack(side=tk.LEFT, padx=10)
                rb_cont.pack(side=tk.LEFT, padx=10)

        elif event_type == 'node_edit_save':
            node = data['node']
            if node.node_type == 'story' and hasattr(self, 'edit_state'):
                node.mode = self.edit_state.get()
