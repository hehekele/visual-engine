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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.schemas import ProductInput, TaskStatus
from app.services.pipeline import ProductImagePipeline
from app.core.logging import logger, setup_logging
from app.core.config import settings

# 初始化日志配置
setup_logging()

# 初始化 FastAPI 应用
app = FastAPI(
    title="Visual Engine API",
    description="电商视觉生成后端服务，负责任务调度和 AI 流水线编排。",
    version="1.0.0"
)

# -----------------------------------------------------------------------------
# CORS 配置 (CORS Configuration)
# -----------------------------------------------------------------------------
# 允许来自浏览器插件的跨域请求。
# 在生产环境中，'allow_origins' 应该限制为特定的域名或插件 ID。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# 静态文件服务 (Static File Serving)
# -----------------------------------------------------------------------------
# 配置数据存储路径
DATA_ROOT = Path("data")
DATA_OUTPUTS = DATA_ROOT / "outputs"

# 确保必要的目录存在
DATA_ROOT.mkdir(parents=True, exist_ok=True)
DATA_OUTPUTS.mkdir(parents=True, exist_ok=True)

# 挂载静态目录以服务生成的图片
app.mount("/outputs", StaticFiles(directory=DATA_OUTPUTS), name="outputs")
app.mount("/data", StaticFiles(directory=DATA_ROOT), name="data")

# -----------------------------------------------------------------------------
# 全局状态与并发控制 (Global State & Concurrency Control)
# -----------------------------------------------------------------------------
# 用于同步写入文件级数据库 (products.json) 的锁
db_lock = threading.Lock()

# 用于跟踪活跃任务状态的内存存储。
# 注意：在多 Worker 的生产环境中，请替换为 Redis。
tasks_db = {}

# -----------------------------------------------------------------------------
# 辅助函数 (Helper Functions)
# -----------------------------------------------------------------------------

def get_next_product_index() -> int:
    """
    通过读取 products.json 文件计算下一个可用的商品序号。
    
    Returns:
        int: 下一个可用的自增序号。如果文件为空或不存在，默认为 1。
    """
    with db_lock:
        json_path = settings.full_products_json_path
        if not json_path.exists():
            return 1
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not data:
                    return 1
                # 过滤掉类似时间戳的异常序号（例如 > 1,000,000）以保持序列连续
                indices = [
                    item.get('index', 0) 
                    for item in data 
                    if isinstance(item.get('index'), int) and item.get('index', 0) < 1000000
                ]
                return max(indices) + 1 if indices else 1
        except Exception as e:
            logger.error(f"Error reading products.json: {e}")
            return 1

def save_product_to_json(product_data: dict) -> None:
    """
    线程安全地保存或更新商品数据到 products.json。
    
    Args:
        product_data (dict): 要保存的商品信息字典。
    """
    with db_lock:
        json_path = settings.full_products_json_path
        data = []
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading products.json: {e}")
        
        # 检查序号是否存在，以进行更新而不是追加
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

