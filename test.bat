@echo off
setlocal
title XYZ2Heightmap Test Runner & CI Gate

:: Navigate to project root directory
cd /d "%~dp0"

echo ===================================================
echo   XYZ2Heightmap - Pre-Commit Quality & CI Gate
echo ===================================================
echo.

python scripts\verify_ci.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Verification failed with error code %ERRORLEVEL%.
    echo Please review the errors above and resolve them before committing.
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [SUCCESS] All verification gates passed successfully!
echo.
pause
