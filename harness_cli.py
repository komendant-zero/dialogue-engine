"""
Dialogue Engine - Harness CLI Runner.
Утилита командной строки для автоматического тестирования сценариев и ассетов.
Пример запуска:
    python harness_cli.py violant.json
    python harness_cli.py violant.json --markdown report.md
    python harness_cli.py violant.json --strict
"""

from __future__ import annotations
import argparse
import os
import sys

# UTF-8 fix for Windows console
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from harness import run_audit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dialogue Engine Scenario & Asset Test Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "project",
        nargs="?",
        default="violant.json",
        help="Путь к файлу проекта .json (по умолчанию: violant.json)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести отчёт в формате JSON"
    )
    parser.add_argument(
        "--markdown",
        metavar="FILE",
        help="Сохранить отчёт в файл Markdown (.md)"
    )
    parser.add_argument(
        "--log",
        metavar="FILE",
        default="audit.log",
        help="Путь к файлу лога (по умолчанию: audit.log)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Возвращать код ошибки 1, если найдены критические ошибки или warnings"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Вывести только краткую сводку без полного списка проблем"
    )

    args = parser.parse_args()

    project_path = args.project
    if not os.path.exists(project_path):
        # Пробуем искать в текущей директории
        candidate = os.path.join(SCRIPT_DIR, project_path)
        if os.path.exists(candidate):
            project_path = candidate
        else:
            print(f"❌ Ошибка: файл проекта '{project_path}' не найден!")
            return 2

    try:
        report = run_audit(project_path)
    except Exception as e:
        print(f"❌ Критическая ошибка при загрузке или аудите проекта: {e}")
        import traceback
        traceback.print_exc()
        return 2

    # Сохранение в Markdown
    if args.markdown:
        try:
            with open(args.markdown, "w", encoding="utf-8") as f:
                f.write(report.to_markdown())
            print(f"📝 Отчёт успешно сохранён в: {os.path.abspath(args.markdown)}")
        except Exception as e:
            print(f"⚠️ Не удалось записать Markdown-отчёт: {e}")

    # Автоматическое сохранение в audit.log
    if getattr(args, "log", None) == "audit.log":
        log_file = os.path.join(os.path.dirname(os.path.abspath(project_path)), "audit.log")
    else:
        log_file = args.log if getattr(args, "log", None) else "audit.log"
    log_saved_path = report.save_log(log_file)

    # Вывод результатов
    if args.json:
        print(report.to_json())
    elif args.summary:
        s = report.summary()
        status = "ПРОЙДЕН" if report.is_passed else "ОШИБКИ"
        print(f"Статус: {status} | Критических: {s['critical']} | Ошибок: {s['error']} | Предупреждений: {s['warning']} | Концовок: {s['endings_count']}")
        print(f"📄 Лог сохранён: {log_saved_path}")
    else:
        print(report.to_text())
        print(f"\n📄 Полный лог проверки сохранён в: {log_saved_path}")

    if args.strict and not report.is_passed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
