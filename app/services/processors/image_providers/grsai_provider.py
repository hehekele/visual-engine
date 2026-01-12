import requests
import base64
import io
from pathlib import Path
from PIL import Image
from loguru import logger
from .base_provider import BaseImageProvider
from app.core.config import settings

class GrsaiProvider(BaseImageProvider):
    """
    Grsai 提供商实现，支持 Gemini 官方接口格式，模型名为 nano-banana-fast。
    """
    def __init__(self):
        super().__init__()
        self.provider_name = "grsai"
        self.api_key = settings.GRSAI_API_KEY or settings.GEMINI_API_KEY
        self.base_url = settings.GRSAI_BASE_URL.rstrip('/')
        # 从配置中读取模型名称
        self.model_name = settings.GRSAI_MODEL

    async def generate_image(self, prompt: str, original_image: Image.Image, output_path: Path) -> bool:
        # 将 PIL 图片转换为 base64
        buffered = io.BytesIO()
        original_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # 根据用户示例，使用 v1beta 接口
        # 提示：如果 :generateContent 不支持，可以尝试 :streamGenerateContent
        url = f"{self.base_url}/v1beta/models/{self.model_name}:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 使用 Gemini 官方接口格式
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": img_base64
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"]
            }
        }

        try:
            logger.info(f"Calling Grsai: {url}")
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()
            
            image_saved = False
            # 解析 Gemini 响应格式
            if "candidates" in data and data["candidates"]:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        img_data = base64.b64decode(part["inlineData"]["data"])
                        with open(output_path, "wb") as f:
                            f.write(img_data)
                        image_saved = True
                        break
            
            if not image_saved:
                logger.error(f"Grsai response did not contain image data: {data}")
            
            return image_saved
        except Exception as e:
            logger.error(f"Grsai generation error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response details: {e.response.text}")
            return False
