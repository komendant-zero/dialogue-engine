"""
Dialogue Engine - Core Data Models.
Содержит dataclass-структуры для чистого представления узлов, соединений и проекта.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


CURRENT_FORMAT_VERSION = "2.0"
ENGINE_VERSION = "2.0.0"


@dataclass
class ConnectionData:
    """Представление связи между выходным портом одного узла и входным портом другого."""
    from_node: str
    out_idx: int
    to_node: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_node,
            "out_idx": self.out_idx,
            "to": self.to_node
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConnectionData:
        return cls(
            from_node=str(data.get("from", "")),
            out_idx=int(data.get("out_idx", 0)),
            to_node=str(data.get("to", ""))
        )


@dataclass
class NodeData:
    """Представление данных одного узла графа."""
    id: str = field(default_factory=lambda: str(uuid.uuid4().int)[:13])
    x: float = 0.0
    y: float = 0.0
    width: float = 180.0
    height: float = 100.0
    title: str = ""
    content: str = ""
    node_type: str = "story"
    mode: str = "standard"
    custom_data: Dict[str, Any] = field(default_factory=dict)
    is_character: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        is_char = self.is_character
        if is_char is None:
            is_char = not self.title.startswith('#') if self.title else False

        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "title": self.title,
            "content": self.content,
            "type": self.node_type,
            "mode": self.mode,
            "custom_data": dict(self.custom_data),
            "is_character": is_char
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NodeData:
        return cls(
            id=str(data.get("id", str(uuid.uuid4().int)[:13])),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            title=str(data.get("title", "")),
            content=str(data.get("content", "")),
            node_type=str(data.get("type", "story")),
            mode=str(data.get("mode", "standard")),
            custom_data=dict(data.get("custom_data", {})),
            is_character=data.get("is_character")
        )


@dataclass
class ProjectMetadata:
    """Метаданные проекта."""
    format_version: str = CURRENT_FORMAT_VERSION
    engine_version: str = ENGINE_VERSION
    title: str = "Новый проект"
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format_version": self.format_version,
            "engine_version": self.engine_version,
            "title": self.title,
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> ProjectMetadata:
        if not data:
            return cls()
        return cls(
            format_version=str(data.get("format_version", CURRENT_FORMAT_VERSION)),
            engine_version=str(data.get("engine_version", ENGINE_VERSION)),
            title=str(data.get("title", "Новый проект")),
            created_at=float(data.get("created_at", time.time())),
            modified_at=float(data.get("modified_at", time.time()))
        )


@dataclass
class ProjectData:
    """Полное представление проекта со всеми узлами, связями и метаданными."""
    nodes: List[NodeData] = field(default_factory=list)
    connections: List[ConnectionData] = field(default_factory=list)
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "nodes": [n.to_dict() for n in self.nodes],
            "connections": [c.to_dict() for c in self.connections]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectData:
        meta = ProjectMetadata.from_dict(data.get("metadata"))
        nodes = [NodeData.from_dict(nd) for nd in data.get("nodes", [])]
        conns = [ConnectionData.from_dict(cd) for cd in data.get("connections", [])]
        return cls(nodes=nodes, connections=conns, metadata=meta)


@dataclass
class GraphIssue:
    """Диагностическая запись анализа графа."""
    level: str  # "error", "warning", "info"
    message: str
    node_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
