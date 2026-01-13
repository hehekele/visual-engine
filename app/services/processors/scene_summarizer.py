import base64
import io
import json
import os
from pathlib import Path
from PIL import Image
from openai import OpenAI
from loguru import logger
from app.schemas import ProductInput, SceneSummary
from app.core.config import settings

class SceneSummarizer:
    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.model_name = "qwen-vl-plus"
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    def encode_image(self, image_path: Path):
        """
        Resizes image to 512x512 and encodes to base64.
        """
        try:
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                img = img.resize((512, 512))
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG")
                return base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            return None

    async def process(self, product: ProductInput) -> SceneSummary:
        logger.info(f"Summarizing product: {product.name} (Dir: {product.sample_dir})")
        
        image_contents = []
        valid_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        
        # 根据 sample_dir 获取绝对路径
        sample_path = Path(product.sample_dir)
        if not sample_path.is_absolute():
            sample_path = settings.DATA_ROOT / sample_path
        
        # 兼容性处理：如果路径中包含了多余的 data/ 前缀
        if not sample_path.exists() and "data" in sample_path.parts:
            parts = list(sample_path.parts)
            if parts.count("data") > 1:
                new_parts = []
                seen_data = False
                for p in parts:
                    if p == "data":
                        if not seen_data:
                            new_parts.append(p)
                            seen_data = True
                    else:
                        new_parts.append(p)
                sample_path = Path(*new_parts)

        # 1. 加载主参考图 (优先级：white_bg_main > main)
        # 注意：这里只选一张最合适的作为主参考
        primary_candidates = [
            "white_bg_main.jpg", "white_bg_main.png", 
            "white_bg.jpg", "white_bg.png", 
            "main.jpg", "main.png"
        ]
        
        for candidate in primary_candidates:
            img_path = sample_path / candidate
            if img_path.exists():
                base64_img = self.encode_image(img_path)
                if base64_img:
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                    })
                    logger.info(f"Loaded primary reference image: {candidate}")
                    break
        
        # 2. 加载 detail 目录下的详情图 (不再使用 sub_images)
        detail_images_path = sample_path / "detail"
        if detail_images_path.exists() and detail_images_path.is_dir():
            detail_files = sorted(os.listdir(detail_images_path))
            detail_count = 0
            for filename in detail_files:
                ext = os.path.splitext(filename)[1].lower()
                if ext in valid_extensions:
                    img_path = detail_images_path / filename
                    base64_img = self.encode_image(img_path)
                    if base64_img:
                        image_contents.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                        })
                        detail_count += 1
            if detail_count > 0:
                logger.info(f"Loaded {detail_count} detail images from detail/")

        if not image_contents:
            logger.warning(f"No valid images found for product {product.name} at {sample_path}")
        else:
            logger.info(f"Loaded total {len(image_contents)} images for analysis.")

        prompt_text = f"""
        产品名称：{product.name}
        产品描述：{product.detail or ""}
        产品规格参数：{product.attributes or ""}
        
        任务：
        请作为一名专业的电商视觉策划，结合产品的名称、描述以及规格参数，分析提供的参考图片内容，并输出标准的 JSON 格式数据。

        步骤 1：判断提供的参考图片内容是否与“产品名称”和“产品描述”一致。
        步骤 2：总结或推断适合该产品的使用场景（如果图片不符，请根据产品文本描述推断场景）。

        输出格式要求（必须是合法的 JSON）：
        {{
            "is_match": boolean,  // 图片是否符合产品描述，符合为 true，不符合为 false
            "mismatch_reason": string, // 如果不符合，请说明原因；如果符合，可为空字符串
            "scene_count": integer, // 总结的场景数量
            "scenes": [ // 场景列表
                {{
                    "id": integer, // 场景序号
                    "scene_name": string, // 场景名称
                    "description": string, // 场景描述（光线、氛围）
                    "surrounding_objects": string, // 周围物体
                    "details": string, // 细节展示
                    "selling_point": string // 卖点描述（关联功能）
                }}
            ]
        }}

        注意：
        1. 直接返回 JSON 字符串，不要包含 ```json 或其他 Markdown 标记。
        2. 场景描述要具体，具有画面感。
        3. 即使图片不匹配，也必须根据产品文本生成场景推荐。
        """
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    *image_contents
                ]
            }
        ]
        logger.debug(f"Summarizer Prompt (length={len(prompt_text)}): \n{prompt_text}")

        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
            )
            content = completion.choices[0].message.content
            logger.debug(f"Raw Qwen VL response: {content}")
            
            # Simple cleanup
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            json_data = json.loads(content)
            return SceneSummary(**json_data)
            
        except Exception as e:
            logger.error(f"Error calling Qwen VL: {e}")
            raise e
