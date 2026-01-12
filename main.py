import asyncio
import json
from app.core.logging import logger, setup_logging
from app.services.data_loader import ExcelDataLoader
from app.services.pipeline import ProductImagePipeline

async def main():
    setup_logging()
    logger.info("Initializing Visual Engine Pipeline")
    
    # 1. Load Data
    loader = ExcelDataLoader()
    products = loader.load_products()
    
    if not products:
        logger.warning("No products found to process. Please check your Excel file and DATA_ROOT.")
        return

    # 2. Run Pipeline
    pipeline = ProductImagePipeline()
    
    tasks = []
    for product in products:
        task = await pipeline.run(product)
        tasks.append(task)
    
    # 3. Print Results
    logger.info("-" * 50)
    logger.info("Pipeline Execution Results Summary:")
    for task in tasks:
        status_icon = "✅" if task.status == "completed" else "❌"
        logger.info(f"{status_icon} Product: {task.product.name} (Dir: {task.product.sample_dir})")
        if task.status == "completed":
            if task.summary:
                logger.info(f"   - Scenes Found (VL): {len(task.summary.scenes)}")
            if task.phrase_result:
                logger.info(f"   - Generated Phrases (Qwen):")
                for phrase in task.phrase_result.phrases:
                    logger.info(f"     [{phrase.scene_no}] {phrase.scene_description}")
            if task.image_result:
                logger.info(f"   - Generated Images (Gemini):")
                for img in task.image_result.images:
                    logger.info(f"     [{img.scene_no}] Saved to: {img.image_path}")
        else:
            logger.error(f"   - Error: {task.error}")
    logger.info("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
