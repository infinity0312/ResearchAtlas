@echo off
powershell -NoProfile -File "%~dp0start.ps1"
if errorlevel 1 pause
