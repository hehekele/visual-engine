import pandas as pd
import json
from pathlib import Path
from typing import List
from loguru import logger
from app.schemas import ProductInput
from app.core.config import settings

class JSONDataLoader:
    def __init__(self):
        self.json_path = settings.full_products_json_path
        self.data_root = settings.DATA_ROOT

    def load_products(self) -> List[ProductInput]:
        logger.info(f"Loading products from {self.json_path}")
        
        if not self.json_path.exists():
            logger.error(f"JSON file not found: {self.json_path}")
            return []

        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            products = []
            for item in data:
                sample_dir = str(item.get("index", ""))
                name = item.get("name", "")
                detail = item.get("detail", "")
                image_relative_path = item.get("image", "")
                
                image_path = Path(image_relative_path)
                if not image_path.is_absolute():
                    image_path = self.data_root / image_path
                
                product = ProductInput(
                    sample_dir=sample_dir,
                    name=name,
                    detail=detail,
                    image=image_path
                )
                products.append(product)
                
            logger.info(f"Successfully loaded {len(products)} products")
            return products
        except Exception as e:
            logger.exception(f"Error loading JSON file: {e}")
            return []

class ExcelDataLoader:
    def __init__(self):
        self.excel_path = settings.full_excel_path
        self.data_root = settings.DATA_ROOT

    def load_products(self) -> List[ProductInput]:
        logger.info(f"Loading products from {self.excel_path}")
        
        if not self.excel_path.exists():
            logger.error(f"Excel file not found: {self.excel_path}")
            return []

        try:
            # 适配用户提供的 4 列: sample_dir, name, detail, image
            df = pd.read_excel(self.excel_path)
            products = []
            
            for _, row in df.iterrows():
                sample_dir = str(row.get("sample_dir", ""))
                name = str(row.get("name", ""))
                detail = str(row.get("detail", "")) if pd.notna(row.get("detail")) else ""
                image_relative_path = str(row.get("image", ""))
                
                # image 列存放的是主图文件的路径
                image_path = Path(image_relative_path)
                if not image_path.is_absolute():
                    image_path = self.data_root / image_path
                
                # 兼容性处理：如果路径中包含了多余的 data/ 前缀
                if not image_path.exists() and "data" in image_path.parts:
                    parts = list(image_path.parts)
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
                        image_path = Path(*new_parts)
                
                product = ProductInput(
                    sample_dir=sample_dir,
                    name=name,
                    detail=detail,
                    image=image_path
                )
                products.append(product)
                
            logger.info(f"Successfully loaded {len(products)} products")
            return products
        except Exception as e:
            logger.exception(f"Error loading Excel file: {e}")
            return []
