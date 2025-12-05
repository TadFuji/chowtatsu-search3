@echo off
echo Starting Chowtatsu Search Robot...

:: Start Backend
echo Starting Backend Server...
cd backend
start "Chowtatsu Backend" cmd /k "python main.py"

:: Wait for backend to initialize (3 seconds)
timeout /t 3 /nobreak >nul

:: Start Frontend
echo Opening Frontend...
cd ..\frontend
start index.html

echo Done!
pause
