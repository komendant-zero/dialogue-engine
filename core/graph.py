"""
Dialogue Engine - Core Graph Logic.
Инкапсулирует операции над графом узлов, поиск путей, валидацию связей и циклов.
"""

from __future__ import annotations
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from core.models import ConnectionData, GraphIssue, NodeData, ProjectData


class GraphModel:
    """Модель графа диалогов и сценариев."""

    def __init__(self, project_data: Optional[ProjectData] = None):
        self._nodes: Dict[str, NodeData] = {}
        self._connections: List[ConnectionData] = []
        if project_data:
            self.load_from_project_data(project_data)

    @property
    def nodes(self) -> List[NodeData]:
        return list(self._nodes.values())

    @property
    def connections(self) -> List[ConnectionData]:
        return list(self._connections)

    def clear(self) -> None:
        self._nodes.clear()
        self._connections.clear()

    def add_node(self, node: NodeData) -> NodeData:
        self._nodes[node.id] = node
        return node

    def remove_node(self, node_id: str) -> Optional[NodeData]:
        if node_id not in self._nodes:
            return None
        node = self._nodes.pop(node_id)
        self._connections = [
            c for c in self._connections
            if c.from_node != node_id and c.to_node != node_id
        ]
        return node

    def get_node(self, node_id: str) -> Optional[NodeData]:
        return self._nodes.get(node_id)

    def add_connection(self, from_node: str, out_idx: int, to_node: str) -> bool:
        if from_node not in self._nodes or to_node not in self._nodes:
            return False

        # Удаляем существующую связь с того же выхода, если выход моногамный
        self._connections = [
            c for c in self._connections
            if not (c.from_node == from_node and c.out_idx == out_idx)
        ]
        self._connections.append(ConnectionData(from_node=from_node, out_idx=out_idx, to_node=to_node))
        return True

    def remove_connection(self, from_node: str, out_idx: int, to_node: Optional[str] = None) -> bool:
        initial_len = len(self._connections)
        if to_node is not None:
            self._connections = [
                c for c in self._connections
                if not (c.from_node == from_node and c.out_idx == out_idx and c.to_node == to_node)
            ]
        elif out_idx == -1:
            # Удалить все исходящие связи узла
            self._connections = [c for c in self._connections if c.from_node != from_node]
        else:
            self._connections = [
                c for c in self._connections
                if not (c.from_node == from_node and c.out_idx == out_idx)
            ]
        return len(self._connections) < initial_len

    def remove_incoming_connections(self, node_id: str) -> bool:
        initial_len = len(self._connections)
        self._connections = [c for c in self._connections if c.to_node != node_id]
        return len(self._connections) < initial_len

    def get_outgoing(self, node_id: str) -> List[ConnectionData]:
        return [c for c in self._connections if c.from_node == node_id]

    def get_incoming(self, node_id: str) -> List[ConnectionData]:
        return [c for c in self._connections if c.to_node == node_id]

    def get_start_nodes(self) -> List[NodeData]:
        """Возвращает список возможных стартовых узлов (узлы без входящих связей или с заголовком start)."""
        if not self._nodes:
            return []

        # 1. Приоритет: явные узлы 'start'
        named_starts = [
            n for n in self._nodes.values()
            if n.title.strip().lower() in ("start", "старт", "начало")
        ]
        if named_starts:
            return named_starts

        # 2. Узлы без входящих связей
        target_ids = {c.to_node for c in self._connections}
        roots = [n for nid, n in self._nodes.items() if nid not in target_ids]
        if roots:
            return roots

        # 3. Фолбэк: первый созданный узел
        return [next(iter(self._nodes.values()))]

    def get_reachable_nodes(self, start_node_id: Optional[str] = None) -> Set[str]:
        """Возвращает ID всех узлов, достижимых из стартовой точки."""
        if not self._nodes:
            return set()

        start_ids: List[str] = []
        if start_node_id and start_node_id in self._nodes:
            start_ids = [start_node_id]
        else:
            start_ids = [n.id for n in self.get_start_nodes()]

        visited: Set[str] = set()
        queue = deque(start_ids)

        out_map: Dict[str, List[str]] = defaultdict(list)
        for c in self._connections:
            out_map[c.from_node].append(c.to_node)

        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)
            for neighbor in out_map.get(curr, []):
                if neighbor not in visited and neighbor in self._nodes:
                    queue.append(neighbor)

        return visited

    def get_unreachable_nodes(self) -> List[NodeData]:
        """Возвращает список узлов, изолированных от основного графа."""
        reachable = self.get_reachable_nodes()
        return [n for nid, n in self._nodes.items() if nid not in reachable]

    def detect_cycles(self) -> List[List[str]]:
        """Находит циклы в графе (полезно для предупреждения о бесконечных рекурсиях)."""
        adj: Dict[str, List[str]] = defaultdict(list)
        for c in self._connections:
            adj[c.from_node].append(c.to_node)

        visited: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited
        cycles: List[List[str]] = []
        path: List[str] = []

        def dfs(node_id: str):
            visited[node_id] = 1
            path.append(node_id)
            for neighbor in adj.get(node_id, []):
                if neighbor not in self._nodes:
                    continue
                state = visited.get(neighbor, 0)
                if state == 1:
                    cycle_start = path.index(neighbor)
                    cycles.append(list(path[cycle_start:] + [neighbor]))
                elif state == 0:
                    dfs(neighbor)
            path.pop()
            visited[node_id] = 2

        for nid in self._nodes:
            if visited.get(nid, 0) == 0:
                dfs(nid)

        return cycles

    def validate(self) -> List[GraphIssue]:
        """Комплексная диагностика целостности графа."""
        issues: List[GraphIssue] = []

        if not self._nodes:
            issues.append(GraphIssue(level="warning", message="Граф пуст. Добавьте узлы."))
            return issues

        start_nodes = self.get_start_nodes()
        if not start_nodes:
            issues.append(GraphIssue(level="error", message="Не найдена стартовая точка графа."))

        # 1. Проверка битых связей
        for c in self._connections:
            if c.from_node not in self._nodes:
                issues.append(GraphIssue(
                    level="error",
                    message=f"Связь указывает из несуществующего узла: {c.from_node}",
                    details=c.to_dict()
                ))
            if c.to_node not in self._nodes:
                issues.append(GraphIssue(
                    level="error",
                    message=f"Связь указывает в несуществующий узел: {c.to_node}",
                    details=c.to_dict()
                ))

        # 2. Проверка недостижимых узлов
        unreachable = self.get_unreachable_nodes()
        for node in unreachable:
            issues.append(GraphIssue(
                level="warning",
                message=f"Узел '{node.title or node.id}' недостижим из стартовой точки.",
                node_id=node.id
            ))

        # 3. Проверка пропущенных веток выбора
        for node in self._nodes.values():
            if node.node_type == "choice":
                lines = [l.strip() for l in node.content.split("\n") if l.strip()]
                connected_indices = {c.out_idx for c in self.get_outgoing(node.id)}
                for idx in range(len(lines)):
                    if idx not in connected_indices:
                        issues.append(GraphIssue(
                            level="warning",
                            message=f"Выбор '{node.title}': вариант #{idx+1} ('{lines[idx]}') не имеет связи.",
                            node_id=node.id,
                            details={"choice_index": idx}
                        ))
            elif node.node_type == "condition":
                connected_indices = {c.out_idx for c in self.get_outgoing(node.id)}
                if 0 not in connected_indices:
                    issues.append(GraphIssue(
                        level="warning",
                        message=f"Условие '{node.title}': ветка ИСТИНА (True) не соединена.",
                        node_id=node.id
                    ))
                if 1 not in connected_indices:
                    issues.append(GraphIssue(
                        level="warning",
                        message=f"Условие '{node.title}': ветка ЛОЖЬ (False) не соединена.",
                        node_id=node.id
                    ))

        return issues

    def to_project_data(self, title: str = "Новый проект") -> ProjectData:
        return ProjectData(
            nodes=self.nodes,
            connections=self.connections
        )

    def load_from_project_data(self, project: ProjectData) -> None:
        self.clear()
        for node in project.nodes:
            self._nodes[node.id] = node
        for conn in project.connections:
            if conn.from_node in self._nodes and conn.to_node in self._nodes:
                self._connections.append(conn)
