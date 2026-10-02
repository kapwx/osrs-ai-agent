@echo off
title OSRS AI Agent - RuneLite Client
echo Starting RuneLite with Agent Plugin injected...
cd /d "%~dp0\plugin"
call gradle-8.5\bin\gradle.bat runClient
pause
