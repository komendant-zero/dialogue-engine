import tkinter as tk
from plugin_system import Plugin
import math

class CoreNodesPlugin(Plugin):
    name = "Core Nodes"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'context_menu':
            if not data['target']:
                menu = data['menu']
                menu.add_command(label="Сцена", command=lambda: self.editor.add_node('story', data['x'], data['y']))
                menu.add_command(label="Выбор", command=lambda: self.editor.add_node('choice', data['x'], data['y']))

        elif event_type == 'node_added':
            node = data
            if getattr(node, 'is_new', True):
                if node.node_type == 'story':
                    node.title = "Сцена"
                    node.content = "Текст..."
                elif node.node_type == 'choice':
                    node.title = "Выбор"
                    node.content = "Вариант 1\nВариант 2"

        elif event_type == 'calculate_node_size':
            node = data['node']
            if node.node_type == 'choice':
                display_content = data['display_content']
                options = display_content.split('\n')
                font = getattr(node, 'font_content', None)

                # Вычисляем максимальную длину строки для адаптивной ширины блока
                max_text_w = 140
                if font:
                    for opt in options:
                        clean_opt = opt.strip() if opt else ""
                        if clean_opt:
                            w_meas = font.measure(clean_opt)
                            if w_meas > max_text_w:
                                max_text_w = w_meas

                # Адаптивная ширина: базовая 200px, максимум 340px (если текст длиннее, он переносится)
                node.width = max(200, min(340, max_text_w + 40))
                avail_w = max(100, node.width - 32)

                port_offsets = []
                curr_y = 35.0
                canvas = self.editor.canvas if (self.editor and hasattr(self.editor, 'canvas')) else None

                for opt in options:
                    clean_opt = opt.strip() if opt else ""
                    if not clean_opt:
                        opt_h = 24.0
                    elif canvas and font:
                        temp_t = canvas.create_text(0, 0, text=clean_opt, width=avail_w, font=font, anchor="nw")
                        bbox = canvas.bbox(temp_t)
                        canvas.delete(temp_t)
                        opt_h = max(24.0, (bbox[3] - bbox[1]) + 8.0) if bbox else 24.0
                    elif font:
                        lines_cnt = max(1, math.ceil(font.measure(clean_opt) / avail_w))
                        opt_h = max(24.0, lines_cnt * 18.0 + 6.0)
                    else:
                        opt_h = 24.0

                    port_offsets.append(curr_y + (opt_h / 2.0))
                    curr_y += opt_h + 6.0

                node._choice_port_offsets = port_offsets
                data['height'] = curr_y + 8.0
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
                port_offsets = getattr(node, '_choice_port_offsets', None)
                if not port_offsets or len(port_offsets) != len(options):
                    port_offsets = [35.0 + 12.0 + (i * 28.0) for i in range(len(options))]

                avail_w = max(100, w - 32)

                for i, opt in enumerate(options):
                    clean_opt = opt.strip() if opt else ""
                    port_y = y + port_offsets[i]

                    # Проверяем наличие подсветки конкретных фраз
                    matched_highlight = None
                    if highlights and clean_opt:
                        for phrase, color in highlights.items():
                            if phrase and phrase in clean_opt:
                                matched_highlight = color
                                break

                    # Если текст вмещается в одну строку и есть фрагментарная подсветка
                    if matched_highlight and node.font_content and node.font_content.measure(clean_opt) <= avail_w and len(highlights) > 0:
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
                        cur_x = x + w - 18
                        for text_chunk, color in reversed(chunks):
                            canvas.create_text(cur_x, port_y, text=text_chunk, fill=color, anchor="e", font=node.font_content, tags=("node", node.id))
                            cur_x -= node.font_content.measure(text_chunk)
                    else:
                        # Текст опции с жесткой привязкой к границам блока (не может вылезти влево или вправо)
                        fill_color = matched_highlight if matched_highlight else text_col
                        canvas.create_text(
                            x + w - 18,
                            port_y,
                            text=opt,
                            fill=fill_color,
                            anchor="e",
                            justify="right",
                            width=avail_w,
                            font=node.font_content,
                            tags=("node", node.id)
                        )
                    
                    node.draw_port(canvas, x + w, port_y, i)
                    
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
