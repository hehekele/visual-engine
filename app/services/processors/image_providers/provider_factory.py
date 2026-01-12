from typing import Dict, Type
from .base_provider import BaseImageProvider
from .gemini_official_provider import GeminiOfficialProvider
from .grsai_provider import GrsaiProvider
from .api147_provider import Api147Provider
from .deerapi_provider import DeerApiProvider
from app.core.config import settings

class ImageProviderFactory:
    """
    图像提供商工厂类，负责根据配置创建具体的提供商实例。
    """
    _providers: Dict[str, Type[BaseImageProvider]] = {
        "gemini": GeminiOfficialProvider,
        "grsai": GrsaiProvider,
        "147api": Api147Provider,
        "deerapi": DeerApiProvider
    }

    @classmethod
    def create(cls, provider_name: str = None) -> BaseImageProvider:
        """
        创建一个提供商实例。
        
        :param provider_name: 提供商名称（如 gemini, grsai, 147api, deerapi）
        :return: BaseImageProvider 的实例
        """
        # 优先从参数获取，否则从 settings 获取
        name = provider_name or settings.IMAGE_PROVIDER
        provider_cls = cls._providers.get(name.lower())
        
        if not provider_cls:
            raise ValueError(f"Unknown image provider: {name}. Available: {list(cls._providers.keys())}")
        
        return provider_cls()
