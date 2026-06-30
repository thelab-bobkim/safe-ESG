@echo off
chcp 65001 > nul
title MediSafe 설치

REM PowerShell 실행 정책 우회해서 PS1 실행
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0MediSafe_설치_DSTI.ps1"

pause
