@echo off
title OSRS AI Agent - Brain Server
echo Starting Brain Middleware on http://localhost:8000 ...
cd /d "%~dp0\brain"
call venv\Scripts\activate
python main.py
pause
