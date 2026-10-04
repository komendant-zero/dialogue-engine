"""
Dialogue Engine - Core Package.
"""

from core.models import NodeData, ConnectionData, ProjectData, ProjectMetadata, GraphIssue
from core.graph import GraphModel
from core.serialization import ProjectSerializer, SerializationError
from core.history import HistoryManager
from core.autosave import AutosaveManager

__all__ = [
    "NodeData",
    "ConnectionData",
    "ProjectData",
    "ProjectMetadata",
    "GraphIssue",
    "GraphModel",
    "ProjectSerializer",
    "SerializationError",
    "HistoryManager",
    "AutosaveManager",
]
