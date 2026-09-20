import tkinter as tk
from tkinter import ttk, messagebox
from plugin_system import Plugin

class GraphValidatorPlugin(Plugin):
    name = "Graph Validator (Diagnostics)"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            parent = getattr(self.editor, 'toolbar_right', data)
            tk.Button(
                parent,
                text="🩺 Проверка сюжета",
                command=self.run_diagnostics,
                bg='#2c3e50',
                activebackground='#34495e',
                fg='#5dade2',
                activeforeground='white',
                relief='flat',
                font=('Segoe UI', 9, 'bold'),
                padx=8,
                pady=3,
                cursor='hand2'
            ).pack(side=tk.RIGHT, padx=3)

    def run_diagnostics(self):
        nodes = self.editor.nodes
        connections = self.editor.connections

        if not nodes:
            messagebox.showinfo("Диагностика сюжета", "Холст пуст! Добавьте ноды для проверки.", parent=self.editor)
            return

        issues = []

        # 1. Проверка стартовой точки
        incoming_map = {}
        outgoing_map = {}
        for n in nodes:
            incoming_map[n.id] = []
            outgoing_map[n.id] = []

        for c in connections:
            if c['from'] in outgoing_map:
                outgoing_map[c['from']].append(c)
            if c['to'] in incoming_map:
                incoming_map[c['to']].append(c)

        # Поиск start-ноды
        start_nodes = [n for n in nodes if n.title.lower().strip() == 'start']
        if not start_nodes:
            # Ищем ноды без входов
            zero_in = [n for n in nodes if len(incoming_map[n.id]) == 0]
            if not zero_in:
                issues.append({
                    'severity': 'ERROR',
                    'node': None,
                    'msg': "Не найдена стартовая нода! Создайте ноду с заголовком 'start' или убедитесь, что в графе есть начало."
                })
            elif len(zero_in) > 1:
                issues.append({
                    'severity': 'WARNING',
                    'node': zero_in[0],
                    'msg': f"Найдено несколько возможных начал сюжета ({len(zero_in)} нод без входа). Рекомендуется назвать главную ноду 'start'."
                })
        else:
            zero_in = [start_nodes[0]]

        # 2. Недостижимые ноды (нет входов и это не start)
        for n in nodes:
            is_start = (n in start_nodes) or (not start_nodes and n in zero_in[:1])
            if not is_start and len(incoming_map[n.id]) == 0:
                issues.append({
                    'severity': 'WARNING',
                    'node': n,
                    'msg': f"Узел '{n.title}' [{n.node_type}] недостижим — к нему нет входящих связей."
                })

        # 3. Проверка нод выбора (Choice) на неподключенные варианты
        for n in nodes:
            if n.node_type == 'choice':
                options = [opt for opt in n.content.split('\n') if opt.strip()]
                connected_indices = {c['out_idx'] for c in outgoing_map[n.id]}
                for idx, opt in enumerate(options):
                    if idx not in connected_indices:
                        issues.append({
                            'severity': 'ERROR',
                            'node': n,
                            'msg': f"В узле выбора '{n.title}' вариант '{opt[:25]}...' (№{idx+1}) никуда не ведёт!"
                        })

        # 4. Проверка нод условий (Condition)
        for n in nodes:
            if n.node_type == 'condition':
                connected_indices = {c['out_idx'] for c in outgoing_map[n.id]}
                if 0 not in connected_indices:
                    issues.append({
                        'severity': 'ERROR',
                        'node': n,
                        'msg': f"Условие '{n.title}' не имеет выхода для ветки True (Да)."
                    })
                if 1 not in connected_indices:
                    issues.append({
                        'severity': 'ERROR',
                        'node': n,
                        'msg': f"Условие '{n.title}' не имеет выхода для ветки False (Нет)."
                    })

        # 5. Тупиковые ноды (нет выходов)
        for n in nodes:
            if len(outgoing_map[n.id]) == 0:
                # Если в заголовке или тексте нет слова 'конец', 'финал', 'end'
                title_lower = n.title.lower()
                if not any(w in title_lower for w in ['конец', 'финал', 'end']):
                    issues.append({
                        'severity': 'INFO',
                        'node': n,
                        'msg': f"Узел '{n.title}' является тупиковым (нет выходов). Если это финал, назовите его 'Финал' или 'Конец'."
                    })

        # Отображение результатов
        self.show_results_dialog(issues)

    def show_results_dialog(self, issues):
        dialog = tk.Toplevel(self.editor)
        dialog.title("Диагностика сценария")
        dialog.geometry("650x450")
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.editor)

        # Верхняя панель со статусом
        status_frame = tk.Frame(dialog, bg='#252526', padx=15, pady=10)
        status_frame.pack(fill=tk.X)

        errors_count = sum(1 for i in issues if i['severity'] == 'ERROR')
        warnings_count = sum(1 for i in issues if i['severity'] == 'WARNING')

        if errors_count == 0 and warnings_count == 0:
            status_text = "🎉 Отлично! Критических сюжетных дыр и ошибок не обнаружено."
            status_fg = "#2ecc71"
        else:
            status_text = f"Найдено замечаний: {len(issues)} (Ошибок: {errors_count}, Предупреждений: {warnings_count})"
            status_fg = "#e74c3c" if errors_count > 0 else "#f39c12"

        tk.Label(status_frame, text=status_text, bg='#252526', fg=status_fg, font=("Segoe UI", 11, "bold")).pack(anchor='w')
        tk.Label(status_frame, text="Двойной клик по строке сфокусирует холст на проблемной ноде.", bg='#252526', fg='#888888', font=("Segoe UI", 8)).pack(anchor='w', pady=(3, 0))

        # Список замечаний
        list_frame = tk.Frame(dialog, bg='#1e1e1e', padx=10, pady=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("severity", "message")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        tree.heading("severity", text="Тип")
        tree.heading("message", text="Описание проблемы")
        tree.column("severity", width=110, stretch=False)
        tree.column("message", width=500, stretch=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Стилизация элементов списка
        for idx, item in enumerate(issues):
            sev = item['severity']
            prefix = "❌ ОШИБКА" if sev == 'ERROR' else ("⚠️ ВНИМАНИЕ" if sev == 'WARNING' else "ℹ️ ИНФО")
            tree.insert("", tk.END, iid=str(idx), values=(prefix, item['msg']))

        def on_item_double_click(event):
            selected = tree.selection()
            if not selected:
                return
            idx = int(selected[0])
            target_node = issues[idx]['node']
            if target_node:
                self.focus_on_node(target_node)

        tree.bind("<Double-Button-1>", on_item_double_click)

        # Нижняя панель кнопок
        bottom_frame = tk.Frame(dialog, bg='#1e1e1e', padx=10, pady=10)
        bottom_frame.pack(fill=tk.X)

        def focus_selected():
            selected = tree.selection()
            if selected:
                idx = int(selected[0])
                target_node = issues[idx]['node']
                if target_node:
                    self.focus_on_node(target_node)

        tk.Button(bottom_frame, text="🔍 Показать на холсте", command=focus_selected, 
                  bg='#007acc', fg='white', relief='flat', padx=10, pady=4).pack(side=tk.LEFT)
        tk.Button(bottom_frame, text="Закрыть", command=dialog.destroy, 
                  bg='#333333', fg='white', relief='flat', padx=10, pady=4).pack(side=tk.RIGHT)

    def focus_on_node(self, node):
        # Выделяем ноду
        self.editor.selected_nodes = [node]
        self.editor.selected_connection = None
        
        # Центрируем холст на ноде
        canvas = self.editor.canvas
        canvas_w = canvas.winfo_width() or 800
        canvas_h = canvas.winfo_height() or 600

        # Scrollregion: (0, -limit, limit, limit) где limit = 50000
        limit = 50000
        total_w = limit
        total_h = 2 * limit

        target_x = max(0, node.x - canvas_w / 2 + node.width / 2)
        target_y = node.y - canvas_h / 2 + node.height / 2

        x_frac = target_x / total_w
        y_frac = (target_y + limit) / total_h

        canvas.xview_moveto(max(0.0, min(1.0, x_frac)))
        canvas.yview_moveto(max(0.0, min(1.0, y_frac)))
        self.editor.redraw()
