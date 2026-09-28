@echo off
cd /d "%~dp0.."
py -3 -m compcontrol
if errorlevel 1 pause
