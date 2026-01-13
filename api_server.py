import os
import uuid
import shutil
import base64
import json
import threading
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from app.schemas import ProductInput, TaskStatus
from app.services.pipeline import ProductImagePipeline
from app.core.logging import logger, setup_logging
from app.core.config import settings
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Setup logging
setup_logging()

app = FastAPI(title="Visual Engine API")

# Enable CORS for the extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the extension ID
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for serving generated images
DATA_ROOT = Path("data")
DATA_OUTPUTS = DATA_ROOT / "outputs"
DATA_ROOT.mkdir(parents=True, exist_ok=True)
DATA_OUTPUTS.mkdir(parents=True, exist_ok=True)

app.mount("/outputs", StaticFiles(directory=DATA_OUTPUTS), name="outputs")
app.mount("/data", StaticFiles(directory=DATA_ROOT), name="data")

# File-based database lock
db_lock = threading.Lock()

def get_next_product_index():
    with db_lock:
        json_path = settings.full_products_json_path
        if not json_path.exists():
            return 1
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not data:
                    return 1
                # 过滤掉时间戳风格的异常序号（例如大于 1000000 的）
                indices = [item.get('index', 0) for item in data if isinstance(item.get('index'), int) and item.get('index', 0) < 1000000]
                return max(indices) + 1 if indices else 1
        except Exception as e:
            logger.error(f"Error reading products.json: {e}")
            return 1

def save_product_to_json(product_data):
    with db_lock:
        json_path = settings.full_products_json_path
        data = []
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading products.json: {e}")
        
        # Check if index already exists to update instead of append
        existing_idx = -1
        for i, item in enumerate(data):
            if item.get('index') == product_data['index']:
                existing_idx = i
                break
        
        if existing_idx >= 0:
            data[existing_idx] = product_data
        else:
            data.append(product_data)
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving products.json: {e}")

class GenerateRequest(BaseModel):
    name: str
    detail: str
    attributes: Optional[str] = ""     # 商品属性
    image_base64: Optional[str] = None  # Base64 encoded image
    image_url: Optional[str] = None    # Fallback URL
    image_path: Optional[str] = None   # 服务器端相对路径 (例如 /outputs/xxx.png)
    product_index: Optional[int] = None # 复用已有的产品序号
    gallery_images: List[str] = []     # 橱窗图列表 (用于存入 sub_images)
    detail_images: List[str] = []      # 详情图列表 (用于存入 detail 目录)
    need_white_bg: bool = False        # 是否需要先生成白底图
    save_to_data: bool = True          # 是否保存到 data/序号 目录
    white_bg_only: bool = False        # 是否仅生成白底图 (第一步)
    
class GenerateResponse(BaseModel):
    task_id: str
    status: str

# In-memory task storage (for demo purposes)
tasks_db = {}

