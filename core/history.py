"""
Dialogue Engine - History and Undo/Redo Manager.
Управляет стеком снимков состояния графа для безопасных операций отмены и повтора действий.
"""

from __future__ import annotations
import copy
from typing import Any, Dict, List, Optional


class HistoryManager:
    """Менеджер истории действий с поддержкой лимита глубины стека."""

    def __init__(self, max_depth: int = 50):
        self.max_depth = max_depth
        self._undo_stack: List[Dict[str, Any]] = []
        self._redo_stack: List[Dict[str, Any]] = []

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def push_state(self, state: Dict[str, Any], clear_redo: bool = True) -> None:
        """Сохраняет состояние в стек отмены."""
        # Глубокая копия состояния для предотвращения мутаций
        cloned = copy.deepcopy(state)
        self._undo_stack.append(cloned)
        if len(self._undo_stack) > self.max_depth:
            self._undo_stack.pop(0)

        if clear_redo:
            self._redo_stack.clear()

    def undo(self, current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Возвращает предыдущее состояние и сохраняет текущее в стек повтора."""
        if not self._undo_stack:
            return None

        self._redo_stack.append(copy.deepcopy(current_state))
        if len(self._redo_stack) > self.max_depth:
            self._redo_stack.pop(0)

        return self._undo_stack.pop()

    def redo(self, current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Возвращает отмененное состояние и сохраняет текущее в стек отмены."""
        if not self._redo_stack:
            return None

        self._undo_stack.append(copy.deepcopy(current_state))
        if len(self._undo_stack) > self.max_depth:
            self._undo_stack.pop(0)

        return self._redo_stack.pop()

    def pop_last_undo(self) -> Optional[Dict[str, Any]]:
        """Удаляет последний снимок без сохранения в redo (например, при отмене драга без смещения)."""
        if self._undo_stack:
            return self._undo_stack.pop()
        return None

    def clear(self) -> None:
        """Очищает историю."""
        self._undo_stack.clear()
        self._redo_stack.clear()
