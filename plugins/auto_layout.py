import os
import sys
import json
from collections import defaultdict, deque

try:
    from plugin_system import Plugin
except ImportError:
    class Plugin:
        name = "BasePlugin"
        version = "1.0"
        def __init__(self, editor): self.editor = editor
        def on_enable(self): pass
        def on_event(self, event_type, data=None): pass

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    tk = None
    messagebox = None


def compute_auto_layout(nodes_list, conns_list, start_x=100, baseline_y=400, dx=280, dy=180, grid_snap=20):
    """
    Интеллектуальный алгоритм расстановки графа нод диалогового редактора:
    - Поток строго слева направо (DAG).
    - Базовая сюжетная линия на уровне baseline_y (по умолчанию 400).
    - Ветвления аккуратно разносятся по параллельным дорожкам (верхняя / нижняя).
    - Короткие тупиковые реплики (dead-ends) располагаются под узлом выбора.
    - Точки схождения (Merge) центрируются на базовой линии с плавной стыковкой.
    - Привязка всех координат к сетке grid_snap (по умолчанию 20 px).
    
    Возвращает:
      positions: dict {str(node_id): (x, y)}
      topo_order: list [node_id, ...]
    """
    if not nodes_list:
        return {}, []

    nodes_dict = {}
    for n in nodes_list:
        nid = str(getattr(n, 'id', None) or n.get('id'))
        nodes_dict[nid] = n

    adj = defaultdict(list)
    rev_adj = defaultdict(list)
    in_deg = defaultdict(int)
    out_deg = defaultdict(int)

    for c in conns_list:
        u = str(c['from'])
        v = str(c['to'])
        out_idx = int(c.get('out_idx', 0))
        adj[u].append((out_idx, v))
        rev_adj[v].append(u)
        out_deg[u] += 1
        in_deg[v] += 1

    for u in adj:
        adj[u].sort(key=lambda item: item[0])

    # Поиск корней (входящая степень = 0)
    roots = [nid for nid in nodes_dict if in_deg[nid] == 0]
    if not roots:
        roots = [next(iter(nodes_dict))]

    # 1. Топологический ранг (X-координата: Longest Path DAG)
    rank = {}
    temp_in_deg = {nid: in_deg[nid] for nid in nodes_dict}
    queue = deque([r for r in roots])
    for r in roots:
        rank[r] = 0

    topo_order = []
    while queue:
        u = queue.popleft()
        topo_order.append(u)
        current_rank = rank[u]
        for out_idx, v in adj[u]:
            rank[v] = max(rank.get(v, 0), current_rank + 1)
            temp_in_deg[v] -= 1
            if temp_in_deg[v] == 0:
                queue.append(v)

    # Обработка возможных циклов или изолированных узлов
    for nid in nodes_dict:
        if nid not in rank:
            rank[nid] = max(rank.values(), default=0) + 1
            topo_order.append(nid)

    # 2. Вычисление дорожек (Y-координаты)
    merge_nodes = set(nid for nid, d in in_deg.items() if d > 1)
    y_coords = {}

    for r in roots:
        y_coords[r] = baseline_y

    for u in topo_order:
        u_y = y_coords.get(u, baseline_y)
        outs = adj.get(u, [])
        if not outs:
            continue

        if len(outs) == 1:
            v = outs[0][1]
            if v not in y_coords and v not in merge_nodes:
                y_coords[v] = u_y
        else:
            # Узел выбора (Choice)
            num_outs = len(outs)
            for idx, (out_idx, v) in enumerate(outs):
                if v in y_coords:
                    continue

                # Проверка: является ли ветка коротким тупиком
                curr = v
                depth = 0
                while curr and adj.get(curr) and len(adj[curr]) == 1 and curr not in merge_nodes and depth < 25:
                    curr = adj[curr][0][1]
                    depth += 1

                is_dead_end = (len(adj.get(curr, [])) == 0 and curr not in merge_nodes and depth <= 2)

                if is_dead_end:
                    # Тупиковые варианты располагаются каскадом ниже выбора
                    y_coords[v] = u_y + (idx * dy) if idx > 0 else u_y
                else:
                    # Полноценные сюжетные ветки: симметрично от базовой линии
                    if num_outs == 2:
                        y_coords[v] = (u_y - dy) if idx == 0 else (u_y + dy)
                    elif num_outs == 3:
                        if idx == 0:
                            y_coords[v] = u_y
                        elif idx == 1:
                            y_coords[v] = u_y + dy
                        else:
                            y_coords[v] = u_y + 2 * dy
                    else:
                        y_coords[v] = u_y + (idx - num_outs // 2) * dy

    # Для точек слияния (Merge) возвращаем уровень на базовую линию
    for m in merge_nodes:
        y_coords[m] = baseline_y
        curr = m
        while curr:
            y_coords[curr] = baseline_y
            outs = adj.get(curr, [])
            if len(outs) == 1:
                curr = outs[0][1]
            else:
                break

    # Распространяем координаты по цепочкам
    for u in topo_order:
        u_y = y_coords.get(u, baseline_y)
        outs = adj.get(u, [])
        for out_idx, v in outs:
            if v not in y_coords:
                y_coords[v] = u_y

    # Формируем итоговые координаты со снапом к сетке
    positions = {}
    for nid, node in nodes_dict.items():
        rx = rank.get(nid, 0)
        raw_x = start_x + rx * dx
        raw_y = y_coords.get(nid, baseline_y)

        snapped_x = round(raw_x / grid_snap) * grid_snap
        snapped_y = round(raw_y / grid_snap) * grid_snap
        positions[nid] = (snapped_x, snapped_y)

    return positions, topo_order


class AutoLayoutPlugin(Plugin):
    name = "Auto Layout"
    version = "1.0"

    def on_enable(self):
        # Биндим горячую клавишу Ctrl+L
        if hasattr(self.editor, 'bind'):
            self.editor.bind("<Control-l>", self.run_auto_layout)
            self.editor.bind("<Control-L>", self.run_auto_layout)

    def on_event(self, event_type, data=None):
        if event_type == 'setup_ui':
            self.add_ui_elements(data)

    def add_ui_elements(self, toolbar):
        if not tk:
            return

        # Добавляем кнопку на тулбар справа
        parent = getattr(self.editor, 'toolbar_right', toolbar)
        tk.Button(
            parent,
            text="📐 Расставить ноды",
            command=self.run_auto_layout,
            bg='#1f618d',
            activebackground='#2980b9',
            fg='white',
            activeforeground='white',
            relief='flat',
            font=('Segoe UI', 9, 'bold'),
            padx=8,
            pady=3,
            cursor='hand2'
        ).pack(side=tk.RIGHT, padx=3)

        # Добавляем в dev_menu (Меню)
        if hasattr(self.editor, 'dev_menu') and self.editor.dev_menu:
            self.editor.dev_menu.add_separator()
            self.editor.dev_menu.add_command(
                label="📐 Авто-расстановка нод (Ctrl+L)",
                command=self.run_auto_layout
            )

    def run_auto_layout(self, event=None):
        if not getattr(self.editor, 'nodes', None):
            if messagebox:
                messagebox.showinfo("Авто-расстановка", "Проект пуст, нечего расставлять.")
            return

        # Сохраняем состояние для Undo (Ctrl+Z)
        if hasattr(self.editor, 'save_state'):
            self.editor.save_state()

        positions, _ = compute_auto_layout(self.editor.nodes, self.editor.connections)

        for node in self.editor.nodes:
            nid = str(node.id)
            if nid in positions:
                node.x, node.y = positions[nid]

        if hasattr(self.editor, 'redraw'):
            self.editor.redraw()

        if hasattr(self.editor, 'set_dirty'):
            self.editor.set_dirty(True)

        if messagebox:
            messagebox.showinfo("Успех", f"Ноды ({len(self.editor.nodes)}) успешно выровнены по сетке!")


def format_json_file(file_path):
    """
    Применяет алгоритм авто-расстановки к указанному JSON файлу,
    сохраняя все свойства и упорядочивая ноды топологически.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    nodes = data.get('nodes', [])
    connections = data.get('connections', [])

    positions, topo_order = compute_auto_layout(nodes, connections)

    # Применяем новые координаты
    nodes_by_id = {str(n['id']): n for n in nodes}
    for nid, pos in positions.items():
        if nid in nodes_by_id:
            nodes_by_id[nid]['x'] = int(pos[0])
            nodes_by_id[nid]['y'] = int(pos[1])

    # Упорядочиваем массив нод в топологическом порядке
    ordered_nodes = []
    seen = set()
    for nid in topo_order:
        if nid in nodes_by_id and nid not in seen:
            ordered_nodes.append(nodes_by_id[nid])
            seen.add(nid)

    # Добавляем любые оставшиеся ноды
    for n in nodes:
        nid = str(n['id'])
        if nid not in seen:
            ordered_nodes.append(n)
            seen.add(nid)

    result_data = {
        "nodes": ordered_nodes,
        "connections": connections
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=4, ensure_ascii=False)

    print(f"[AutoLayout] Successfully arranged {len(ordered_nodes)} nodes in '{file_path}'")


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else r'd:\projects\Violant\game\violant.json'
    format_json_file(target)
