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
    def __init__(self):
        self.summarizer = SceneSummarizer()
        self.refiner = SceneRefiner()
        self.phrase_generator = PhraseGenerator()
        self.image_generator = ImageGenerator()
        self.white_bg_generator = WhiteBGGenerator()

    def _save_intermediate(self, task_dir: Path, step_name: str, data: any):
        """
        保存中间结果为 JSON 文件。
        """
        output_dir = task_dir / "intermediates"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{step_name}.json"
        filepath = output_dir / filename
        
        try:
            # 如果是 Pydantic 模型，使用 model_dump
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
        仅执行白底图生成步骤并返回生成的图片路径。
        """
        logger.info("Pipeline: Generating white background only...")
        new_image_path = await self.white_bg_generator.process(product.image)
        return new_image_path

    async def run(self, product: ProductInput, need_white_bg: bool = False) -> GenerationTask:
        start_time = time.time()
        task_id = str(uuid.uuid4())
        task = GenerationTask(task_id=task_id, product=product, status=TaskStatus.PROCESSING)
        
        # 0. 预先构建任务输出目录名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        product_id = Path(product.sample_dir).name
        
        # 如果需要生成白底图，先执行 Step 0
        if need_white_bg:
            s0_start = time.time()
            logger.info("Step 0: Generating white background (Gemini)...")
            try:
                new_image_path = await self.white_bg_generator.process(product.image)
                product.image = new_image_path
                logger.info(f"✅ Step 0 Completed in {time.time() - s0_start:.2f}s. New image: {product.image}")
            except Exception as e:
                logger.error(f"❌ Step 0 Failed: {e}")
                # 即使失败也继续，或者抛出异常取决于需求
                # 这里我们选择抛出异常，因为后续流程依赖白底图
                raise e
        
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
            # 1. Summarizer (Qwen VL)
            s1_start = time.time()
            logger.info("Step 1: Summarizing product (Visual Understanding)...")
            task.summary = await self.summarizer.process(product)
            self._save_intermediate(task_dir, f"01_scene_summarizer_{self.summarizer.model_name}", task.summary)
            logger.info(f"✅ Step 1 Completed in {time.time() - s1_start:.2f}s")
            
            # 2. Refiner (Qwen Text Optimization)
            s2_start = time.time()
            logger.info("Step 2: Refining scenes (Text Optimization & Expansion)...")
            task.refined_scene = await self.refiner.process(product, task.summary)
            self._save_intermediate(task_dir, f"02_scene_refiner_{self.refiner.model_name}", task.refined_scene)
            logger.info(f"✅ Step 2 Completed in {time.time() - s2_start:.2f}s. Total scenes: {len(task.refined_scene.scenes)}")
            
            # 3. Phrase Generator (Qwen Scene Phrases)
            s3_start = time.time()
            logger.info(f"Step 3: Generating scene phrases ({self.phrase_generator.prompt_type})...")
            task.phrase_result = await self.phrase_generator.process(product, task.refined_scene)
            self._save_intermediate(task_dir, f"03_phrase_generator_{self.phrase_generator.model_name}_{self.phrase_generator.prompt_type}", task.phrase_result)
            logger.info(f"✅ Step 3 Completed in {time.time() - s3_start:.2f}s. Generated {len(task.phrase_result.phrases)} phrases.")
            
            # 4. Image Generator (Multi-provider)
            s4_start = time.time()
            logger.info(f"Step 4: Generating images with {self.image_generator.provider.provider_name}...")
            
            # 为 ImageGenerator 注入元数据以便生成文件名
            metadata = {
                "product_id": product_id,
                "summarizer_model": self.summarizer.model_name,
                "refiner_model": self.refiner.model_name,
                "phrase_model": self.phrase_generator.model_name,
                "prompt_type": self.phrase_generator.prompt_type,
                "provider_name": self.image_generator.provider.provider_name,
                "image_model": self.image_generator.provider.model_name
            }
            
            task.image_result = await self.image_generator.process(product, task.phrase_result, task_dir, metadata=metadata)
            logger.info(f"✅ Step 4 Completed in {time.time() - s4_start:.2f}s. Saved {len(task.image_result.images)} images.")
            
            task.status = TaskStatus.COMPLETED
            total_duration = time.time() - start_time
            logger.info(f"🎉 [Pipeline Success] Task {task_id} finished in {total_duration:.2f}s")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(f"❌ [Pipeline Failed] Task {task_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
        return task
            
        return task
