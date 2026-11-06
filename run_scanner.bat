@echo off
REM ==== Scanner "Value en Crisis" — lanzador para la tarea programada ====
cd /d "C:\Users\dig8_\OneDrive\Documents\BOT 2026\scanner"
python scanner.py --stage news >> "salida\log.txt" 2>&1
