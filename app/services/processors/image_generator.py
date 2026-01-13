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

    async def process(self, product: ProductInput, phrase_result: PhraseResult, output_dir: Path, metadata: dict = None) -> ImageGenerationResult:
        logger.info(f"Starting image generation for product: {product.name}")
        
        # 1. 使用指定的 image 路径作为原始商品图片
        original_image = None
        image_path = Path(product.image) if isinstance(product.image, str) else product.image
        
        if image_path.exists():
            try:
                original_image = PIL.Image.open(image_path)
                logger.debug(f"Using original image: {image_path}")
            except Exception as e:
                logger.error(f"Failed to open image {image_path}: {e}")
        
        if not original_image:
            raise Exception(f"No valid original image found for product {product.name} at {image_path}")

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
