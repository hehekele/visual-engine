import os
import PIL.Image
from pathlib import Path
from datetime import datetime
from loguru import logger
from app.schemas import ProductInput, PhraseResult, ImageGenerationResult, GeneratedImage
from app.core.config import settings
from .image_providers.provider_factory import ImageProviderFactory

class ImageGenerator:
    """
    图像生成处理器，负责调用具体的提供商生成图片。
    """
    def __init__(self):
        # 优先使用分项配置，如果没有则回退到默认生图配置
        provider_name = settings.SCENE_GEN_PROVIDER or settings.IMAGE_PROVIDER
        model_name = settings.SCENE_GEN_MODEL
        
        self.provider = ImageProviderFactory.create(
            provider_name=provider_name,
            model_name=model_name
        )
        logger.info(f"Initialized ImageGenerator with provider: {self.provider.provider_name}, model: {self.provider.model_name}")

    async def process(self, product: ProductInput, phrase_result: PhraseResult, output_dir: Path, metadata: dict = None, on_image_complete: callable = None) -> ImageGenerationResult:
        logger.info(f"--- [Image Generation Start] ---")
        logger.info(f"Product Name: {product.name}")
        
        # 1. 使用指定的 image 路径作为原始商品图片
        original_image = None
        image_path = Path(product.image) if isinstance(product.image, str) else product.image
        
        # 确保是绝对路径以方便日志查看
        # 💡 修复：如果 image_path 已经包含了 'data/'，不要重复拼接
        if not image_path.is_absolute():
            # 检查 image_path 的第一个部分是否已经是 settings.DATA_ROOT 的名称
            path_parts = image_path.parts
            if path_parts and path_parts[0] == Path(settings.DATA_ROOT).name:
                # 如果已经是 'data' 开头，则它是相对于工作目录的路径，或者是被误拼接的相对路径
                # 这里我们统一将其转为绝对路径
                image_path_abs = Path(os.getcwd()) / image_path
            else:
                image_path_abs = Path(settings.DATA_ROOT) / image_path
        else:
            image_path_abs = image_path
            
        # 再次确保最终路径中没有冗余的 data/data
        # 如果路径中有重复的 data 文件夹（例如 data/data/34/...），进行清理
        path_str = str(image_path_abs)
        data_name = Path(settings.DATA_ROOT).name
        redundant_pattern = f"{data_name}{os.sep}{data_name}{os.sep}"
        if redundant_pattern in path_str:
            path_str = path_str.replace(redundant_pattern, f"{data_name}{os.sep}")
            image_path_abs = Path(path_str)

        logger.info(f"Subject Reference Image: {image_path_abs}")
        
        if image_path_abs.exists():
            try:
                original_image = PIL.Image.open(image_path_abs)
                logger.info(f"Subject Reference Image: [LOADED SUCCESS]")
            except Exception as e:
                logger.error(f"Subject Reference Image: [LOAD FAILED] -> {e}")
        else:
            logger.error(f"Subject Reference Image: [NOT FOUND] -> {image_path_abs}")
        
        if not original_image:
            raise Exception(f"No valid original image found for product {product.name} at {image_path_abs}")

        # 2. 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        generated_images = []
        timestamp = datetime.now().strftime("%H%M%S")
        
        # 3. 遍历短语生成图片
        image_count = len(phrase_result.phrases)
        logger.info(f"Generating {image_count} images for product '{product.name}'")
        
        for i, phrase in enumerate(phrase_result.phrases):
            # 替换提示词模板中的占位符
            prompt = phrase_result.positive_prompt_template.replace("{{}}", phrase.scene_description)
            logger.info(f"[{i+1}/{image_count}] Processing scene {phrase.scene_no}...")
            logger.debug(f"Full generation prompt: {prompt}")
            
            # 构建符合要求的文件名
            if metadata:
                # 格式: 商品序号_sceneX_summarizer模型_refiner模型_phrase模型_prompt类型_服务商_生图模型_时间戳.png
                output_filename = (
                    f"{metadata['product_id']}_"
                    f"scene{phrase.scene_no}_"
                    f"{metadata['summarizer_model']}_"
                    f"{metadata['refiner_model']}_"
                    f"{metadata['phrase_model']}_"
                    f"{metadata['prompt_type']}_"
                    f"{metadata['provider_name']}_"
                    f"{metadata['image_model']}_"
                    f"{timestamp}.png"
                )
            else:
                output_filename = f"generated_{phrase.scene_no}_{timestamp}.png"
                
            output_path = output_dir / output_filename
            
            logger.info(f"Generating image {phrase.scene_no} using {self.provider.provider_name} ({self.provider.model_name})...")
            
            try:
                success = await self.provider.generate_image(prompt, original_image, output_path)
                
                if success:
                    generated_images.append(GeneratedImage(
                        scene_no=phrase.scene_no,
                        image_path=output_path,
                        prompt=prompt
                    ))
                    logger.info(f"  > Successfully saved to {output_path}")
                else:
                    logger.warning(f"  > Provider failed to generate image {phrase.scene_no}")
                    
            except Exception as e:
                logger.error(f"  > Unexpected error generating image {phrase.scene_no}: {e}")

        return ImageGenerationResult(images=generated_images)
