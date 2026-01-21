import base64
from io import BytesIO
from typing import Optional

from google import genai
from PIL import Image, UnidentifiedImageError


GEMINI_WHITE_BG_PROMPT = """
Identify the main product in the uploaded photo (automatically removing any hands holding it or messy background details).
Recreate it as a premium e-commerce product shot .
Subject Isolation :
Cleanly extract the product, completely removing any fingers, hands, or clutter .
Background : Place the product on a pure white studio background (RGB 255, 255, 255) with no shadow at all — remove any contact shadow or gradient so the background is perfectly uniform.
Lighting : Use soft, commercial studio lighting to highlight the product's texture and material. Ensure even illumination with no harsh glare.
Retouching : Automatically fix any lens distortion, improve sharpness, and color-correct to make the product look brand new and professional .
"""


def _extract_image_from_gemini_response(response) -> Optional[Image.Image]:
    def open_from_bytes(data_bytes: bytes) -> Image.Image:
        buf = BytesIO(data_bytes)
        buf.seek(0)
        img_probe = Image.open(buf)
        img_probe.verify()
        buf.seek(0)
        return Image.open(buf).convert("RGB")

    for cand in getattr(response, "candidates", []) or []:
        content = getattr(cand, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            inline = getattr(part, "inline_data", None)
            if not inline:
                continue
            raw = getattr(inline, "data", None)
            if raw is None:
                continue
            try:
                if isinstance(raw, (bytes, bytearray)):
                    return open_from_bytes(bytes(raw))
                try:
                    data_bytes = base64.b64decode(raw)
                    return open_from_bytes(data_bytes)
                except Exception:
                    data_bytes = raw.encode("utf-8")
                    return open_from_bytes(data_bytes)
            except (UnidentifiedImageError, OSError):
                continue
    return None


def generate_white_bg_with_gemini(client: genai.Client, model_name: str, image_path: str) -> Image.Image:
    base_img = Image.open(image_path)
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[GEMINI_WHITE_BG_PROMPT, base_img],
        )
    finally:
        base_img.close()

    img = _extract_image_from_gemini_response(response)
    if img is None:
        raise RuntimeError("未能从 Gemini 返回中解析出图片")
    return img

