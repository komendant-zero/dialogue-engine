"""
Dialogue Engine - Core Package.
"""

from core.models import NodeData, ConnectionData, ProjectData, ProjectMetadata, GraphIssue, CharacterData
from core.graph import GraphModel
from core.serialization import ProjectSerializer, SerializationError
from core.history import HistoryManager
from core.autosave import AutosaveManager
from core.characters import CharacterManager, DEFAULT_CHARACTER_PALETTE, DEFAULT_EMOTIONS
from core.sprites import SpriteResolver

__all__ = [
    "NodeData",
    "ConnectionData",
    "ProjectData",
    "ProjectMetadata",
    "CharacterData",
    "CharacterManager",
    "SpriteResolver",
    "DEFAULT_CHARACTER_PALETTE",
    "DEFAULT_EMOTIONS",
    "GraphIssue",
    "GraphModel",
    "ProjectSerializer",
    "SerializationError",
    "HistoryManager",
    "AutosaveManager",
]
