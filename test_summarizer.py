import asyncio
import os
import sys
from pathlib import Path

# 将项目根目录添加到 python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.processors.scene_summarizer import SceneSummarizer
from app.schemas import ProductInput
from app.core.config import settings

async def test_summarizer_with_data_45():
    print("--- Starting SceneSummarizer Test (Data/45) ---")
    
    # 1. 准备测试数据
    product = ProductInput(
        name="测试商品-45",
        detail="测试详情-45",
        attributes="测试属性-45",
        sample_dir="45",  # 对应 data/45
        image="45/white_bg_main.jpg"  # 假设已有白底图，或者改为 main.jpg
    )
    
    # 检查路径是否存在
    sample_path = settings.DATA_ROOT / product.sample_dir
    if not sample_path.exists():
        print(f"❌ Error: Directory {sample_path} does not exist!")
        return

    # 2. 初始化处理器
    summarizer = SceneSummarizer()
    
    # 3. 执行分析
    try:
        print(f"Analyzing product in: {sample_path}")
        result = await summarizer.process(product)
        
        print("\n--- Analysis Result ---")
        print(f"Is Match: {result.is_match}")
        print(f"Mismatch Reason: {result.mismatch_reason}")
        print(f"Scene Count: {result.scene_count}")
        for scene in result.scenes:
            print(f"\nScene {scene.id}: {scene.scene_name}")
            print(f"  Description: {scene.description}")
            print(f"  Selling Point: {scene.selling_point}")
        print("--- End of Result ---\n")
        
    except Exception as e:
        print(f"❌ Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_summarizer_with_data_45())
