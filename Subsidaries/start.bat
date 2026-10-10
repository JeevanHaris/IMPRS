@echo off
:: ═══════════════════════════════════════════════════════════
::  IPMPRS — Puducherry Police Hackathon 2026
::  Intelligent Proposal Management & Precedent Retrieval System
:: ═══════════════════════════════════════════════════════════
title IPMPRS - Puducherry Police Platform

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║   IPMPRS · Puducherry Police Department              ║
echo  ║   Intelligent Proposal Management & Precedents       ║
echo  ║   Hackathon 2026 - Problem Statement 01              ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: Check Ollama
echo [1/3] Checking Ollama service...
ollama list >nul 2>&1
if errorlevel 1 (
    echo  [!] Ollama offline or not running.
    echo      IPMPRS will operate with high-speed BM25 & template fallbacks.
    echo      To enable local neural embeddings: install https://ollama.com
    echo.
) else (
    echo  [OK] Ollama service detected.
    echo.
)

echo [2/3] Checking database status...
python -c "import proposals, seed_data; s = proposals.get_proposal_stats(); print(f'  [OK] proposals.db active ({s[\"total_proposals\"]} proposals indexed)')"

echo.
echo [3/3] Starting IPMPRS server on http://localhost:5000 ...
echo       Access the platform via index.html in your browser.
echo       Press Ctrl+C to stop.
echo.

python server.py
pause
