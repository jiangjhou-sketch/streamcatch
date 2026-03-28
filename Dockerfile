# 1. 使用官方的 Python 3.11 輕量版作為基礎鏡像
FROM python:3.11-slim

# 2. 安裝 FFmpeg (影音合併與轉檔的核心工具) 以及基礎系統工具
RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# 3. 設定程式在雲端電腦中的工作資料夾
WORKDIR /app

# 4. 先複製套件清單並執行安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 複製你所有的程式碼 (main.py, video-downloader.html 等) 到雲端電腦
COPY . .

# 6. 建立存放下載影片與 Cookie 的資料夾
RUN mkdir -p downloads cookies

# 7. 告知 Render 我們的程式跑在 8000 埠
EXPOSE 8000

# 8. 啟動程式的最終指令
CMD ["python", "main.py"]