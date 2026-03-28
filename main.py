import os
import uuid
import asyncio
import shutil
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import logging

# 1. 設定日誌系統，讓你能在黑視窗看到詳細的下載進度與錯誤訊息
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="StreamCatch Backend")

# 2. 允許前端網頁連線到這個後端
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# 3. 設定檔案存放目錄
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_ROOT = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

# 任務狀態儲存器 (儲存於記憶體中)
tasks = {}

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp4"
    quality: str = "1080"
    type: str = "video"

def ytdlp_hook(d, task_id):
    """yt-dlp 的進度鉤子，將下載百分比更新到 tasks 中"""
    if d['status'] == 'downloading':
        # 提取百分比數字
        p_str = d.get('_percent_str', '0%').replace('%', '').strip()
        try:
            progress = float(p_str)
        except:
            progress = 0
            
        tasks[task_id].update({
            "status": "downloading",
            "progress": progress,
            "speed": d.get('_speed_str', 'N/A'),
            "eta": d.get('_eta_str', 'N/A'),
            "size": d.get('_total_bytes_str', d.get('_total_bytes_estimate_str', 'N/A'))
        })
    elif d['status'] == 'finished':
        tasks[task_id].update({"status": "processing", "progress": 100})

def run_download(task_id, url, format, quality, dl_type):
    """在背景執行真正的下載與轉檔邏輯"""
    task_dir = os.path.join(DOWNLOAD_ROOT, task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    # 畫質高度處理
    h = "1080"
    if "720" in quality: h = "720"
    elif "480" in quality: h = "480"
    elif "2160" in quality or "4k" in quality.lower(): h = "2160"

    ydl_opts = {
        # 格式選擇：自動選擇畫質高度內的最佳視訊+音訊
        'format': f'bestvideo[height<={h}]+bestaudio/best' if dl_type == "video" else 'bestaudio/best',
        'outtmpl': f'{task_dir}/%(title)s.%(ext)s',
        # 使用 FFmpeg 合併為指定格式
        'merge_output_format': 'mp4' if dl_type == "video" else None,
        'progress_hooks': [lambda d: ytdlp_hook(d, task_id)],
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': format,
        }] if dl_type == "video" else [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }

    # 檢查有無提供 facebook cookie
    cookie_path = os.path.join(BASE_DIR, "cookies", "facebook.txt")
    if os.path.exists(cookie_path):
        ydl_opts['cookiefile'] = cookie_path

    try:
        logger.info(f"開始任務 [{task_id}]: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 執行下載
            info = ydl.extract_info(url, download=True)
            
            # 抓取處理後資料夾中的檔案
            files = [f for f in os.listdir(task_dir) if not f.startswith('.')]
            if not files:
                raise Exception("下載已完成但未在資料夾發現檔案，請檢查 FFmpeg 合併過程。")
            
            actual_filename = files[0]
            tasks[task_id].update({
                "status": "completed", 
                "filename": actual_filename,
                "progress": 100
            })
            logger.info(f"任務成功: {actual_filename}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"任務失敗: {error_msg}")
        tasks[task_id].update({"status": "failed", "error": error_msg})

@app.post("/api/download")
async def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "starting", "progress": 0}
    # 將下載任務丟到背景執行，以免網頁卡死
    background_tasks.add_task(run_download, task_id, req.url, req.format, req.quality, req.type)
    return {"task_id": task_id}

@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    return tasks.get(task_id, {"status": "not_found"})

@app.get("/api/file/{task_id}")
async def get_file(task_id: str):
    if task_id not in tasks or "filename" not in tasks[task_id]:
        raise HTTPException(status_code=404, detail="檔案還沒準備好")
    
    file_path = os.path.join(DOWNLOAD_ROOT, task_id, tasks[task_id]["filename"])
    return FileResponse(file_path, filename=tasks[task_id]["filename"])

@app.on_event("startup")
async def check_environment():
    """啟動時自動檢查電腦有沒有裝好 FFmpeg"""
    ffmpeg_check = shutil.which("ffmpeg")
    if ffmpeg_check:
        logger.info(f"✅ 環境檢查通過！偵測到 FFmpeg: {ffmpeg_check}")
    else:
        logger.warning("❌ 環境檢查警告：找不到 FFmpeg！影片下載後將無法合併音軌，請務必安裝。")

@app.get("/")
async def index():
    """造訪首頁時顯示前端 HTML"""
    return FileResponse('video-downloader.html')

if __name__ == "__main__":
    import uvicorn
    # 啟動 API 伺服器
    uvicorn.run(app, host="0.0.0.0", port=8000)
