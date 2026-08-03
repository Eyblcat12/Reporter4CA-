@echo off
echo =========================================
echo   Reporter Pro - Starting both servers
echo =========================================
echo.

echo [1/2] Starting Backend (FastAPI) on port 8000...
cd /d "%~dp0reporter-backend"
start "Reporter Backend" cmd /k "python main.py"

echo [2/2] Starting Frontend (Vite) on port 5173...
cd /d "%~dp0reporter-frontend"
start "Reporter Frontend" cmd /k "npm run dev"

echo.
echo =========================================
echo   Both servers are starting!
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://127.0.0.1:8000/docs
echo =========================================
echo.
echo Opening browser...
timeout /t 3 /nobreak > nul
start http://localhost:5173
