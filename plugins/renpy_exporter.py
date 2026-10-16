"""
Dialogue Engine - Ren'Py Exporter Plugin.
Delegates to core.export.RenPyExporter while integrating with UI and Editor events.
"""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional

from core.models import ConnectionData, NodeData, ProjectData
from export.renpy_exporter import RenPyExporter
from plugin_system.base import Plugin


class RenpyExporterPlugin(Plugin):
    name = "Renpy Exporter"
    version = "2.1"

    def __init__(self, editor: Any = None):
        super().__init__(editor)
        pm = getattr(editor, "plugin_manager", None) if editor else None
        self.exporter = RenPyExporter(plugin_manager=pm)

    def on_event(self, event_type: str, data: Any = None) -> None:
        if event_type == "setup_ui":
            self.add_toolbar_button(data)

    def add_toolbar_button(self, toolbar: Any) -> None:
        parent = getattr(self.editor, "toolbar_right", toolbar)
        tk.Button(
            parent,
            text="⚙ Экспорт Ren'Py",
            command=self.export_project,
            bg="#8a2318",
            activebackground="#a93226",
            fg="white",
            activeforeground="white",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=3,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=3)

    def export_project(self) -> None:
        nodes = getattr(self.editor, "nodes", [])
        connections = getattr(self.editor, "connections", [])

        if not nodes:
            messagebox.showwarning("Пусто", "Проект пуст! Добавьте блоки для экспорта.")
            return

        export_dir = filedialog.askdirectory(title="Выберите папку game вашего проекта Ren'Py")
        if not export_dir:
            return

        success, msg = self.do_export(export_dir, nodes, connections)
        if success:
            messagebox.showinfo("Успех", msg)
        else:
            messagebox.showerror("Ошибка", msg)

    def do_export(self, export_dir: str, nodes: List[Any], connections: List[Any]) -> tuple[bool, str]:
        if hasattr(self.editor, "plugin_manager"):
            self.exporter.plugin_manager = self.editor.plugin_manager

        node_datas: List[NodeData] = []
        for n in nodes:
            if hasattr(n, "to_node_data"):
                node_datas.append(n.to_node_data())
            elif isinstance(n, NodeData):
                node_datas.append(n)
            elif isinstance(n, dict):
                node_datas.append(NodeData.from_dict(n))
            else:
                node_datas.append(NodeData(
                    id=getattr(n, "id", ""),
                    x=getattr(n, "x", 0.0),
                    y=getattr(n, "y", 0.0),
                    title=getattr(n, "title", ""),
                    content=getattr(n, "content", ""),
                    node_type=getattr(n, "node_type", "story"),
                    mode=getattr(n, "mode", "standard"),
                    custom_data=getattr(n, "custom_data", {})
                ))

        conn_datas: List[ConnectionData] = []
        for c in connections:
            if isinstance(c, ConnectionData):
                conn_datas.append(c)
            elif isinstance(c, dict):
                conn_datas.append(ConnectionData.from_dict(c))
            else:
                conn_datas.append(ConnectionData(
                    from_node=getattr(c, "from_node", getattr(c, "from", "")),
                    out_idx=getattr(c, "out_idx", 0),
                    to_node=getattr(c, "to_node", getattr(c, "to", ""))
                ))

        project = ProjectData(nodes=node_datas, connections=conn_datas)
        return self.exporter.export(project, export_dir)

    def clean_rel_path(self, path: str, export_dir: str = "") -> str:
        return self.exporter.clean_rel_path(path, export_dir)

    def should_pause_after_media(self, node: Any, connections: List[Any], nodes_map: Optional[Dict[str, Any]] = None) -> bool:
        conn_datas = [c if isinstance(c, ConnectionData) else ConnectionData.from_dict(c) for c in connections]
        node_data = node if isinstance(node, NodeData) else (node.to_node_data() if hasattr(node, "to_node_data") else NodeData(id=node.id, title=node.title, content=node.content, node_type=node.node_type, custom_data=getattr(node, "custom_data", {})))
        nm: Dict[str, NodeData] = {}
        if nodes_map:
            for k, v in nodes_map.items():
                nm[k] = v if isinstance(v, NodeData) else (v.to_node_data() if hasattr(v, "to_node_data") else NodeData(id=v.id, title=v.title, content=v.content, node_type=v.node_type, custom_data=getattr(v, "custom_data", {})))
        return self.exporter.should_pause_after_media(node_data, conn_datas, nm)

    def write_node_content_default(self, f: Any, node: Any, connections: List[Any], export_dir: str = "", nodes_map: Optional[Dict[str, Any]] = None) -> None:
        conn_datas = [c if isinstance(c, ConnectionData) else ConnectionData.from_dict(c) for c in connections]
        node_data = node if isinstance(node, NodeData) else (node.to_node_data() if hasattr(node, "to_node_data") else NodeData(id=node.id, title=node.title, content=node.content, node_type=node.node_type, custom_data=getattr(node, "custom_data", {})))
        nm = None
        if nodes_map:
            nm = {k: v if isinstance(v, NodeData) else (v.to_node_data() if hasattr(v, "to_node_data") else NodeData(id=v.id, title=v.title, content=v.content, node_type=v.node_type, custom_data=getattr(v, "custom_data", {}))) for k, v in nodes_map.items()}
        return self.exporter.write_node_content_default(f, node_data, conn_datas, output_dir=export_dir, nodes_map=nm)

    def write_jump(self, f: Any, node_id: str, connections: List[Any]) -> None:
        conn_datas = [c if isinstance(c, ConnectionData) else ConnectionData.from_dict(c) for c in connections]
        return self.exporter.write_jump(f, node_id, conn_datas)
