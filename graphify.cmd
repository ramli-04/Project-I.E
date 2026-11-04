@echo off
"%~dp0.graphify-venv\Scripts\python.exe" -m graphify %*
exit /b %errorlevel%
