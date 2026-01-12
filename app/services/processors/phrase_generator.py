import json
from openai import OpenAI
from loguru import logger
from app.schemas import ProductInput, RefinedScene, PhraseResult, ScenePhrase
from app.core.config import settings
from .prompt_manager import PromptManager

class PhraseGenerator:
    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.model_name = "qwen-plus"
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.prompt_type = settings.PHRASE_PROMPT_TYPE
        self.prompt_version = settings.PHRASE_PROMPT_VERSION

    def _get_system_prompt(self, image_num: int, product_name: str, product_function: str, refined_scenes_text: str = "") -> str:
        """
        根据配置动态加载系统提示词。
        """
        system_prompt_tpl, _ = PromptManager.get_prompt(self.prompt_type, self.prompt_version)
        return system_prompt_tpl.format(
            image_num=image_num,
            product_name=product_name,
            product_function=product_function,
            refined_scenes=refined_scenes_text
        )

    async def process(self, product: ProductInput, refined_scene: RefinedScene) -> PhraseResult:
        logger.info(f"Generating scene phrases ({self.prompt_type} - {self.prompt_version}) for product: {product.name}")
        
        # 1. 解析场景来源配置
        source_config = {}
        try:
            for item in settings.PHRASE_SCENE_SOURCE_CONFIG.split(","):
                if ":" in item:
                    src, count = item.split(":")
                    source_config[src.strip()] = int(count.strip())
        except Exception as e:
            logger.warning(f"Failed to parse PHRASE_SCENE_SOURCE_CONFIG: {e}. Using default.")
            source_config = {"optimized": 3, "new": 2}

        # 2. 根据配置筛选场景
        selected_scenes_data = []
        logger.debug(f"Filtering scenes with config: {source_config}")
        for src, count in source_config.items():
            src_scenes = [s for s in refined_scene.scenes if s.source == src]
            selected = src_scenes[:count]
            selected_scenes_data.extend(selected)
            logger.debug(f"  - Source '{src}': selected {len(selected)}/{len(src_scenes)} scenes")
        
        if not selected_scenes_data:
            logger.warning("No scenes matched the source config. Using first 5 scenes.")
            selected_scenes_data = refined_scene.scenes[:5]
            
        image_num = len(selected_scenes_data)
        logger.info(f"Total scenes selected for phrase generation: {image_num}")
        
        # 3. 格式化筛选出的场景信息供提示词使用
        refined_scenes_text = ""
        for i, s in enumerate(selected_scenes_data):
            refined_scenes_text += f"\n### 场景候选 {i+1}\n"
            refined_scenes_text += f"- 场景名称: {s.scene_name}\n"
            refined_scenes_text += f"- 场景描述: {s.description}\n"
            refined_scenes_text += f"- 环境元素: {s.surrounding_objects}\n"
            refined_scenes_text += f"- 细节描述: {s.details}\n"
            refined_scenes_text += f"- 核心卖点: {s.selling_point}\n"

        # 4. 生成系统提示词
        system_prompt = self._get_system_prompt(
            image_num=image_num,
            product_name=product.name, 
            product_function=product.detail or "",
            refined_scenes_text=refined_scenes_text
        )
        logger.debug(f"System Prompt (length={len(system_prompt)}): \n{system_prompt}")

        messages = [
            {"role": "system", "content": "你是一位资深电商运营与海报摄影导演。"},
            {"role": "user", "content": system_prompt}
        ]
        
        # 加载对应的 positive_prompt_template
        _, positive_prompt_template = PromptManager.get_prompt(self.prompt_type, self.prompt_version)
        
        # 5. 统一的 Function Calling 结构
        if self.prompt_type == "structured":
            # 扩展参数以支持结构化填充
            properties = {
                "scenes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "scene_no": {"type": "integer"},
                            "scene_name": {"type": "string"},
                            "description": {"type": "string"},
                            "surrounding_objects": {"type": "string"},
                            "details": {"type": "string"},
                            "selling_point": {"type": "string"}
                        },
                        "required": ["scene_no", "scene_name", "description", "surrounding_objects", "details", "selling_point"]
                    }
                }
            }
        else:
            properties = {
                "scenes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "scene_no": {"type": "integer"},
                            "scene_description": {"type": "string"}
                        },
                        "required": ["scene_no", "scene_description"]
                    }
                }
            }

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "generate_scene_phrases",
                    "description": f"生成 {image_num} 条场景描述",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": ["scenes"]
                    }
                }
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "generate_scene_phrases"}}
            )
            
            tool_call = response.choices[0].message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments)
            logger.debug(f"LLM Response Arguments: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
            
            scenes = []
            for s in arguments.get("scenes", []):
                if self.prompt_type == "structured":
                    # 对于结构化模板，我们需要手动填充 template
                    filled_prompt = positive_prompt_template.replace("{{scene_name}}", s["scene_name"])
                    filled_prompt = filled_prompt.replace("{{description}}", s["description"])
                    filled_prompt = filled_prompt.replace("{{surrounding_objects}}", s["surrounding_objects"])
                    filled_prompt = filled_prompt.replace("{{details}}", s["details"])
                    filled_prompt = filled_prompt.replace("{{selling_point}}", s["selling_point"])
                    
                    scenes.append(ScenePhrase(
                        scene_no=s["scene_no"],
                        scene_description=filled_prompt
                    ))
                else:
                    scenes.append(ScenePhrase(**s))
            
            # 注意：对于 structured，返回的 phrases.scene_description 已经是完整提示词了
            # 所以 positive_prompt_template 我们传一个直接透传的占位符
            final_template = "{{}}" if self.prompt_type == "structured" else positive_prompt_template
            
            return PhraseResult(
                phrases=scenes,
                positive_prompt_template=final_template
            )

        except Exception as e:
            logger.error(f"Error generating scene phrases: {e}")
            raise e
