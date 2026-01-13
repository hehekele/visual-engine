import os
import uuid
import shutil
import base64
import json
import threading
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
DATA_OUTPUTS = Path("data/outputs")
DATA_OUTPUTS.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=DATA_OUTPUTS), name="outputs")

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
                # 假设数据是列表，每个元素有 index 字段
                indices = [item.get('index', 0) for item in data]
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
    
    # Initialize task status
    tasks_db[task_id] = {"status": "processing", "images": [], "error": None}
    
    # Start the pipeline in background
    background_tasks.add_task(run_pipeline_task, task_id, request)
    
    return GenerateResponse(task_id=task_id, status="processing")

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

        # 2. Save/Load the image
        if request.image_path:
            # Handle server-side path (from previous white-bg step)
            # Example: /outputs/white_bg_xxx.png
            rel_path = request.image_path.lstrip('/')
            if rel_path.startswith('outputs/'):
                src_path = DATA_OUTPUTS / rel_path[8:]
                if src_path.exists():
                    shutil.copy(src_path, img_path)
                    logger.info(f"Loaded image from path: {src_path}")
                else:
                    raise Exception(f"Image path not found: {src_path}")
            else:
                raise Exception(f"Invalid image path format: {request.image_path}")
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
            sample_dir=str(img_path.parent),
            image=img_path
        )
        
        # Run pipeline
        if request.white_bg_only:
            # 仅生成白底图
            white_bg_path = await pipeline.run_white_bg_only(product)
            # 转换为相对于 DATA_ROOT 的路径供前端访问
            # 注意：white_bg_generator 返回的是绝对路径
            # 我们需要把生成的白底图也放到静态文件服务目录下
            
            # 将生成的白底图移动/复制到 outputs 目录下以便访问
            rel_white_bg = f"white_bg_{task_id}.png"
            output_white_bg = DATA_OUTPUTS / rel_white_bg
            shutil.copy(white_bg_path, output_white_bg)
            
            # Get Base64 for white background image to avoid CORS/Mixed Content issues
            white_bg_base64 = ""
            try:
                if output_white_bg.exists():
                    with open(output_white_bg, "rb") as f:
                        white_bg_base64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
            except Exception as e:
                logger.error(f"Error encoding white_bg to base64: {e}")

            tasks_db[task_id]["status"] = "completed"
            tasks_db[task_id]["images"] = [f"/outputs/{rel_white_bg}"]
            tasks_db[task_id]["white_bg_base64"] = white_bg_base64
        else:
            # 运行完整流程（或从已有的白底图开始）
            result_task = await pipeline.run(product, need_white_bg=request.need_white_bg)
            
            if result_task.status == TaskStatus.COMPLETED:
                generated_images = []
                if result_task.image_result:
                    for img in result_task.image_result.images:
                        # Convert absolute path to relative for the static server
                        rel_path = os.path.relpath(img.image_path, DATA_OUTPUTS)
                        generated_images.append(f"/outputs/{rel_path.replace(os.sep, '/')}")
                
                tasks_db[task_id]["status"] = "completed"
                tasks_db[task_id]["images"] = generated_images
                
                # Proactively return Base64 for the first few results to ensure they display in HTTPS
                tasks_db[task_id]["images_base64"] = []
                for img_path_str in [img.image_path for img in result_task.image_result.images[:2]]:
                    try:
                        with open(img_path_str, "rb") as f:
                            tasks_db[task_id]["images_base64"].append(
                                f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
                            )
                    except:
                        pass
                
                # Also try to get white_bg_base64 for the full pipeline if requested
                if request.need_white_bg:
                    try:
                        white_bg_file = product_dir / "white_bg.png"
                        if white_bg_file.exists():
                            with open(white_bg_file, "rb") as f:
                                tasks_db[task_id]["white_bg_base64"] = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
                    except Exception as e:
                        logger.error(f"Error encoding full-pipeline white_bg to base64: {e}")
            else:
                tasks_db[task_id]["status"] = "failed"
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
