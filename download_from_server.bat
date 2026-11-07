@echo off
chcp 65001 > nul
title Dialogue Engine - Sync from Server

echo ===================================================
echo   Синхронизация проекта с сервера коворка
echo   Сервер: https://dialogue-engine.duckdns.org
echo ===================================================

cd /d "%~dp0"
set "TARGET=D:\projects\Violant\game\violant.json"
set "URL=https://dialogue-engine.duckdns.org/api/project"

if exist "%TARGET%" (
    echo [1/3] Создание резервной копии %TARGET%.bak...
    copy /y "%TARGET%" "%TARGET%.bak" > nul
)

echo [2/3] Загрузка актуального violant.json с сервера...
curl.exe -f -s -S -o "%TARGET%" "%URL%"

if %errorlevel% equ 0 (
    echo [3/3] Успешно! Файл %TARGET% обновлен с сервера.
) else (
    echo [ОШИБКА] Не удалось скачать файл с сервера. Проверьте подключение.
)

echo ===================================================
pause
