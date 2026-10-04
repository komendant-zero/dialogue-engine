"""
Dialogue Engine - Plugin Event Constants.
"""

# UI & Lifecycle
EVENT_SETUP_UI = "setup_ui"
EVENT_CONTEXT_MENU = "context_menu"
EVENT_AUTOSAVE_TICK = "autosave_tick"
EVENT_PROJECT_LOADED = "project_loaded"
EVENT_PROJECT_SAVED = "project_saved"

# Node Lifecycle
EVENT_NODE_ADDED = "node_added"
EVENT_NODE_DELETED = "node_deleted"
EVENT_NODE_EDIT_DIALOG = "node_edit_dialog"
EVENT_NODE_EDIT_SAVE = "node_edit_save"

# Node Rendering & Layout
EVENT_DRAW_NODE = "draw_node"
EVENT_DRAW_NODE_CONTENT = "draw_node_content"
EVENT_DRAW_NODE_PORTS = "draw_node_ports"
EVENT_CALCULATE_NODE_SIZE = "calculate_node_size"

# Ren'Py Exporter
EVENT_RENPY_EXPORT_INIT = "renpy_export_init"
EVENT_RENPY_EXPORT_CHECK = "renpy_export_check"
EVENT_RENPY_EXPORT_NODE = "renpy_export_node"
