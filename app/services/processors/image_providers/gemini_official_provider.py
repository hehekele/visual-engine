import google.generativeai as genai
from pathlib import Path
from PIL import Image
from loguru import logger
from .base_provider import BaseImageProvider
from app.core.config import settings

class GeminiOfficialProvider(BaseImageProvider):
    """
    Google Gemini 官方 API 提供商。
    """
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        genai.configure(api_key=self.api_key)
        # 从配置中读取模型名称
        self.model_name = settings.GEMINI_MODEL
        try:
            self.model = genai.GenerativeModel(self.model_name)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Official model: {e}")
            self.model = None

    async def generate_image(self, prompt: str, original_image: Image.Image, output_path: Path) -> bool:
        if not self.model:
            logger.error("Gemini Official model is not initialized.")
            return False
            
        try:
            # 官方 SDK 调用
            response = self.model.generate_content([prompt, original_image])
            
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        with open(output_path, "wb") as f:
                            f.write(part.inline_data.data)
                        return True
            
            logger.warning(f"No image data in Gemini Official response for prompt: {prompt[:50]}...")
            return False
        except Exception as e:
            logger.error(f"Gemini Official generation error: {e}")
            return False
