import json
from openai import OpenAI
from loguru import logger
from app.schemas import ProductInput, SceneSummary, RefinedScene
from app.core.config import settings

class SceneRefiner:
    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.model_name = "qwen-plus"
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    async def process(self, product: ProductInput, summary: SceneSummary) -> RefinedScene:
        logger.info(f"Refining scenes for product: {product.name}")
        
        # Prepare example scene from input data for prompt
        first_scene_str = ""
        if summary.scenes:
            example_scene = summary.scenes[0].model_dump()
            if "source" not in example_scene:
                example_scene["source"] = "optimized_original"
            first_scene_str = json.dumps(example_scene, ensure_ascii=False, indent=8)
        else:
            first_scene_str = json.dumps({
                "id": 1, 
                "scene_name": "示例", 
                "source": "optimized_original"
            }, ensure_ascii=False, indent=8)

        # Construct Prompt
        prompt = f"""
            ### 角色设定
            你是一位资深电商运营与海报摄影导演，将帮助我生成商品展示海报的“场景短语”。所有描述必须用于**静态**的商品展示海报，画面必须是静止的瞬间，而非动态视频。

            ### 商品信息
            - 名称：{product.name}
            - 描述：{product.detail or ""}

            ### 输入 JSON 数据
            以下是需要优化和泛化的原始 JSON 数据，请基于此进行操作：
            {summary.model_dump_json(indent=2)}

            ### 任务 1：优化现有场景
            1. 遍历输入 JSON 中 `scenes` 列表，对每个场景的 `description`（场景描述）、`surrounding_objects`（周围物体）、`details`（细节展示）和 `selling_point`（卖点展示）进行优化。
            2. **更清晰**：用具象名词和视觉动作替代抽象形容词，使描述直观且易于想象。
            3. **更简单**：简化句子结构，使其符合 Stable Diffusion 或 Midjourney 风格的提示词，但保持中文表达。
            4. **画面化**：确保 `details` 和 `selling_point` 的内容描述的是画面元素或视觉特写，而非功能说明。

            ### 任务 2：扩展新场景
            1. 结合产品名称、描述及输入 JSON 中已有的场景内容，发散思维但保持合理，在此基础上额外生成 5 个新的静态商品展示场景。
            2. 泛化维度包括：使用场景（室内、户外、办公、休闲等）、时间/季节（春夏秋冬、不同时段光线）、背景主题（现代都市、自然风光、简约摄影棚等）、情绪氛围（温馨、活力、专业、奢华等）。
            3. 避免与原有场景重复，也不要天马行空；每个新场景应突出商品特色并符合品牌风格。
            4. 为新场景生成唯一的 `id`（在现有最大 `id` 基础上顺延）和简洁独特的 `scene_name`。

            ### 输出格式
            请将优化后的原有场景和新增的 5 个场景合并为一个新的 `scenes` 列表，每个场景对象必须包含以下字段：
            - `id`: 数字标识，不重复。
            - `scene_name`: 概括场景主题的名称。
            - `description`: 对场景画面的整体描述，静态的画面，不要有产品本身或者使用产品的描述存在。
            - `surrounding_objects`: 出现在画面中的其他物体，用逗号分隔。
            - `details`: 需要突出的视觉细节，如光影、材质特写等，禁止出现跟产品相关或者产品替代物的描述。
            - `selling_point`: 突出卖点的画面展示方式。
            - `source`: 对原有场景填入 "optimized"，对新增场景填入 "new"。

            ### 示例场景（仅供参考，用于理解结构）
            {first_scene_str}

            ### 输出要求
            - 请直接返回修改后的完整 JSON 数据，不要包含任何 Markdown 标记（如 ```json）。
            - 输出的根对象应该至少包含 `scenes` 字段，且结构与示例一致。
        """
        logger.debug(f"Refiner Prompt (length={len(prompt)}): \n{prompt}")

        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
            )
            
            content = completion.choices[0].message.content.strip()
            logger.debug(f"Raw Qwen Refiner response: {content}")
            
            # Simple cleanup
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
                
            refined_data = json.loads(content)
            return RefinedScene(**refined_data)

        except Exception as e:
            logger.error(f"Error calling Qwen for refinement: {e}")
            raise e
