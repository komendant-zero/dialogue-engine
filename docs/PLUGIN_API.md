# 🧩 Dialogue Engine — Plugin Development Guide & Public API

Dialogue Engine предоставляет модульную систему плагинов, позволяющую расширять типы блоков, добавлять кастомные инструменты в UI, переопределять отрисовку и интегрироваться в процесс экспорта в Ren'Py.

---

## 1. Структура плагина

Все плагины размещаются в папке `plugins/` и наследуются от базового класса `Plugin` из модуля `plugin_system`.

```python
from plugin_system import Plugin

class MyCustomPlugin(Plugin):
    name = "My Custom Plugin"
    version = "1.0"
    author = "Ваше Имя"
    description = "Описание возможностей плагина"

    def on_enable(self):
        """Вызывается один раз при успешной загрузке плагина."""
        print(f"[{self.name}] Плагин активирован!")

    def on_disable(self):
        """Вызывается при отключении плагина."""
        pass

    def on_event(self, event_type: str, data: dict = None):
        """Обработчик событий редактора."""
        if event_type == "setup_ui":
            self.setup_my_ui(data)
```

---

## 2. Жизненный цикл и безопасность

- **Изоляция сбоев (Error Boundary):** Если в обработчике `on_event` плагина произойдет исключение, редактор изолирует ошибку, запишет её в лог и продолжит работу остальных компонентов.
- **Auto-Disable:** Если плагин вызывает несколько критических ошибок подряд, он переводится в статус `PluginStatus.ERROR` во избежание деградации производительности GUI.

---

## 3. Таблица поддерживаемых событий

| Событие | Аргумент `data` | Описание |
| :--- | :--- | :--- |
| `setup_ui` | `toolbar` (tk.Frame) | Инициализация кнопок в тулбаре редактора |
| `node_added` | `Node` | Добавление нового узла на холст |
| `node_deleted` | `Node` | Удаление узла с холста |
| `draw_node` | `{'node': Node, 'canvas': Canvas}` | Хук отрисовки дополнительных элементов поверх узла |
| `draw_node_content`| `{'node': Node, 'canvas': Canvas, 'handled': bool}` | Переопределение отрисовки тела узла |
| `draw_node_ports` | `{'node': Node, 'canvas': Canvas, 'handled': bool}` | Кастомное размещение входных портов |
| `calculate_node_size` | `{'node': Node, 'base_h': int, 'display_content': str, 'height': int, 'handled': dict}` | Расчет высоты нестандартных блоков |
| `context_menu` | `{'target': Node, 'x': float, 'y': float, 'menu': tk.Menu}` | Добавление пунктов в контекстное меню (ПКМ) |
| `node_edit_dialog` | `{'node': Node, 'frame': tk.Frame, 'dialog': tk.Toplevel}` | Встраивание кастомных настроек в окно редактирования |
| `node_edit_save` | `{'node': Node}` | Сохранение настроек из диалога в `node.custom_data` |
| `renpy_export_init` | `{'file': file, 'nodes': list, 'connections': list, 'export_dir': str}` | Экспорт глобальных определений Ren'Py (ATL, transforms, init python) |
| `renpy_export_check` | `{'node': Node, 'skip': bool}` | Возможность пропустить стандартный экспорт ноды |
| `renpy_export_node` | `{'node': Node, 'file': file, 'connections': list, 'export_dir': str, 'handled': bool}` | Генерация кастомного Ren'Py кода для ноды |
| `project_loaded` | `{'project': ProjectData}` | Завершение загрузки проекта из JSON |
| `project_saved` | `{'file': str, 'project': ProjectData}` | Завершение сохранения проекта |
| `autosave_tick` | `{'project': ProjectData}` | Срабатывание периодического автосохранения |

---

## 4. Пример: Создание кастомного типа узла

Ниже приведен полный пример плагина, добавляющего новый узел **Таймер**:

```python
import tkinter as tk
from plugin_system import Plugin

class TimerNodePlugin(Plugin):
    name = "Timer Node"
    version = "1.0"

    def on_event(self, event_type, data=None):
        if event_type == "setup_ui":
            self.add_toolbar_item()
        elif event_type == "node_edit_dialog":
            self.build_editor_ui(data)
        elif event_type == "node_edit_save":
            self.save_editor_data(data)
        elif event_type == "renpy_export_node":
            self.export_renpy(data)

    def add_toolbar_item(self):
        if hasattr(self.editor, "plugin_menu"):
            self.editor.plugin_menu.add_command(
                label="⏱️ Таймер",
                command=lambda: self.editor.add_node(
                    ntype="timer",
                    title="Таймер",
                    content="Время: 5 сек",
                    custom_data={"duration": 5.0}
                )
            )

    def build_editor_ui(self, data):
        node = data["node"]
        if node.node_type != "timer":
            return

        frame = data["frame"]
        tk.Label(frame, text="Длительность таймера (сек):", bg="#1e1e1e", fg="white").pack(anchor="w")
        e_dur = tk.Entry(frame, bg="#333", fg="white")
        e_dur.insert(0, str(node.custom_data.get("duration", 5.0)))
        e_dur.pack(fill=tk.X, pady=4)
        self._temp_entry = e_dur

    def save_editor_data(self, data):
        node = data["node"]
        if node.node_type == "timer" and hasattr(self, "_temp_entry"):
            try:
                dur = float(self._temp_entry.get())
                node.custom_data["duration"] = dur
                node.content = f"Время: {dur} сек"
            except ValueError:
                pass

    def export_renpy(self, data):
        node = data["node"]
        if node.node_type != "timer":
            return

        f = data["file"]
        dur = node.custom_data.get("duration", 5.0)
        f.write(f"    $ renpy.pause({dur}, hard=True)\n")

        conns = data.get("connections", [])
        out_conns = [c for c in conns if c["from"] == node.id]
        if out_conns:
            f.write(f"    jump node_{out_conns[0]['to']}\n")
        else:
            f.write("    return\n")

        data["handled"] = True
```

---

## 5. Рекомендации по совместимости

1. **Хранение данных:** Сохраняйте все кастомные поля исключительно в словаре `node.custom_data`. Он автоматически сериализуется в JSON и сохраняется в истории `Undo/Redo`.
2. **Пути к ресурсам:** Используйте относительные пути для ассетов или вспомогательный метод `RenPyExporter.clean_rel_path(...)`.
3. **Обновление интерфейса:** При программном изменении узлов вызывайте `self.editor.redraw()` и `self.editor.set_dirty(True)`.
