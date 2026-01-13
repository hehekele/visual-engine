from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    QWEN_API_KEY: str
    GEMINI_API_KEY: str

    # 图像生成配置
    IMAGE_PROVIDER: str = "gemini"  # gemini, 147api, grsai, deerapi
    
    # 分项生图配置 (可选，如果不设置则回退到 IMAGE_PROVIDER)
    WHITE_BG_PROVIDER: Optional[str] = None
    WHITE_BG_MODEL: Optional[str] = None
    SCENE_GEN_PROVIDER: Optional[str] = None
    SCENE_GEN_MODEL: Optional[str] = None
    
    # Grsai 配置
    GRSAI_API_KEY: Optional[str] = None
    GRSAI_BASE_URL: str = "https://grsai.dakka.com.cn"
    GRSAI_MODEL: str = "nano-banana-fast"  # 可选: nano-banana-fast, nano-banana-pro 等
    
    # 147api 配置
    API147_API_KEY: Optional[str] = None
    API147_BASE_URL: str = "https://api.147api.com"
    API147_MODEL: str = "gemini-2.5-flash-image" # 可选: gemini-2.5-flash-image
    
    # DeerAPI 配置
    DEERAPI_API_KEY: Optional[str] = None
    DEERAPI_BASE_URL: str = "https://api.deerapi.com"
    DEERAPI_MODEL: str = "gemini-2.5-flash-image" # 可选: gemini-3-pro-image, gemini-2.5-flash-image

    # 官方 Gemini 配置
    GEMINI_MODEL: str = "gemini-2.5-flash-image"
    
    # 提示词生成配置
    PHRASE_PROMPT_TYPE: str = "text"
    PHRASE_PROMPT_VERSION: str = "v1"
    # 场景来源配置，格式为 "source1:count1,source2:count2"
    PHRASE_SCENE_SOURCE_CONFIG: str = "optimized:3,new:2"

    # 路径配置
    DATA_ROOT: Path = Path("./data")
    EXCEL_PATH: str = "products.xlsx"
    PRODUCTS_JSON_PATH: str = "products.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def full_excel_path(self) -> Path:
        return self.DATA_ROOT / self.EXCEL_PATH

    @property
    def full_products_json_path(self) -> Path:
        return self.DATA_ROOT / self.PRODUCTS_JSON_PATH

settings = Settings()
