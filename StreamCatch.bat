@echo off
title StreamCatch Launcher
echo [1/2] 正在檢查 Python 環境...

:: 啟動後端伺服器 (在新視窗或背景執行)
start /min cmd /c "python main.py"

echo [2/2] 正在等待伺服器啟動...
:: 等待 3 秒讓伺服器準備好
timeout /t 3 /nobreak > nul

echo [OK] 正在開啟瀏覽器...
:: 自動開啟預設瀏覽器造訪首頁
start http://localhost:8000

echo 完成！現在可以開始下載影片了。
echo (請勿關閉背景執行的視窗)
pause