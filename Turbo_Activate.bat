@echo off
REM ═══════════════════════════════════════════════════════════════
REM  TURBO — Neural Activator (one-click activation)
REM  Runs the full health + drift check for Quantum Nexus Forge
REM ═══════════════════════════════════════════════════════════════

cd /d "%~dp0"
title TURBO — Neural Activator
set PYTHONIOENCODING=utf-8

python turbo_console.py activate

echo.
echo ───────────────────────────────────────────────
echo  Press any key to close.
pause >nul