def update_task_progress(task_id: str, phrases: List[str] = None, new_image_url: str = None, new_image_base64: str = None, status: str = None):
    """
    线程安全地更新内存中的任务状态，供前端轮询。
    
    Args:
        task_id (str): 任务的唯一标识符。
        phrases (List[str], optional): 生成的提示词列表。
        new_image_url (str, optional): 新生成图片的 URL。
        new_image_base64 (str, optional): 新生成图片的 Base64 字符串。
        status (str, optional): 新的状态字符串 (例如 'processing', 'completed', 'failed')。
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

# -----------------------------------------------------------------------------
# 数据模型 (Data Models)
# -----------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """
    /api/generate 端点的请求模型。
    """
    name: str
    detail: str
    attributes: Optional[str] = ""      # 商品属性/规格
    image_base64: Optional[str] = None  # Base64 编码的源图
    image_url: Optional[str] = None     # 源图 URL (Fallback)
    image_path: Optional[str] = None    # 服务端相对路径 (例如 /outputs/xxx.png)
    product_index: Optional[int] = None # 如果提供，复用现有的商品序号
    gallery_images: List[str] = []      # 需要下载的橱窗图 URL 列表
    detail_images: List[str] = []       # 需要下载的详情图 URL 列表
    need_white_bg: bool = False         # 是否触发去底步骤
    save_to_data: bool = True           # 是否将数据持久化到磁盘结构
    white_bg_only: bool = False         # 如果为 True，则在去底后停止

class GenerateResponse(BaseModel):
    """
    任务创建的响应模型。
    """
    task_id: str
    status: str

# -----------------------------------------------------------------------------
# API 端点 (API Endpoints)
# -----------------------------------------------------------------------------

@app.post("/api/generate", response_model=GenerateResponse)
async def generate_scene(request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    发起场景生成任务。
    
    此端点是非阻塞的。它初始化任务上下文并将繁重的工作卸载到后台任务。
    """
    task_id = str(uuid.uuid4())
    
    # 1. 为此任务创建一个临时目录
    task_dir = Path(f"data/temp/{task_id}")
    task_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. 在内存中初始化任务状态
    tasks_db[task_id] = {
        "status": "processing",
        "phrases": [],         # 存储生成的场景描述
        "images": [],          # 存储生成图片的 URL
        "images_base64": [],   # 存储用于即时预览的 Base64 数据
        "error": None
    }
    
    # 3. 在后台调度流水线执行
    background_tasks.add_task(run_pipeline_task, task_id, request)
    
    return GenerateResponse(task_id=task_id, status="processing")

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """
    获取特定任务的当前状态和结果。
    前端用于轮询进度。
    """
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks_db[task_id]

# -----------------------------------------------------------------------------
# 后台任务逻辑 (Background Task Logic)
# -----------------------------------------------------------------------------

