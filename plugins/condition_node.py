import tkinter as tk
from plugin_system import Plugin

class ConditionNodePlugin(Plugin):
    name = "Condition (If / Else)"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            self.add_toolbar_item(data)

        elif event_type == 'node_added':
            node = data
            if getattr(node, 'is_new', True) and node.node_type == 'condition':
                node.custom_data['bg_color'] = '#1b4f72'       # Глубокий сине-стальной фон
                node.custom_data['header_color'] = '#154360'   # Тёмный заголовок
                node.custom_data['text_color'] = '#58d68d'     # Светло-зеленый текст условия
                node.title = "Условие"
                node.content = "has_key == True"
                self.editor.redraw()

        elif event_type == 'calculate_node_size':
            node = data['node']
            if node.node_type == 'condition':
                # Заголовок + условие + 2 выхода (True / False)
                data['height'] = data['base_h'] + 65
                data['handled']['done'] = True

        elif event_type == 'draw_node':
            node = data['node']
            canvas = data['canvas']
            if node.node_type == 'condition':
                # Иконка вопроса в заголовке
                canvas.create_text(node.x + node.width - 20, node.y + 12, text="❓", fill="white", tags=("node", node.id))

        elif event_type == 'draw_node_content':
            node = data['node']
            canvas = data['canvas']
            if node.node_type == 'condition':
                x, y, w, h = node.x, node.y, node.width, node.height
                text_col = node.custom_data.get('text_color', '#58d68d')
                display_content = node._get_display_text(node.content)

                # 1. Текст условия
                canvas.create_text(x + 10, y + 32, text=f"if {display_content}:", fill=text_col, 
                                   anchor="nw", font=("Consolas", 9, "bold"), tags=("node", node.id))

                # 2. Метки выходов True / False
                y_true = y + 35 + 15
                y_false = y + 35 + 40

                canvas.create_text(x + w - 18, y_true, text="True (Да)", fill="#2ecc71", 
                                   anchor="e", font=("Segoe UI", 8, "bold"), tags=("node", node.id))
                canvas.create_text(x + w - 18, y_false, text="False (Нет)", fill="#e74c3c", 
                                   anchor="e", font=("Segoe UI", 8, "bold"), tags=("node", node.id))

                # Рисуем порты выходов
                self.draw_colored_port(node, canvas, x + w, y_true, 0, "#2ecc71")
                self.draw_colored_port(node, canvas, x + w, y_false, 1, "#e74c3c")

                data['handled'] = True

        elif event_type == 'draw_node_ports':
            node = data['node']
            canvas = data['canvas']
            if node.node_type == 'condition':
                # Входной порт по центру верхней части
                in_y = node.y + 35
                node.draw_input_port(canvas, node.x, in_y)
                data['handled'] = True

        elif event_type == 'renpy_export_node':
            node = data['node']
            f = data['file']
            conns = data['connections']

            if node.node_type == 'condition':
                cond_expr = node.content.strip() or "True"
                
                # Находим соединения для True (0) и False (1)
                conn_true = next((c for c in conns if c['from'] == node.id and c['out_idx'] == 0), None)
                conn_false = next((c for c in conns if c['from'] == node.id and c['out_idx'] == 1), None)

                f.write(f"    if {cond_expr}:\n")
                if conn_true:
                    f.write(f"        jump node_{conn_true['to']}\n")
                else:
                    f.write("        return\n")

                f.write("    else:\n")
                if conn_false:
                    f.write(f"        jump node_{conn_false['to']}\n")
                else:
                    f.write("        return\n")

                data['handled'] = True

    def draw_colored_port(self, node, canvas, px, py, index, color):
        r = 5
        tag = f"port_out_{node.id}_{index}"
        canvas.create_oval(px-r, py-r, px+r, py+r, fill=color, outline="#222222", width=1, tags=("port", "output", tag))
        node.outputs.append({'id': index, 'x': px, 'y': py, 'tag': tag})

    def add_toolbar_item(self, toolbar):
        if hasattr(self.editor, 'plugin_menu'):
            self.editor.plugin_menu.add_command(
                label="❓ Условие (If / Else)", 
                command=lambda: self.editor.add_node('condition')
            )
