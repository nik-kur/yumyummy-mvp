#!/bin/zsh
# Двойной клик по этому файлу в Finder запускает песочницу Agent v2
# и открывает её в браузере. Закрыть: закрыть окно Терминала (или Ctrl+C).
cd "$(dirname "$0")/.."
PY="/Users/nikita/Documents/YumYummy/yumyummy-mvp/.venv/bin/python"
( sleep 2 && open "http://127.0.0.1:8787" ) &
exec "$PY" sandbox/server.py