async def run_pipeline_task(task_id: str, request: GenerateRequest):
    """
    执行核心 AI 生成流水线。
    
    步骤:
    1. 确定存储路径并下载资源 (橱窗/详情图)。
    2. 解析源图片 (来自 Path, Base64 或 URL)。
    3. 初始化 ProductImagePipeline。
    4. 执行流水线 (仅去底 或 全流程生成)。
    5. 完成或失败时更新任务状态。
    """
    try:
        pipeline = ProductImagePipeline()
        index = request.product_index
        
        # --- 步骤 1: 确定存储路径 & 下载资源 ---
        if request.save_to_data:
            if index is None:
                index = get_next_product_index()
            
            target_dir = settings.DATA_ROOT / str(index)
            target_dir.mkdir(parents=True, exist_ok=True)
            img_path = target_dir / "main.jpg"
            
            # 辅助函数: 下载图片到指定目录
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

            # 保存橱窗图和详情图
            saved_sub_images = download_to_dir(request.gallery_images, target_dir / "sub_images", "gallery")
            saved_detail_images = download_to_dir(request.detail_images, target_dir / "detail", "detail")

            # 持久化商品信息到 JSON
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
            # 更新任务状态中的商品序号
            tasks_db[task_id]["product_index"] = index
        else:
            # 如果不保存到数据根目录，则使用临时目录
            task_dir = Path(f"data/temp/{task_id}")
            task_dir.mkdir(parents=True, exist_ok=True)
            img_path = task_dir / "main.jpg"

        # --- 步骤 2: 解析源图片 ---
        active_image_path = img_path
        if request.image_path:
            # 情况 A: 图片已存在于服务器上 (例如来自上一步的白底图)
            rel_path = request.image_path.lstrip('/')
            src_path = None
            if rel_path.startswith('outputs/'):
                src_path = DATA_OUTPUTS / rel_path[8:]
            elif rel_path.startswith('data/'):
                src_path = DATA_ROOT / rel_path[5:]
            
            if src_path and src_path.exists():
                active_image_path = src_path
                logger.info(f"Using provided image source: {active_image_path}")
            else:
                raise Exception(f"Image path not found or invalid format: {request.image_path}")
        elif request.image_base64:
            # 情况 B: 提供了 Base64 数据
            header, data = request.image_base64.split(',', 1) if ',' in request.image_base64 else (None, request.image_base64)
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(data))
        elif request.image_url:
            # 情况 C: 从 URL 下载
            import requests
            response = requests.get(request.image_url, timeout=10)
            with open(img_path, "wb") as f:
                f.write(response.content)
        else:
            raise Exception("No image provided (base64, URL or path)")

        # --- 步骤 3: 准备流水线输入 ---
        product = ProductInput(
            name=request.name,
            detail=request.detail,
            attributes=request.attributes,
            sample_dir=str(img_path.parent.relative_to(DATA_ROOT)), 
            image=active_image_path.relative_to(DATA_ROOT) if active_image_path.is_absolute() else active_image_path
        )
        
        # --- 步骤 4: 执行流水线 ---
        if request.white_bg_only:
            # 子流程: 仅生成白底图
            white_bg_path = await pipeline.run_white_bg_only(product)
            white_bg_path_abs = Path(white_bg_path).resolve()
            
            # 保存到永久位置
            product_index = request.product_index if request.product_index is not None else get_next_product_index()
            task_dir = DATA_ROOT / str(product_index)
            task_dir.mkdir(parents=True, exist_ok=True)
            
            output_white_bg = task_dir / "white_bg_main.jpg"
            white_bg_path_p = Path(white_bg_path).resolve()
            output_white_bg_p = output_white_bg.resolve()
            
            # 避免自我覆盖
            if white_bg_path_p == output_white_bg_p:
                logger.info(f"New white bg is already at target: {output_white_bg_p}")
            else:
                if output_white_bg_p.exists():
                    output_white_bg_p.unlink()
                shutil.copy(white_bg_path, output_white_bg)
            
            output_white_bg_abs = output_white_bg.resolve()
            
            # 生成返回 URL
            try:
                rel_path = output_white_bg_abs.relative_to(DATA_ROOT.resolve())
                url = f"/data/{rel_path.as_posix()}"
            except ValueError:
                url = str(output_white_bg_abs)
            
            # 编码 Base64
            white_bg_base64 = ""
            try:
                if output_white_bg_abs.exists():
                    with open(output_white_bg_abs, "rb") as f:
                        white_bg_base64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
            except Exception as e:
                logger.error(f"Error encoding white_bg to base64: {e}")

            # 更新任务状态
            with db_lock:
                tasks_db[task_id]["images"] = [url]
                tasks_db[task_id]["images_base64"] = [white_bg_base64]
                tasks_db[task_id]["white_bg_base64"] = white_bg_base64
                tasks_db[task_id]["status"] = "completed"
                tasks_db[task_id]["product_index"] = product_index
        else:
            # 子流程: 全流程生成
            result_task = await pipeline.run(
                product, 
                need_white_bg=request.need_white_bg
            )
            
            if result_task.status == TaskStatus.COMPLETED:
                # 任务完成，提取生成的提示词并更新状态
                final_phrases = []
                if result_task.phrase_result and result_task.phrase_result.phrases:
                    final_phrases = [p.scene_description for p in result_task.phrase_result.phrases]
                
                # 提取生成的所有图片
                final_images = []
                final_images_base64 = []
                
                if result_task.image_result and result_task.image_result.images:
                    for img_obj in result_task.image_result.images:
                        img_path_abs = Path(img_obj.image_path).resolve()
                        
                        # 解析图片 URL
                        try:
                            rel_path = img_path_abs.relative_to(DATA_OUTPUTS.resolve())
                            url = f"/outputs/{rel_path.as_posix()}"
                        except ValueError:
                            try:
                                rel_path = img_path_abs.relative_to(DATA_ROOT.resolve())
                                url = f"/data/{rel_path.as_posix()}"
                            except ValueError:
                                url = str(img_path_abs)
                        final_images.append(url)
                        
                        # 编码 Base64
                        try:
                            if img_path_abs.exists():
                                with open(img_path_abs, "rb") as f:
                                    base64_data = f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
                                    final_images_base64.append(base64_data)
                        except Exception as e:
                            logger.error(f"Error encoding final image: {e}")

                # 一次性更新所有结果
                with db_lock:
                    tasks_db[task_id]["phrases"] = final_phrases
                    tasks_db[task_id]["images"] = final_images
                    tasks_db[task_id]["images_base64"] = final_images_base64
                    tasks_db[task_id]["status"] = "completed"
            else:
                update_task_progress(task_id, status="failed")
                tasks_db[task_id]["error"] = result_task.error
            
    except Exception as e:
        logger.error(f"Error in background task {task_id}: {str(e)}")
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["error"] = str(e)

if __name__ == "__main__":
    import uvicorn
    # 使用 uvicorn 启动服务器
    uvicorn.run(app, host="0.0.0.0", port=8000)
