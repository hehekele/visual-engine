import PIL.Image
from pathlib import Path
from loguru import logger
from app.core.config import settings
from .image_providers.provider_factory import ImageProviderFactory

GEMINI_WHITE_BG_PROMPT = """
Identify the main product in the uploaded photo (automatically removing any hands holding it or messy background details).
Recreate it as a premium e-commerce product shot .
Subject Isolation :
Cleanly extract the product, completely removing any fingers, hands, or clutter .
Background : Place the product on a pure white studio background (RGB 255, 255, 255) with no shadow at all — remove any contact shadow or gradient so the background is perfectly uniform.
Lighting : Use soft, commercial studio lighting to highlight the product's texture and material. Ensure even illumination with no harsh glare.
Retouching : Automatically fix any lens distortion, improve sharpness, and color-correct to make the product look brand new and professional .
"""

class WhiteBGGenerator:
    """
    白底图生成处理器，复用 ImageGenerator 的提供商机制。
    支持官方 Gemini API 及第三方代理服务。
    """
    def __init__(self):
        # 优先使用分项配置，如果没有则回退到默认生图配置
        provider_name = settings.WHITE_BG_PROVIDER or settings.IMAGE_PROVIDER
        model_name = settings.WHITE_BG_MODEL
        
        self.provider = ImageProviderFactory.create(
            provider_name=provider_name,
            model_name=model_name
        )
        logger.info(f"Initialized WhiteBGGenerator with provider: {self.provider.provider_name}, model: {self.provider.model_name}")

    async def process(self, image_path: Path) -> Path:
        """
        生成白底图并保存，返回新图片路径。
        """
        logger.info(f"Generating white background for: {image_path}")
        
        # 1. 打开原始图片
        try:
            base_img = PIL.Image.open(image_path)
        except Exception as e:
            logger.error(f"Failed to open source image for white bg: {e}")
            raise e

        # 2. 准备输出路径
        output_path = image_path.parent / f"white_bg_{image_path.stem}.jpg"
        
        # 3. 调用提供商生成图片
        try:
            logger.info(f"Calling provider {self.provider.provider_name} for white background generation...")
            success = await self.provider.generate_image(
                prompt=GEMINI_WHITE_BG_PROMPT,
                original_image=base_img,
                output_path=output_path
            )
            
            if not success:
                raise RuntimeError(f"Provider {self.provider.provider_name} failed to generate white background")
                
            logger.info(f"White background image successfully saved to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"White background generation failed: {e}")
            raise e
        finally:
            base_img.close()
