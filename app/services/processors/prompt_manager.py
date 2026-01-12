import importlib
from loguru import logger

class PromptManager:
    @staticmethod
    def get_prompt(prompt_type: str, version: str):
        """
        动态加载指定类型和版本的提示词。
        路径: app/resources/prompts/{prompt_type}/{version}.py
        """
        try:
            module_path = f"app.resources.prompts.{prompt_type}.{version}"
            module = importlib.import_module(module_path)
            
            system_prompt = getattr(module, "SYSTEM_PROMPT")
            positive_template = getattr(module, "POSITIVE_TEMPLATE")
            
            return system_prompt, positive_template
        except ImportError as e:
            logger.error(f"Failed to load prompt version '{version}' for type '{prompt_type}': {e}")
            raise Exception(f"Prompt version '{version}' not found for type '{prompt_type}'")
        except AttributeError as e:
            logger.error(f"Prompt module '{module_path}' missing required attributes: {e}")
            raise Exception(f"Invalid prompt module structure for '{module_path}'")
