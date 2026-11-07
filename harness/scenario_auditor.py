"""
Dialogue Engine - Scenario & Asset Auditor Engine.
Выполняет глубокое автоматическое тестирование сюжетного графа, ассетов,
развилок выборов, условий, реплик персонажей и целостности медиа.
"""

from __future__ import annotations
import collections
from collections import defaultdict, deque
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from core.characters import CharacterManager
from core.models import CharacterData, ConnectionData, NodeData, ProjectData
from core.serialization import ProjectSerializer
from core.sprites import SpriteResolver
from harness.models import (
    AuditIssue,
    AuditReport,
    IssueCategory,
    IssueSeverity,
    RouteEnding,
)


class ScenarioAuditor:
    """Движок автоматического аудита сценария и всех связанных ассетов."""

    # Известные маркеры концовок в репликах и заголовках
    ENDING_KEYWORDS = (
        "конец", "финал", "ending", "end", "эпилог", "game over", "gameover",
        "титры", "credits", "true end", "bad end", "good end", "death"
    )

    def __init__(
        self,
        project_data: ProjectData,
        project_file_path: Optional[str] = None,
        asset_roots: Optional[Dict[str, str]] = None
    ):
        self.project = project_data
        self.project_file_path = project_file_path
        self.asset_roots: Dict[str, str] = asset_roots or self._discover_asset_roots()

        # Индексированные структуры для быстрого поиска
        self.nodes_map: Dict[str, NodeData] = {n.id: n for n in self.project.nodes}
        self.connections: List[ConnectionData] = list(self.project.connections)

        self.outgoing_map: Dict[str, List[ConnectionData]] = defaultdict(list)
        self.incoming_map: Dict[str, List[ConnectionData]] = defaultdict(list)
        for c in self.connections:
            self.outgoing_map[c.from_node].append(c)
            self.incoming_map[c.to_node].append(c)

    def _discover_asset_roots(self) -> Dict[str, str]:
        """Автоматически находит директории ресурсов (спрайты, музыка, звуки, фоны)."""
        roots: Dict[str, str] = {
            "sprites": "",
            "backgrounds": "",
            "music": "",
            "sounds": "",
            "voice": "",
        }

        # 1. Из fs_settings.json
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        de_root = os.path.dirname(cur_dir)
        cfg_paths = [
            os.path.join(de_root, "plugins", "fs_settings.json"),
            os.path.join(os.getcwd(), "plugins", "fs_settings.json"),
        ]
        for cfg in cfg_paths:
            if os.path.exists(cfg):
                try:
                    with open(cfg, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for key in ("sprites", "backgrounds", "music", "sounds", "voice"):
                            if data.get(key) and os.path.exists(data[key]):
                                roots[key] = os.path.abspath(data[key])
                except Exception:
                    pass

        # 2. Поиск стандартной структуры Ren'Py проекта (game/sprite, game/bg, etc.)
        candidate_game_dirs = [
            r"D:\projects\Violant\game",
        ]
        if self.project_file_path:
            pdir = os.path.dirname(os.path.abspath(self.project_file_path))
            candidate_game_dirs.extend([
                pdir,
                os.path.join(pdir, "game"),
                os.path.join(pdir, "..", "game"),
            ])

        for gdir in candidate_game_dirs:
            if os.path.exists(gdir):
                m_sprite = os.path.join(gdir, "sprite")
                if not roots["sprites"] and os.path.exists(m_sprite):
                    roots["sprites"] = m_sprite

                m_bg = os.path.join(gdir, "bg")
                if not roots["backgrounds"] and os.path.exists(m_bg):
                    roots["backgrounds"] = m_bg

                m_music = os.path.join(gdir, "music")
                if not roots["music"] and os.path.exists(m_music):
                    roots["music"] = m_music

                m_sound = os.path.join(gdir, "sound")
                if not roots["sounds"] and os.path.exists(m_sound):
                    roots["sounds"] = m_sound

                m_voice = os.path.join(gdir, "voice")
                if not roots["voice"] and os.path.exists(m_voice):
                    roots["voice"] = m_voice

        return roots

    # =========================================================================
    # ГЛАВНЫЙ ЗАПУСК АУДИТА
    # =========================================================================

    def run_full_audit(self, auto_save_log: bool = True) -> AuditReport:
        """Выполняет полную проверку сценария, автоматически пишет в audit.log и возвращает готовый AuditReport."""
        proj_name = (
            os.path.basename(self.project_file_path)
            if self.project_file_path
            else "Сценарий"
        )
        report = AuditReport(
            project_name=proj_name,
            total_nodes=len(self.nodes_map),
            total_connections=len(self.connections),
        )

        # Подсчёт типов узлов
        type_counts: Dict[str, int] = defaultdict(int)
        for n in self.nodes_map.values():
            type_counts[n.node_type] += 1
        report.node_type_counts = dict(type_counts)

        # 1. Проверка структуры и топологии графа
        start_nodes = self._audit_graph_flow(report)

        # 2. Проверка выборов и развилок
        self._audit_choices(report)

        # 3. Проверка условий и переменных
        self._audit_conditions_and_variables(report)

        # 4. Проверка диалогов и персонажей
        self._audit_characters_and_dialogues(report)

        # 5. Проверка целостности ассетов на диске
        self._audit_assets(report)

        # 6. Симуляция прохождений, метрики и расчёт концовок
        self._simulate_routes_and_metrics(report, start_nodes)

        # 7. Автоматическое сохранение в audit.log
        if auto_save_log:
            try:
                pdir = os.path.dirname(os.path.abspath(self.project_file_path)) if self.project_file_path else os.getcwd()
                log_file = os.path.join(pdir, "audit.log")
                report.save_log(log_file)
            except Exception:
                pass

        return report

    # =========================================================================
    # 1. ТОПОЛОГИЯ ГРАФА И ПОВЕСТВОВАНИЕ
    # =========================================================================

    def _audit_graph_flow(self, report: AuditReport) -> List[NodeData]:
        if not self.nodes_map:
            report.issues.append(AuditIssue(
                severity=IssueSeverity.CRITICAL,
                category=IssueCategory.GRAPH_FLOW,
                message="Сценарий пуст: в проекте нет ни одного узла.",
                suggestion="Добавьте стартовый сюжетный узел с заголовком 'start'."
            ))
            return []

        # Поиск стартовых точек
        start_nodes: List[NodeData] = [
            n for n in self.nodes_map.values()
            if n.title.strip().lower() in ("start", "старт", "начало", "prologue", "пролог")
            or (n.node_type == "label" and "start" in n.title.lower())
        ]

        if not start_nodes:
            # Ищем узлы с нулевым числом входящих связей
            zero_in = [n for nid, n in self.nodes_map.items() if len(self.incoming_map[nid]) == 0]
            if not zero_in:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.GRAPH_FLOW,
                    message="В графе не найдена стартовая точка (нет узлов без входа и нет узла 'start').",
                    suggestion="Переименуйте заголовок начального узла в 'start'."
                ))
                start_nodes = [next(iter(self.nodes_map.values()))]
            else:
                start_nodes = zero_in
                if len(zero_in) > 1:
                    report.issues.append(AuditIssue(
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.GRAPH_FLOW,
                        message=f"Найдено {len(zero_in)} независимых точек входа без входящих связей.",
                        suggestion="Назовите главный стартовый узел 'start', чтобы однозначно задать начало."
                    ))

        # Проверка битых связей (ссылающихся на удалённые узлы)
        for c in self.connections:
            if c.from_node not in self.nodes_map:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.GRAPH_FLOW,
                    message=f"Связь исходит из несуществующего узла '{c.from_node}'.",
                    suggestion="Удалите повреждённую связь.",
                    details=c.to_dict()
                ))
            if c.to_node not in self.nodes_map:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.GRAPH_FLOW,
                    node_id=c.from_node,
                    node_title=self.nodes_map.get(c.from_node, NodeData()).title,
                    message=f"Связь ведёт в несуществующий узел '{c.to_node}'.",
                    suggestion="Перенаправьте связь в корректный узел или удалите её.",
                    details=c.to_dict()
                ))

        # Обход достижимости (Reachable Nodes)
        reachable: Set[str] = set()
        queue = deque(n.id for n in start_nodes if n.id in self.nodes_map)
        while queue:
            curr_id = queue.popleft()
            if curr_id in reachable:
                continue
            reachable.add(curr_id)
            for conn in self.outgoing_map.get(curr_id, []):
                if conn.to_node in self.nodes_map and conn.to_node not in reachable:
                    queue.append(conn.to_node)

        # Выявление недостижимых узлов (Orphans)
        unreachable = [n for nid, n in self.nodes_map.items() if nid not in reachable]
        if unreachable:
            for un in unreachable:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.GRAPH_FLOW,
                    node_id=un.id,
                    node_title=un.title,
                    message=f"Узел '{un.title or un.id}' изолирован: до него нельзя дойти из начала истории.",
                    suggestion="Соедините узел с предшествующим блоком или удалите его, если он больше не нужен."
                ))

        # Поиск бесконечных тупиковых циклов (без узла выбора внутри)
        self._detect_trapping_cycles(report)

        return start_nodes

    def _detect_trapping_cycles(self, report: AuditReport) -> None:
        """Находит циклические петли, из которых игрок не может выбраться."""
        adj: Dict[str, List[str]] = defaultdict(list)
        for c in self.connections:
            if c.from_node in self.nodes_map and c.to_node in self.nodes_map:
                adj[c.from_node].append(c.to_node)

        visited: Dict[str, int] = {}
        path: List[str] = []
        found_cycles: List[List[str]] = []

        def dfs(nid: str):
            visited[nid] = 1
            path.append(nid)
            for nxt in adj.get(nid, []):
                state = visited.get(nxt, 0)
                if state == 1:
                    cycle_start = path.index(nxt)
                    found_cycles.append(list(path[cycle_start:]))
                elif state == 0:
                    dfs(nxt)
            path.pop()
            visited[nid] = 2

        for node_id in self.nodes_map:
            if visited.get(node_id, 0) == 0:
                dfs(node_id)

        # Анализируем найденные циклы: есть ли в цикле выбор или узел выхода
        for cycle in found_cycles[:5]:  # Ограничиваем первыми 5 циклами
            has_exit = False
            has_choice = False
            cycle_set = set(cycle)
            for cid in cycle:
                node = self.nodes_map.get(cid)
                if node and node.node_type in ("choice", "condition"):
                    has_choice = True
                for c in self.outgoing_map.get(cid, []):
                    if c.to_node not in cycle_set:
                        has_exit = True
                        break

            first_node = self.nodes_map.get(cycle[0], NodeData())
            if not has_exit:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.GRAPH_FLOW,
                    node_id=cycle[0],
                    node_title=first_node.title,
                    message=f"Бесконечная петля-ловушка из {len(cycle)} узлов без возможности выхода!",
                    suggestion="Добавьте развилку выбора или условие с выходом из цикла.",
                    details={"cycle_node_ids": cycle}
                ))
            elif not has_choice and len(cycle) <= 3:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.GRAPH_FLOW,
                    node_id=cycle[0],
                    node_title=first_node.title,
                    message=f"Циклическое повторение реплик ({len(cycle)} узлов).",
                    suggestion="Убедитесь, что зацикливание реплик было запланировано автором.",
                    details={"cycle_node_ids": cycle}
                ))

    # =========================================================================
    # 2. ВЫБОРЫ И РАЗВИЛКИ
    # =========================================================================

    def _audit_choices(self, report: AuditReport) -> None:
        for node in self.nodes_map.values():
            if node.node_type != "choice":
                continue

            lines = [l.strip() for l in node.content.split("\n") if l.strip()]
            if not lines:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.CRITICAL,
                    category=IssueCategory.CHOICES,
                    node_id=node.id,
                    node_title=node.title,
                    message="Блок выбора пуст: не задан ни один вариант ответа.",
                    suggestion="Откройте редактор блока и напишите варианты ответа с новой строки."
                ))
                continue

            outgoing = self.outgoing_map.get(node.id, [])
            connected_indices = {c.out_idx for c in outgoing}

            # Проверка не привязанных вариантов
            for idx, opt_text in enumerate(lines):
                if idx not in connected_indices:
                    report.issues.append(AuditIssue(
                        severity=IssueSeverity.CRITICAL,
                        category=IssueCategory.CHOICES,
                        node_id=node.id,
                        node_title=node.title,
                        message=f"Вариант #{idx + 1} '{opt_text}' не соединён с продолжением сценария!",
                        suggestion=f"Протяните связь от порта #{idx + 1} к следующей реплике или сцене.",
                        details={"choice_index": idx, "option_text": opt_text}
                    ))

            # Проверка связей с несуществующими индексами
            for c in outgoing:
                if c.out_idx >= len(lines):
                    report.issues.append(AuditIssue(
                        severity=IssueSeverity.ERROR,
                        category=IssueCategory.CHOICES,
                        node_id=node.id,
                        node_title=node.title,
                        message=f"Связь исходит из несуществующего варианта #{c.out_idx + 1} (в блоке всего {len(lines)} вар.).",
                        suggestion="Удалите устаревшую связь или добавьте соответствующий вариант в текст."
                    ))

            # Проверка на дублирование вариантов
            seen_options = set()
            for opt in lines:
                if opt in seen_options:
                    report.issues.append(AuditIssue(
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.CHOICES,
                        node_id=node.id,
                        node_title=node.title,
                        message=f"Дублирующийся текст варианта: '{opt}'.",
                        suggestion="Сделайте тексты вариантов выбора отличимыми для игрока."
                    ))
                seen_options.add(opt)

    # =========================================================================
    # 3. УСЛОВИЯ И ПЕРЕМЕННЫЕ
    # =========================================================================

    def _audit_conditions_and_variables(self, report: AuditReport) -> None:
        # 1. Собираем все переменные, которые где-либо задаются в сюжете
        assigned_variables: Set[str] = set()
        for node in self.nodes_map.values():
            if node.node_type == "variable":
                # Переменные могут задаваться в заголовке или контенте: flag = True
                m = re.findall(r"([a-zA-Z_]\w*)\s*=", node.content)
                assigned_variables.update(m)
                if node.title and re.match(r"^[a-zA-Z_]\w*$", node.title.strip()):
                    assigned_variables.add(node.title.strip())
            elif node.node_type == "python_code":
                m = re.findall(r"(?:\$|\b)([a-zA-Z_]\w*)\s*=", node.content)
                assigned_variables.update(m)

        # 2. Проверяем блоки условий
        for node in self.nodes_map.values():
            if node.node_type != "condition":
                continue

            outgoing = self.outgoing_map.get(node.id, [])
            out_indices = {c.out_idx for c in outgoing}

            if 0 not in out_indices:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.LOGIC,
                    node_id=node.id,
                    node_title=node.title,
                    message="Ветка ИСТИНА (True / выход 0) не имеет исходящей связи.",
                    suggestion="Протяните связь от верхнего порта выхода блока условия."
                ))

            if 1 not in out_indices:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.LOGIC,
                    node_id=node.id,
                    node_title=node.title,
                    message="Ветка ЛОЖЬ (False / выход 1) не имеет связи. Сюжет остановится, если условие не выполнено.",
                    suggestion="Протяните связь от нижнего порта выхода условия для альтернативной ветки."
                ))

            # Поиск переменных в выражении условия
            expr = f"{node.title} {node.content}".strip()
            var_candidates = set(re.findall(r"\b([a-zA-Z_]\w*)\b", expr))
            # Исключаем ключевые слова Python
            py_keywords = {"True", "False", "None", "if", "else", "and", "or", "not", "in", "is"}
            checked_vars = var_candidates - py_keywords

            for v in checked_vars:
                if assigned_variables and v not in assigned_variables:
                    report.issues.append(AuditIssue(
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.LOGIC,
                        node_id=node.id,
                        node_title=node.title,
                        message=f"Условие проверяет переменную '{v}', которая не инициализируется в явных блоках переменных.",
                        suggestion=f"Убедитесь, что переменная '{v}' определена в Ren'Py по умолчанию (default {v} = ...)."
                    ))

    # =========================================================================
    # 4. ДИАЛОГИ И ПЕРСОНАЖИ
    # =========================================================================

    def _audit_characters_and_dialogues(self, report: AuditReport) -> None:
        registered_chars = {c.name.strip().lower() for c in getattr(self.project, "characters", []) if c.name.strip()}

        for node in self.nodes_map.values():
            if node.node_type != "story":
                continue

            title = node.title.strip()
            content = node.content.strip()

            # Проверка пустых реплик
            if not content:
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.CHARACTERS,
                    node_id=node.id,
                    node_title=title,
                    message="Пустой текст реплики в сюжетном блоке.",
                    suggestion="Напишите диалог или удалите пустой блок."
                ))

            # Проверка незакрытых тегов оформления Ren'Py
            self._check_text_formatting(node, content, report)

            # Проверка персонажей
            if title and not title.startswith("#"):
                # Имя персонажа
                clean_name = title.lower()
                if registered_chars and clean_name not in registered_chars and clean_name not in ("сцена", "автор", "рассказчик", "голос"):
                    report.issues.append(AuditIssue(
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.CHARACTERS,
                        node_id=node.id,
                        node_title=title,
                        message=f"Персонаж '{title}' говорит в реплике, но не внесён в Базу Персонажей.",
                        suggestion="Добавьте персонажа в 'Базу персонажей' для единой настройки цвета и эмоций."
                    ))

    def _check_text_formatting(self, node: NodeData, text: str, report: AuditReport) -> None:
        """Проверяет синтаксис кавычек и тегов Ren'Py."""
        # Баланс тегов {b}...{/b}, {i}...{/i}, {color=...}...{/color}
        open_tags = re.findall(r"\{([a-zA-Z0-9#=_]+)\}", text)
        close_tags = re.findall(r"\{/([a-zA-Z0-9#=_]+)\}", text)

        for ot in open_tags:
            tag_name = ot.split("=")[0]
            if tag_name not in close_tags and tag_name in ("b", "i", "u", "s", "color", "size", "font"):
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.CHARACTERS,
                    node_id=node.id,
                    node_title=node.title,
                    message=f"Возможно, не закрыт текстовый тег '{{{ot}}}' в реплике.",
                    suggestion=f"Добавьте закрывающий тег '{{/{tag_name}}}'."
                ))

        # Баланс кавычек (если обычные ASCII кавычки нечётные)
        ascii_quotes_count = text.count('"') - text.count('\\"')
        if ascii_quotes_count % 2 != 0:
            report.issues.append(AuditIssue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.CHARACTERS,
                node_id=node.id,
                node_title=node.title,
                message="Непарная прямая кавычка (\") в тексте — возможна ошибка синтаксиса в Ren'Py.",
                suggestion="Проверьте правильность расстановки кавычек или экранируйте их (\\\")."
            ))

    # =========================================================================
    # 5. ЦЕЛОСТНОСТЬ АССЕТОВ (СПРАЙТЫ, АУДИО, ФОНЫ)
    # =========================================================================

    def _audit_assets(self, report: AuditReport) -> None:
        sprites_dir = self.asset_roots.get("sprites", "")
        bg_dir = self.asset_roots.get("backgrounds", "")
        music_dir = self.asset_roots.get("music", "")
        sound_dir = self.asset_roots.get("sounds", "")

        checked_sprites: Dict[Tuple[str, str], bool] = {}

        for node in self.nodes_map.values():
            # 1. Проверка спрайтов в Story нодах
            if node.node_type == "story":
                char_name = node.title.strip()
                emo = str(node.custom_data.get("emotion", "")).strip()
                explicit_sprite = str(node.custom_data.get("sprite_path", "")).strip()

                if explicit_sprite:
                    if not os.path.exists(explicit_sprite):
                        report.issues.append(AuditIssue(
                            severity=IssueSeverity.ERROR,
                            category=IssueCategory.ASSETS,
                            node_id=node.id,
                            node_title=node.title,
                            message=f"Файл спрайта не найден по указанному пути: '{explicit_sprite}'",
                            suggestion="Перепривяжите актуальный спрайт в окне редактирования блока."
                        ))
                elif char_name and emo and not char_name.startswith("#"):
                    cache_key = (char_name, emo)
                    if cache_key not in checked_sprites:
                        found_path = SpriteResolver.resolve_sprite(
                            char_name, emo, project_path=self.project_file_path
                        )
                        checked_sprites[cache_key] = bool(found_path and os.path.exists(found_path))

                    if not checked_sprites[cache_key]:
                        report.issues.append(AuditIssue(
                            severity=IssueSeverity.ERROR,
                            category=IssueCategory.ASSETS,
                            node_id=node.id,
                            node_title=node.title,
                            message=f"Не найден файл спрайта для героя '{char_name}' с эмоцией '{emo}' в '{sprites_dir}'.",
                            suggestion=f"Добавьте спрайт в папку sprite/{char_name.lower()} или выберите другую позу."
                        ))

            # 2. Проверка аудиофайлов в Music нодах
            elif node.node_type == "music":
                audio_ref = self._extract_clean_path(
                    node.custom_data.get("audio_path") or node.custom_data.get("filename") or node.content
                )
                if not audio_ref:
                    report.issues.append(AuditIssue(
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.ASSETS,
                        node_id=node.id,
                        node_title=node.title,
                        message="В аудио-блоке не указан путь к звуковому файлу.",
                        suggestion="Выберите звуковой файл в свойствах блока."
                    ))
                elif not audio_ref.startswith("#"):
                    found = self._check_media_file_exists(audio_ref, [music_dir, sound_dir])
                    if not found:
                        report.issues.append(AuditIssue(
                            severity=IssueSeverity.ERROR,
                            category=IssueCategory.ASSETS,
                            node_id=node.id,
                            node_title=node.title,
                            message=f"Аудиофайл '{audio_ref}' не обнаружен в папках music/ или sound/.",
                            suggestion=f"Поместите файл '{audio_ref}' в папку проекта или проверьте путь."
                        ))

            # 3. Проверка фонов в Media нодах
            elif node.node_type == "media":
                bg_ref = self._extract_clean_path(
                    node.custom_data.get("image_path") or node.content
                )
                if not bg_ref:
                    report.issues.append(AuditIssue(
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.ASSETS,
                        node_id=node.id,
                        node_title=node.title,
                        message="В медиа-блоке не выбран файл фонового изображения.",
                        suggestion="Выберите изображение фона в свойствах блока."
                    ))
                elif not bg_ref.startswith("#"):
                    found = self._check_media_file_exists(bg_ref, [bg_dir])
                    if not found:
                        report.issues.append(AuditIssue(
                            severity=IssueSeverity.ERROR,
                            category=IssueCategory.ASSETS,
                            node_id=node.id,
                            node_title=node.title,
                            message=f"Фоновое изображение '{bg_ref}' не найдено на диске в game/bg/.",
                            suggestion=f"Поместите файл '{bg_ref}' в папку game/bg/."
                        ))

    def _extract_clean_path(self, raw_val: Any) -> str:
        """Извлекает чистый путь к файлу из строк, JSON или служебных меток плагинов."""
        if not raw_val:
            return ""
        s = str(raw_val).strip()
        # Если строка содержит JSON
        if s.startswith("{") and s.endswith("}"):
            try:
                data = json.loads(s)
                return str(data.get("image_path") or data.get("audio_path") or data.get("filename") or "").strip()
            except Exception:
                pass

        # Если плагин записал с иконкой "📂: filename.ext"
        if "📂:" in s:
            parts = s.split("📂:", 1)
            candidate = parts[1].split("\n")[0].strip()
            return candidate

        # Удаляем команды Ren'Py вроде 'play sound "..."' или 'scene expression "..."'
        m = re.search(r'["\']([^"\']+\.(?:ogg|mp3|wav|opus|png|jpg|jpeg|webp|gif))["\']', s, re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # Первая непустая строка
        for line in s.split("\n"):
            line = line.strip().strip('"').strip("'")
            if any(line.lower().endswith(ext) for ext in (".ogg", ".mp3", ".wav", ".png", ".jpg", ".jpeg", ".webp", ".gif")):
                return line

        return s

    def _check_media_file_exists(self, filename: str, search_dirs: List[str]) -> bool:
        """Ищет файл на диске с учётом относительных путей."""
        if os.path.isabs(filename) and os.path.exists(filename):
            return True

        clean_fn = filename.replace("\\", "/").lstrip("/")

        # Проверяем в указанных директориях
        for sdir in search_dirs:
            if not sdir or not os.path.exists(sdir):
                continue

            # 1. Прямое совпадение
            direct = os.path.join(sdir, clean_fn)
            if os.path.exists(direct):
                return True

            # 2. По базовому имени
            basename = os.path.basename(clean_fn)
            base_match = os.path.join(sdir, basename)
            if os.path.exists(base_match):
                return True

            # 3. Если путь включает имя папки, например 'sound/track.ogg'
            parent_dir = os.path.dirname(sdir)
            combined = os.path.join(parent_dir, clean_fn)
            if os.path.exists(combined):
                return True

        return False

    # =========================================================================
    # 6. СИМУЛЯЦИЯ ПУТЕЙ, МЕТРИКИ И КОНЦОВКИ
    # =========================================================================

    def _simulate_routes_and_metrics(self, report: AuditReport, start_nodes: List[NodeData]) -> None:
        """Исследует все маршруты от начал до листьев, собирает метрики и список концовок."""
        if not start_nodes:
            return

        leaf_nodes: List[NodeData] = [
            n for nid, n in self.nodes_map.items()
            if len(self.outgoing_map[nid]) == 0
        ]

        total_words = 0
        char_word_counts: Dict[str, int] = defaultdict(int)
        for n in self.nodes_map.values():
            if n.content:
                wc = len(n.content.split())
                total_words += wc
                cname = n.title.strip() or "Автор"
                char_word_counts[cname] += wc

        # Обход маршрутов до листьев
        all_routes: List[Tuple[NodeData, int, int, List[str]]] = []

        for sn in start_nodes:
            # Стек для поиска в глубину (node_id, steps, words, path_titles, visited_in_path)
            stack = [(sn.id, 1, len(sn.content.split()), [sn.title or sn.id], {sn.id})]
            while stack:
                cid, steps, words, path_titles, path_set = stack.pop()
                cnode = self.nodes_map[cid]
                out_conns = self.outgoing_map.get(cid, [])

                if not out_conns:
                    # Достигли терминального листа
                    all_routes.append((cnode, steps, words, path_titles))
                else:
                    for conn in out_conns:
                        nxt_id = conn.to_node
                        if nxt_id in self.nodes_map and nxt_id not in path_set:
                            nxt_node = self.nodes_map[nxt_id]
                            nxt_w = len(nxt_node.content.split())
                            nxt_set = set(path_set)
                            nxt_set.add(nxt_id)
                            stack.append((
                                nxt_id,
                                steps + 1,
                                words + nxt_w,
                                path_titles + [nxt_node.title or nxt_id],
                                nxt_set
                            ))
                            if len(all_routes) > 1000:
                                # Защита от экспоненциального комбинаторного взрыва
                                break

        # Формируем список уникальных концовок
        endings_by_leaf: Dict[str, RouteEnding] = {}
        for leaf, steps, words, p_titles in all_routes:
            lid = leaf.id
            is_declared = self._is_ending_node(leaf)

            if lid not in endings_by_leaf:
                endings_by_leaf[lid] = RouteEnding(
                    leaf_node_id=lid,
                    leaf_title=leaf.title or leaf.id,
                    is_declared_ending=is_declared,
                    steps_count=steps,
                    words_count=words,
                    sample_path=p_titles
                )
            else:
                # Обновляем максимальную длину пути до этой концовки
                if steps > endings_by_leaf[lid].steps_count:
                    endings_by_leaf[lid].steps_count = steps
                    endings_by_leaf[lid].words_count = words
                    endings_by_leaf[lid].sample_path = p_titles

        report.endings = list(endings_by_leaf.values())

        # Проверяем листья на внезапные обрывы (Dead Ends)
        for e in report.endings:
            leaf_node = self.nodes_map.get(e.leaf_node_id)
            if not e.is_declared_ending and leaf_node and leaf_node.node_type == "story":
                report.issues.append(AuditIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.GRAPH_FLOW,
                    node_id=leaf_node.id,
                    node_title=leaf_node.title,
                    message=f"Ветка внезапно обрывается в блоке '{leaf_node.title}'. Это финал или забытая связь?",
                    suggestion="Добавьте в заголовок или текст '[Конец]' или продолжите сюжетную линию."
                ))

        # Сводные метрики проекта
        min_steps = min((e.steps_count for e in report.endings), default=0)
        max_steps = max((e.steps_count for e in report.endings), default=0)
        top_speaker = max(char_word_counts.items(), key=lambda x: x[1])[0] if char_word_counts else "—"

        report.stats = {
            "Общее число слов": f"{total_words:,}".replace(",", " "),
            "Всего маршрутов до концовок": len(all_routes),
            "Уникальных концовок": len(report.endings),
            "Минимальная длина пути": f"{min_steps} узлов",
            "Максимальная длина пути": f"{max_steps} узлов",
            "Главный говорящий": top_speaker,
            "Корень спрайтов": self.asset_roots.get("sprites") or "Не найден",
            "Корень звуков": self.asset_roots.get("sounds") or "Не найден",
            "Корень фонов": self.asset_roots.get("backgrounds") or "Не найден",
        }

    def _is_ending_node(self, node: NodeData) -> bool:
        """Определяет, позиционируется ли узел как сюжетная концовка."""
        text = f"{node.title} {node.content}".lower()
        if any(kw in text for kw in self.ENDING_KEYWORDS):
            return True
        if node.node_type == "label" and any(kw in node.title.lower() for kw in self.ENDING_KEYWORDS):
            return True
        return False
