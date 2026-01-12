from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image

class BaseImageProvider(ABC):
    """
    图像生成服务商基类，定义统一的生图接口。
    """
    def __init__(self):
        self.provider_name = "unknown"
        self.model_name = "unknown"

    @abstractmethod
    async def generate_image(self, prompt: str, original_image: Image.Image, output_path: Path) -> bool:
        """
        根据提示词和原始图片生成新图片。
        
        :param prompt: 生成提示词
        :param original_image: 原始 PIL 图片对象
        :param output_path: 生成图片的保存路径
        :return: 是否生成成功
        """
        pass
