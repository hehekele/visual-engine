import json
import copy
import requests
import base64
import io
from pathlib import Path
from PIL import Image
from loguru import logger
from .base_provider import BaseImageProvider
from app.core.config import settings

class Api147Provider(BaseImageProvider):
    """
    147api 提供商实现，支持 Nano-banana 比例配置。
    """
    def __init__(self, model_name: str = None):
        super().__init__()
        self.provider_name = "147api"
        self.api_key = settings.API147_API_KEY or settings.GEMINI_API_KEY
        self.base_url = settings.API147_BASE_URL.rstrip('/')
        # 优先使用传入的模型名，否则从配置中读取
        self.model_name = model_name or settings.API147_MODEL

    async def generate_image(self, prompt: str, original_image: Image.Image, output_path: Path) -> bool:
        # 将 PIL 图片转换为 base64
        buffered = io.BytesIO()
        original_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

        url = f"{self.base_url}/v1beta/models/{self.model_name}:generateContent"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 根据 147api 文档，使用 Gemini 兼容格式
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
            logger.info(f"Calling 147api: {url}")
            # 记录请求负载（隐藏 base64 图片数据）
            log_payload = copy.deepcopy(payload)
            if log_payload["contents"][0]["parts"][1].get("inlineData"):
                log_payload["contents"][0]["parts"][1]["inlineData"]["data"] = "<BASE64_IMAGE_DATA_TRUNCATED>"
            logger.debug(f"Request Payload: {json.dumps(log_payload, ensure_ascii=False, indent=2)}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()
            
            # 记录响应摘要（隐藏 base64 图片数据）
            log_data = copy.deepcopy(data)
            if "candidates" in log_data and log_data["candidates"]:
                for part in log_data["candidates"][0].get("content", {}).get("parts", []):
                    if "inlineData" in part:
                        part["inlineData"]["data"] = "<BASE64_IMAGE_DATA_TRUNCATED>"
            logger.debug(f"Response Data Summary: {json.dumps(log_data, ensure_ascii=False, indent=2)}")
            
            # 解析响应，Gemini 格式通常在 candidates[0].content.parts 中
            image_saved = False
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
                logger.error(f"147api response did not contain image data: {data}")
            
            return image_saved
        except Exception as e:
            logger.error(f"147api generation error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response details: {e.response.text}")
            return False
