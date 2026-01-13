import requests
import base64
import io
from pathlib import Path
from PIL import Image
from loguru import logger
from .base_provider import BaseImageProvider
from app.core.config import settings

class DeerApiProvider(BaseImageProvider):
    """
    DeerAPI 提供商实现，遵循 Gemini 官方 generateContent 协议。
    根据文档：https://apidoc.deerapi.com/guide-to-calling-gemini-image
    注意：DeerAPI 在 Gemini 协议中使用 snake_case 命名 (inline_data, mime_type)。
    """
    def __init__(self, model_name: str = None):
        super().__init__()
        self.provider_name = "deerapi"
        self.api_key = settings.DEERAPI_API_KEY or settings.GEMINI_API_KEY
        self.base_url = settings.DEERAPI_BASE_URL.rstrip('/')
        # 优先使用传入的模型名，否则从配置中读取
        self.model_name = model_name or settings.DEERAPI_MODEL

    async def generate_image(self, prompt: str, original_image: Image.Image, output_path: Path) -> bool:
        # 将 PIL 图片转换为 base64
        buffered = io.BytesIO()
        original_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # 接口路径：/v1beta/models/{model}:generateContent
        url = f"{self.base_url}/v1beta/models/{self.model_name}:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 严格遵循 DeerAPI 文档中的 snake_case 命名
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/png",
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
            logger.info(f"Calling DeerAPI (Gemini Protocol): {url}")
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            
            image_saved = False
            # 解析响应，文档显示图像数据在 candidates[0].content.parts 的 inline_data 中
            if "candidates" in data and data["candidates"]:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                for part in parts:
                    # 检查 snake_case 的 inline_data
                    if "inline_data" in part:
                        img_data_str = part["inline_data"].get("data")
                        if img_data_str:
                            img_data = base64.b64decode(img_data_str)
                            with open(output_path, "wb") as f:
                                f.write(img_data)
                            image_saved = True
                            break
                    # 兼容性检查 camelCase 的 inlineData
                    elif "inlineData" in part:
                        img_data_str = part["inlineData"].get("data")
                        if img_data_str:
                            img_data = base64.b64decode(img_data_str)
                            with open(output_path, "wb") as f:
                                f.write(img_data)
                            image_saved = True
                            break
            
            if not image_saved:
                logger.error(f"DeerAPI response did not contain image data: {data}")
            
            return image_saved
        except Exception as e:
            logger.error(f"DeerAPI generation error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response details: {e.response.text}")
            return False
