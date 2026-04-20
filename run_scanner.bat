@echo off
:: Setup
pushd "%~dp0"

echo [DEBUG] STARTING SCANNER LAUNCHER...

:: 1. Python Check
echo [DEBUG] Checking Python...
python --version
if errorlevel 1 (
    echo [ERROR] Python failed.
    pause
    exit /b
)

:: 2. Node Check (Simplified)
echo [DEBUG] Checking Node...
:: Using 'where' instead of calling it to avoid hangs
where npm
if errorlevel 1 (
    echo [ERROR] NPM not found.
    pause
    exit /b
)

:: 3. Launch
echo [DEBUG] Launching API...
start "Scanner_API" cmd /k "python -m uvicorn interfaces.api.main:app --port 8001 --host 0.0.0.0"

echo [DEBUG] Launching UI...
start "Scanner_UI" cmd /k "cd interfaces\ui && npm run dev"

echo [DEBUG] Launching Browser...
:: Using ping delay instead of timeout to avoid "Input redirection" error
ping 127.0.0.1 -n 6 > nul
start http://localhost:8080

echo [DEBUG] DONE.
pause
popd
