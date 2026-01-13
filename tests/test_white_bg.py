import asyncio
import sys
import os
from pathlib import Path

# 将当前目录添加到 sys.path 以便导入 app
sys.path.append(os.getcwd())

from app.services.processors.white_bg_generator import WhiteBGGenerator

async def main():
    generator = WhiteBGGenerator()
    image_path = Path("./tests/bg6.jpg")
    
    if not image_path.exists():
        print(f"Error: {image_path} not found!")
        return

    try:
        print(f"Starting white background generation for {image_path}...")
        output_path = await generator.process(image_path)
        print(f"Success! White background image saved to: {output_path}")
    except Exception as e:
        print(f"Failed to generate white background: {e}")

if __name__ == "__main__":
    asyncio.run(main())
