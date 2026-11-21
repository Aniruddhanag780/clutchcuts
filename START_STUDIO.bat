@echo off
title ClutchCuts AI Studio
cd /d "C:\Users\COMPUTER\.gemini\antigravity\scratch\stream_to_shorts_pipeline\web_app"
echo Starting ClutchCuts AI Studio...
start "" http://127.0.0.1:5000
"C:\Users\COMPUTER\AppData\Local\Programs\Python\Python311\python.exe" server.py
pause