@app.post("/api/generate", response_model=GenerateResponse)
async def generate_scene(request: GenerateRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    
    # 1. Create a temp directory for this task
    task_dir = Path(f"data/temp/{task_id}")
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Download the main image (simplified for now - extension can send base64)
    # For now, let's assume extension sends the image content if possible, or we download it.
    # To keep it simple, the extension will send base64 in a real scenario.
    # But let's support image_url for now.
    
    # Initialize task status with support for progressive loading
    tasks_db[task_id] = {
        "status": "processing",
        "phrases": [],         # Placeholder for scene descriptions
        "images": [],          # Progressive image URLs
        "images_base64": [],   # Progressive image Base64
        "error": None
    }
    
    # Start the pipeline in background
    background_tasks.add_task(run_pipeline_task, task_id, request)
    
    return GenerateResponse(task_id=task_id, status="processing")

def update_task_progress(task_id: str, phrases: List[str] = None, new_image_url: str = None, new_image_base64: str = None, status: str = None):
    """
    Update task status in a thread-safe way for progressive loading.
    """
    with db_lock:
        if task_id not in tasks_db:
            return
        
        if phrases is not None:
            tasks_db[task_id]["phrases"] = phrases
            
        if new_image_url is not None:
            tasks_db[task_id]["images"].append(new_image_url)
            
        if new_image_base64 is not None:
            tasks_db[task_id]["images_base64"].append(new_image_base64)
            
        if status is not None:
            tasks_db[task_id]["status"] = status

async def run_pipeline_task(task_id: str, request: GenerateRequest):
    try:
        pipeline = ProductImagePipeline()
        index = request.product_index
        
        # 1. Determine storage path
        if request.save_to_data:
            if index is None:
                index = get_next_product_index()
            
            target_dir = settings.DATA_ROOT / str(index)
            target_dir.mkdir(parents=True, exist_ok=True)
            img_path = target_dir / "main.jpg"
            
            # Helper function for downloading images
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.1688.com/'
            }
            def download_to_dir(urls, directory, prefix):
                saved_paths = []
                if not urls: return saved_paths
                directory.mkdir(exist_ok=True)
                for i, url in enumerate(urls):
                    try:
                        full_url = url if url.startswith('http') else ('https:' + url if url.startswith('//') else url)
                        if not full_url.startswith('http'): continue
                        resp = requests.get(full_url, headers=headers, timeout=15)
                        if resp.status_code == 200:
                            file_ext = ".jpg"
                            if "png" in resp.headers.get("Content-Type", "").lower(): file_ext = ".png"
                            save_path = directory / f"{prefix}_{i}{file_ext}"
                            with open(save_path, "wb") as f:
                                f.write(resp.content)
                            saved_paths.append(str(save_path.relative_to(settings.DATA_ROOT)))
                    except Exception as e:
                        logger.error(f"Failed to download image {url}: {e}")
                return saved_paths

            # 1.1 Save gallery images to sub_images
            saved_sub_images = download_to_dir(request.gallery_images, target_dir / "sub_images", "gallery")
            
            # 1.2 Save detail images to detail directory
            saved_detail_images = download_to_dir(request.detail_images, target_dir / "detail", "detail")

            # Save info to JSON
            product_info = {
                "index": index,
                "name": request.name,
                "detail": request.detail,
                "attributes": request.attributes,
                "image": str(img_path.relative_to(settings.DATA_ROOT)),
                "sub_images": saved_sub_images,
                "detail_images": saved_detail_images,
                "task_id": task_id
            }
            save_product_to_json(product_info)
            # Store index in task status for frontend to reuse
            tasks_db[task_id]["product_index"] = index
        else:
            task_dir = Path(f"data/temp/{task_id}")
            task_dir.mkdir(parents=True, exist_ok=True)
            img_path = task_dir / "main.jpg"

        # 2. 获取正确的图片路径作为生图源
        # 遵循设计：如果提供了 image_path（如白底图），则使用它；否则使用默认的 main.jpg
        active_image_path = img_path
        if request.image_path:
            # Handle server-side path (from previous white-bg step)
            # Example: /outputs/xxx.png or /data/序号/white_bg_main.jpg
            rel_path = request.image_path.lstrip('/')
            
            src_path = None
            if rel_path.startswith('outputs/'):
                src_path = DATA_OUTPUTS / rel_path[8:]
            elif rel_path.startswith('data/'):
                src_path = DATA_ROOT / rel_path[5:]
            
            if src_path and src_path.exists():
                # 不再执行 shutil.copy(src_path, img_path)，避免覆盖原始 main.jpg
                active_image_path = src_path
                logger.info(f"Using provided image source: {active_image_path}")
            else:
                raise Exception(f"Image path not found or invalid format: {request.image_path}")
        elif request.image_base64:
            # Handle base64
            header, data = request.image_base64.split(',', 1) if ',' in request.image_base64 else (None, request.image_base64)
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(data))
        elif request.image_url:
            # Fallback to download
            import requests
            response = requests.get(request.image_url, timeout=10)
            with open(img_path, "wb") as f:
                f.write(response.content)
        else:
            raise Exception("No image provided (base64, URL or path)")

        # 3. Create ProductInput
        product = ProductInput(
            name=request.name,
            detail=request.detail,
            attributes=request.attributes,
            sample_dir=str(img_path.parent.relative_to(DATA_ROOT)), # 使用相对 DATA_ROOT 的路径
            image=active_image_path.relative_to(DATA_ROOT) if active_image_path.is_absolute() else active_image_path
        )
        
        # Define progress callback
        def on_pipeline_progress(progress_data):
            # Handle phrases
            if "phrases" in progress_data:
                update_task_progress(task_id, phrases=progress_data["phrases"])
            
            # Handle single image complete
            if "new_image" in progress_data:
                img_path_abs = Path(progress_data["new_image"]).resolve()
                
                # Try to resolve relative to DATA_OUTPUTS first
                try:
                    rel_path = img_path_abs.relative_to(DATA_OUTPUTS.resolve())
                    url = f"/outputs/{rel_path.as_posix()}"
                except ValueError:
                    # Fallback to DATA_ROOT
                    try:
                        rel_path = img_path_abs.relative_to(DATA_ROOT.resolve())
                        url = f"/data/{rel_path.as_posix()}"
                    except ValueError:
                        # Absolute path or outside data root
                        url = str(img_path_abs)
                
                # Get Base64
                base64_data = ""
                try:
                    if img_path_abs.exists():
                        with open(img_path_abs, "rb") as f:
                            base64_data = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
                except Exception as e:
                    logger.error(f"Error encoding progressive image: {e}")
                
                update_task_progress(task_id, new_image_url=url, new_image_base64=base64_data)

        # Run pipeline
        if request.white_bg_only:
            white_bg_path = await pipeline.run_white_bg_only(product)
            white_bg_path_abs = Path(white_bg_path).resolve()
            
            # 确保保存到正确的序号目录 (data/序号)
            product_index = request.product_index if request.product_index is not None else get_next_product_index()
            task_dir = DATA_ROOT / str(product_index)
            task_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用统一的文件名 white_bg_main.jpg
            output_white_bg = task_dir / "white_bg_main.jpg"
            
            # 💡 修复：如果新生成的路径和目标路径相同，或者目标文件已存在，先处理冲突
            white_bg_path_p = Path(white_bg_path).resolve()
            output_white_bg_p = output_white_bg.resolve()
            
            if white_bg_path_p == output_white_bg_p:
                logger.info(f"New white bg is already at target: {output_white_bg_p}")
            else:
                if output_white_bg_p.exists():
                    logger.info(f"Removing existing white bg before overwrite: {output_white_bg_p}")
                    output_white_bg_p.unlink()
                shutil.copy(white_bg_path, output_white_bg)
            
            output_white_bg_abs = output_white_bg.resolve()
            
            # 生成 URL (相对于 DATA_ROOT)
            try:
                rel_path = output_white_bg_abs.relative_to(DATA_ROOT.resolve())
                url = f"/data/{rel_path.as_posix()}"
            except ValueError:
                url = str(output_white_bg_abs)
            
            white_bg_base64 = ""
            try:
                if output_white_bg_abs.exists():
                    with open(output_white_bg_abs, "rb") as f:
                        white_bg_base64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
            except Exception as e:
                logger.error(f"Error encoding white_bg to base64: {e}")

            # 清空 images 重新填充，确保前端获取的是最新单张图
            with db_lock:
                tasks_db[task_id]["images"] = [url]
                tasks_db[task_id]["images_base64"] = [white_bg_base64]
                tasks_db[task_id]["white_bg_base64"] = white_bg_base64 # 兼容旧逻辑
                tasks_db[task_id]["status"] = "completed"
                tasks_db[task_id]["product_index"] = product_index
        else:
            # 运行完整流程（支持进度回调）
            result_task = await pipeline.run(product, need_white_bg=request.need_white_bg, on_progress=on_pipeline_progress)
            
            if result_task.status == TaskStatus.COMPLETED:
                update_task_progress(task_id, status="completed")
            else:
                update_task_progress(task_id, status="failed")
                tasks_db[task_id]["error"] = result_task.error
            
    except Exception as e:
        logger.error(f"Error in background task {task_id}: {str(e)}")
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["error"] = str(e)

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks_db[task_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
