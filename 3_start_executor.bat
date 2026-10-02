@echo off
title OSRS AI Agent - Mouse Executor
echo Starting Mouse Executor...
echo NOTE: Move mouse to top-left corner (0,0) to abort at any time.
cd /d "%~dp0"
call brain\venv\Scripts\activate
python executor\input_driver.py
pause
