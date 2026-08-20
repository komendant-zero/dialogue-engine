import tkinter as tk
from tkinter import messagebox
import urllib.request
import urllib.parse
import json
import threading
from plugin_system import Plugin

class GrammarPlugin(Plugin):
    name = "Punctuation & Grammar Checker"
    version = "1.2"

    def __init__(self, editor):
        super().__init__(editor)
        self.button = None
        self.clear_button = None

    def on_enable(self):
        pass

    def on_event(self, event_type, data):
        if event_type == 'setup_ui':
            toolbar = data
            
            # Разделитель
            tk.Label(toolbar, text="|", bg='#444', fg='#666').pack(side=tk.RIGHT, padx=2)
            
            # Кнопка очистки
            self.clear_button = tk.Button(
                toolbar, 
                text="Снять подсветку", 
                command=self.clear_highlights,
                bg='#444', 
                fg='white',
                relief='flat', 
                padx=10, 
                pady=5
            )
            self.clear_button.pack(side=tk.RIGHT, padx=2, pady=5)
            
            # Кнопка проверки
            self.button = tk.Button(
                toolbar, 
                text="Проверка пунктуации", 
                command=self.run_check,
                bg='#444', 
                fg='white',
                relief='flat', 
                padx=10, 
                pady=5
            )
            self.button.pack(side=tk.RIGHT, padx=2, pady=5)

    def run_check(self):
        if getattr(self, 'is_checking', False):
            return
            
        self.is_checking = True
        self.button.config(text="Проверяем...", state=tk.DISABLED)
        
        # Запускаем в отдельном потоке
        threading.Thread(target=self._check_grammar_thread, daemon=True).start()

    def _check_grammar_thread(self):
        total_errors = 0
        error_details = []
        
        for node in self.editor.nodes:
            if not node.content or not node.content.strip():
                continue
                
            text = node.content
            # Используем открытое API LanguageTool, оно отлично проверяет пунктуацию (запятые, тире) и стиль
            try:
                url = "https://api.languagetool.org/v2/check"
                data_encoded = urllib.parse.urlencode({'text': text, 'language': 'ru'}).encode('utf-8')
                req = urllib.request.Request(url, data=data_encoded)
                
                with urllib.request.urlopen(req, timeout=15) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    
                matches = result.get("matches", [])
                
                if matches:
                    if 'highlights' not in node.custom_data:
                        node.custom_data['highlights'] = {}
                        
                    for match in matches:
                        offset = match['offset']
                        length = match['length']
                        
                        # Достаём кусок текста, где допущена ошибка
                        wrong_phrase = text[offset:offset+length]
                        
                        # Сообщение с правилом пунктуации/грамматики
                        msg = match.get('message', '')
                        replacements = [r['value'] for r in match.get('replacements', [])[:3]]
                        
                        # Оранжевый цвет для пунктуационных/грамматических ошибок
                        node.custom_data['highlights'][wrong_phrase] = '#ffaa00' 
                        total_errors += 1
                        
                        hint = f" (Варианты: {', '.join(replacements)})" if replacements else ""
                        error_details.append(f"[{node.title}] '{wrong_phrase}' - {msg}{hint}")
                        
            except Exception as e:
                print(f"[GrammarPlugin] Ошибка при проверке узла {node.id}: {e}")
                
        # Возвращаем выполнение в основной поток (Tkinter не любит изменения из других потоков)
        self.editor.after(0, lambda: self.on_check_complete(total_errors, error_details))

    def on_check_complete(self, total_errors, error_details):
        self.is_checking = False
        self.button.config(text="Проверка пунктуации", state=tk.NORMAL)
        
        # Перерисовываем холст, чтобы отобразить подсветку
        self.editor.redraw()
        
        if total_errors > 0:
            msg = f"Найдено ошибок (пунктуация и грамматика): {total_errors}\nФрагменты подсвечены оранжевым.\n\n"
            # Соединяем с переносом строк (но не больше 8, чтобы окно влезло в экран)
            msg += "\n\n".join(error_details[:8])
            if len(error_details) > 8:
                msg += f"\n\n...и еще {len(error_details) - 8} замечаний."
            messagebox.showwarning("Результат проверки", msg)
        else:
            messagebox.showinfo("Результат проверки", "Ошибок не найдено! С пунктуацией все отлично.")

    def clear_highlights(self):
        """Удаляет всю подсветку из узлов"""
        for node in self.editor.nodes:
            if 'highlights' in node.custom_data:
                node.custom_data['highlights'].clear()
                
        self.editor.redraw()
