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
                return self._process_pil_image(img)
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            return None

    def _process_pil_image(self, img: Image.Image):
        """
        Helper to resize and encode a PIL Image object.
        """
        try:
            img = img.convert("RGB")
            img = img.resize((512, 512))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding PIL image: {e}")
            return None

    def stitch_images_9_patch(self, image_paths: list[Path], output_path: Path = None) -> str:
        """
        将最多 9 张图片拼接成 3x3 的九宫格，返回 base64 字符串。
        如果提供了 output_path，则将拼接后的图片保存到该路径。
        """
        grid_size = 3
        single_img_size = 512
        canvas_size = grid_size * single_img_size
        
        # 创建白色背景画布
        canvas = Image.new('RGB', (canvas_size, canvas_size), (255, 255, 255))
        
        for i, img_path in enumerate(image_paths[:9]):
            try:
                with Image.open(img_path) as img:
                    img = img.convert("RGB")
                    img = img.resize((single_img_size, single_img_size))
                    
                    row = i // grid_size
                    col = i % grid_size
                    canvas.paste(img, (col * single_img_size, row * single_img_size))
            except Exception as e:
                logger.error(f"Error stitching image {img_path}: {e}")
        
        # 如果指定了输出路径，保存图片
        if output_path:
            try:
                canvas.save(output_path, format="JPEG", quality=95)
                logger.info(f"Saved stitched 9-patch grid to: {output_path}")
            except Exception as e:
                logger.error(f"Error saving stitched image to {output_path}: {e}")
                
        return self._process_pil_image(canvas)

    async def process(self, product: ProductInput) -> SceneSummary:
        logger.info(f"Summarizing product: {product.name} (Dir: {product.sample_dir})")
        logger.info(f"--- [Visual Analysis Start] ---")
        
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

        # 1. 加载主参考图 (由 ProductInput 指定)
        # 遵循用户指令：如果没有生成 white_bg_main.jpg，使用 main.jpg；如果生成了，使用 white_bg_main.jpg
        primary_img_path = Path(product.image) if not isinstance(product.image, Path) else product.image
        
        # 💡 修复：防御性处理路径冗余，确保不会出现 data/data/
        if not primary_img_path.is_absolute():
            # 检查是否已经是 'data' 开头
            path_parts = primary_img_path.parts
            data_name = Path(settings.DATA_ROOT).name
            if path_parts and path_parts[0] == data_name:
                primary_img_path_abs = Path(os.getcwd()) / primary_img_path
            else:
                primary_img_path_abs = Path(settings.DATA_ROOT) / primary_img_path
        else:
            primary_img_path_abs = primary_img_path
            
        # 最终清理 redundant data/data
        path_str = str(primary_img_path_abs)
        redundant_pattern = f"{data_name}{os.sep}{data_name}{os.sep}"
        if redundant_pattern in path_str:
            path_str = path_str.replace(redundant_pattern, f"{data_name}{os.sep}")
            primary_img_path_abs = Path(path_str)

        if primary_img_path_abs.exists():
            base64_img = self.encode_image(primary_img_path_abs)
            if base64_img:
                image_contents.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                })
                logger.info(f"Primary Reference Image: [USED] -> {primary_img_path_abs}")
        else:
            logger.warning(f"Primary Reference Image: [NOT FOUND] -> {primary_img_path_abs}")
            # 备选方案：如果指定的图片不存在，则尝试在 sample_dir 下搜索常用名称
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
                        logger.info(f"Fallback Reference Image: [USED] -> {img_path}")
                        break
        
        # 2. 加载 detail 目录下的详情图 (进行九宫格拼接预处理)
        detail_images_path = sample_path / "detail"
        if detail_images_path.exists() and detail_images_path.is_dir():
            detail_files = sorted(os.listdir(detail_images_path))
            detail_paths = []
            for filename in detail_files:
                ext = os.path.splitext(filename)[1].lower()
                if ext in valid_extensions:
                    detail_paths.append(detail_images_path / filename)
            
            if detail_paths:
                logger.info(f"Stitching {len(detail_paths)} detail images into 9-patch grids...")
                # 每 9 张图一组进行拼接
                for i in range(0, len(detail_paths), 9):
                    batch = detail_paths[i:i+9]
                    grid_index = i // 9 + 1
                    output_filename = f"stitched_grid_{grid_index}.jpg"
                    output_path = detail_images_path / output_filename
                    
                    stitched_base64 = self.stitch_images_9_patch(batch, output_path=output_path)
                    if stitched_base64:
                        image_contents.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{stitched_base64}"}
                        })
                        logger.info(f"Added stitched 9-patch grid (Batch {grid_index}, images: {len(batch)})")
        
        logger.info(f"--- [Visual Analysis Context Built: {len(image_contents)} image contents total] ---")

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
