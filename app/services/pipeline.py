import time
import uuid
import json
from datetime import datetime
from pathlib import Path
from loguru import logger
from app.schemas import ProductInput, GenerationTask, TaskStatus
from app.core.config import settings
from app.services.processors.scene_summarizer import SceneSummarizer
from app.services.processors.scene_refiner import SceneRefiner
from app.services.processors.phrase_generator import PhraseGenerator
from app.services.processors.image_generator import ImageGenerator
from app.services.processors.white_bg_generator import WhiteBGGenerator

class ProductImagePipeline:
    """
    电商视觉生成核心流水线 (Core Pipeline)。
    
    职责：
    协调各个 AI 处理器（Processors），按序执行“视觉理解 -> 场景优化 -> 提示词生成 -> 图像生成”的完整业务流程。
    同时负责任务状态管理、中间结果持久化及进度回调。
    """
    def __init__(self):
        # 初始化各个处理单元
        self.summarizer = SceneSummarizer()       # 分析商品特征场景
        self.refiner = SceneRefiner()             # 拓展商品场景
        self.phrase_generator = PhraseGenerator() # 将场景转换为具体的绘画 Prompt
        self.image_generator = ImageGenerator()   # 对接外部绘图API
        self.white_bg_generator = WhiteBGGenerator() # 白底图生成

    def _save_intermediate(self, task_dir: Path, step_name: str, data: any):
        """
        持久化中间步骤结果，便于调试与回溯。
        
        Args:
            task_dir (Path): 任务输出目录
            step_name (str): 步骤名称（用于生成文件名）
            data (any): 需要保存的数据（支持 Pydantic 模型或普通字典/列表）
        """
        output_dir = task_dir / "intermediates"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{step_name}.json"
        filepath = output_dir / filename
        
        try:
            # 优先使用 Pydantic 的 model_dump 方法进行序列化
            if hasattr(data, "model_dump"):
                content = data.model_dump()
            else:
                content = data
                
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved intermediate result to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save intermediate result: {e}")

    async def run_white_bg_only(self, product: ProductInput) -> Path:
        """
        [独立功能] 仅执行白底图生成。
        
        Args:
            product (ProductInput): 商品输入信息
            
        Returns:
            Path: 生成的白底图绝对路径
        """
        logger.info("Pipeline: Generating white background only...")
        new_image_path = await self.white_bg_generator.process(product.image)
        return new_image_path

    async def run(self, product: ProductInput, need_white_bg: bool = False) -> GenerationTask:
        """
        执行完整的视觉生成流水线。
        
        Args:
            product (ProductInput): 商品输入数据（包含图片路径、名称等）
            need_white_bg (bool): 是否需要先进行白底图处理（默认 False）
            
        Returns:
            GenerationTask: 包含最终结果及各步骤中间数据的任务对象
        """
        start_time = time.time()
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态对象
        task = GenerationTask(task_id=task_id, product=product, status=TaskStatus.PROCESSING)
        
        # 0. 预先构建任务输出目录名 (格式: ID_模型组合_时间戳)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        product_id = Path(product.sample_dir).name
        
        # --- Step 0: 白底图预处理 (Optional) ---
        if need_white_bg:
            s0_start = time.time()
            logger.info("--- [Step 0: White Background Generation] ---")
            logger.info(f"Source Image for White BG: {product.image}")
            try:
                new_image_path = await self.white_bg_generator.process(product.image)
                product.image = new_image_path # 更新商品图片路径为白底图
                logger.info(f"✅ Step 0 Completed. Generated White BG: {product.image}")
            except Exception as e:
                logger.error(f"❌ Step 0 Failed: {e}")
                raise e
        else:
            logger.info("--- [Step 0: Skipped (User chose not to generate white BG)] ---")
            logger.info(f"Using existing image as reference: {product.image}")
        
        # 构建输出目录名称，包含关键配置信息以利于实验追踪
        folder_name = (
            f"{product_id}_"
            f"{self.summarizer.model_name}_"
            f"{self.refiner.model_name}_"
            f"{self.phrase_generator.model_name}_"
            f"{self.phrase_generator.prompt_type}_"
            f"{self.image_generator.provider.provider_name}_"
            f"{self.image_generator.provider.model_name}_"
            f"{timestamp}"
        )
        
        task_dir = settings.DATA_ROOT / "outputs" / folder_name
        task_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🚀 [Pipeline Start] Task ID: {task_id}")
        logger.info(f"📦 Product: {product.name} (ID: {product_id})")
        logger.info(f"📂 Output Directory: {task_dir}")
        logger.info(f"⚙️ Config: Type={self.phrase_generator.prompt_type}, Version={self.phrase_generator.prompt_version}")
        
        try:
            # --- Step 1: 视觉理解 (Visual Understanding) ---
            # 利用多模态大模型 (Qwen-VL) 分析商品图片，提取核心特征
            s1_start = time.time()
            logger.info("Step 1: Summarizing product")
            task.summary = await self.summarizer.process(product)
            self._save_intermediate(task_dir, f"01_scene_summarizer_{self.summarizer.model_name}", task.summary)
            logger.info(f"✅ Step 1 Completed in {time.time() - s1_start:.2f}s")
            
            # --- Step 2: 场景优化 (Scene Refining) ---
            # 利用 LLM 基于视觉描述扩展适合电商营销的场景列表
            s2_start = time.time()
            logger.info("Step 2: Refining scenes (Text Optimization & Expansion)...")
            task.refined_scene = await self.refiner.process(product, task.summary)
            self._save_intermediate(task_dir, f"02_scene_refiner_{self.refiner.model_name}", task.refined_scene)
            logger.info(f"✅ Step 2 Completed in {time.time() - s2_start:.2f}s. Total scenes: {len(task.refined_scene.scenes)}")
            
            # --- Step 3: 提示词生成 (Phrase Generation) ---
            # 将场景描述转化为具体的生图 Prompt
            s3_start = time.time()
            logger.info(f"Step 3: Generating scene phrases ({self.phrase_generator.prompt_type})...")
            task.phrase_result = await self.phrase_generator.process(product, task.refined_scene)
            self._save_intermediate(task_dir, f"03_phrase_generator_{self.phrase_generator.model_name}_{self.phrase_generator.prompt_type}", task.phrase_result)
            logger.info(f"✅ Step 3 Completed in {time.time() - s3_start:.2f}s. Generated {len(task.phrase_result.phrases)} phrases.")
            
            # --- Step 4: 图像生成 (Image Generation) ---
            # 调用配置的图像生成提供商 (Provider) 执行生图任务
            s4_start = time.time()
            logger.info(f"Step 4: Generating images with {self.image_generator.provider.provider_name}...")
            
            # 注入元数据，用于生图结果的文件命名或 Exif 信息
            metadata = {
                "product_id": product_id,
                "summarizer_model": self.summarizer.model_name,
                "refiner_model": self.refiner.model_name,
                "phrase_model": self.phrase_generator.model_name,
                "prompt_type": self.phrase_generator.prompt_type,
                "provider_name": self.image_generator.provider.provider_name,
                "image_model": self.image_generator.provider.model_name
            }
            
            task.image_result = await self.image_generator.process(
                product, 
                task.phrase_result, 
                task_dir, 
                metadata=metadata
            )
            logger.info(f"✅ Step 4 Completed in {time.time() - s4_start:.2f}s. Saved {len(task.image_result.images)} images.")
            
            # 标记任务成功
            task.status = TaskStatus.COMPLETED
            total_duration = time.time() - start_time
            logger.info(f"🎉 [Pipeline Success] Task {task_id} finished in {total_duration:.2f}s")
            
        except Exception as e:
            # 异常捕获与状态更新
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"❌ [Pipeline Failed] Task {task_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        return task
