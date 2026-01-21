# Visual Engine

## 1. 核心服务

### 1.1 API 服务入口 (`api_server.py`)
**文件路径**: [api_server.py](api_server.py)
**描述**: FastAPI 应用入口，负责 RESTful API 路由、后台任务调度、静态文件服务及简单的内存任务状态管理。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `generate_scene` | `request: GenerateRequest`, `background_tasks: BackgroundTasks` | `GenerateResponse` | **POST /api/generate**<br>异步端点，创建生图任务。初始化任务状态，将 `run_pipeline_task` 加入后台队列。 |
| `get_task_status` | `task_id: str` | `dict` | **GET /api/task/{task_id}**<br>获取任务状态（pending/processing/completed/failed）、生成图片 URL 及 Base64 预览。 |
| `run_pipeline_task` | `task_id: str`, `request: GenerateRequest` | `None` | **后台核心逻辑**<br>1. **资源准备**: 如果 `save_to_data=True`，下载橱窗/详情图到 `data/{index}`，并保存 `products.json`。<br>2. **输入解析**: 确定主图路径（支持 Path/Base64/URL）。<br>3. **流水线执行**: 根据 `white_bg_only` 标记决定执行 `run_white_bg_only` 或完整 `run`。<br>4. **状态更新**: 任务结束时更新 `tasks_db`。 |
| `get_next_product_index` | 无 | `int` | 读取 `products.json` 计算下一个可用的自增商品序号，用于数据目录隔离。 |
| `save_product_to_json` | `product_data: dict` | `None` | 线程安全地将商品元数据写入 `data/products.json`。 |

### 1.2 全局配置 (`app/core/config.py`)
**文件路径**: [app/core/config.py](app/core/config.py)
**描述**: 基于 Pydantic 的 `Settings` 类，管理环境变量与全局常量。

| 属性/方法 | 类型 | 默认值/描述 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `IMAGE_PROVIDER` | `str` | `gemini` | 默认图像生成服务商 (gemini, 147api, grsai, deerapi)。 |
| `WHITE_BG_PROVIDER` | `str` | `None` | 专用于白底图生成的服务商。未设置时回退到 `IMAGE_PROVIDER`。 |
| `SCENE_GEN_PROVIDER` | `str` | `None` | 专用于场景图生成的服务商。未设置时回退到 `IMAGE_PROVIDER`。 |
| `PHRASE_PROMPT_TYPE` | `str` | `structured` | 提示词生成模式 (`structured` 模板填充 / `text` 直接生成)。 |
| `PHRASE_SCENE_SOURCE_CONFIG` | `str` | `optimized:3, new:2` | 定义从 Refiner 结果中选取多少个“优化场景”和“新增场景”。 |
| `DATA_ROOT` | `Path` | `data` | 数据存储根目录。 |

### 1.3 核心流水线 (`app/services/pipeline.py`)
**文件路径**: [app/services/pipeline.py](app/services/pipeline.py)
**描述**: 负责按顺序编排 AI 处理器，管理数据流转、中间结果保存和错误处理。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `run` | `product: ProductInput`, `need_white_bg: bool` | `GenerationTask` | **全流程入口**<br>1. **预处理 (Step 0)**: 若 `need_white_bg=True`，先调用 `WhiteBGGenerator` 生成白底图作为后续步骤的参考图。<br>2. **视觉理解 (Step 1)**: `SceneSummarizer` 分析商品。<br>3. **场景优化 (Step 2)**: `SceneRefiner` 扩展场景。<br>4. **提示词生成 (Step 3)**: `PhraseGenerator` 生成 Prompt。<br>5. **图像生成 (Step 4)**: `ImageGenerator` 批量生图。<br>输出目录命名格式: `ID_模型组合_时间戳`。 |
| `run_white_bg_only` | `product: ProductInput` | `Path` | **子流程入口**<br>仅调用 `WhiteBGGenerator` 生成白底图，不进行后续场景生成。 |
| `_save_intermediate` | `task_dir: Path`, `step_name: str`, `data: Any` | `None` | 辅助函数，将中间步骤的 Pydantic 模型或字典保存为 JSON 文件，便于调试。 |

### 1.4 数据加载服务 (`app/services/data_loader.py`)
**文件路径**: [app/services/data_loader.py](app/services/data_loader.py)
**描述**: 提供从 JSON 或 Excel 文件批量加载商品数据的工具类。

| 类/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `JSONDataLoader.load_products` | 无 | `List[ProductInput]` | 读取 `products.json`，解析并转换为 `ProductInput` 对象列表。 |
| `ExcelDataLoader.load_products` | 无 | `List[ProductInput]` | 读取 Excel 文件，自动修复 `data/` 路径冗余问题，转换为 `ProductInput` 对象列表。 |

---

## 2. AI 处理器 (Processors)

### 2.1 场景总结 (`app/services/processors/scene_summarizer.py`)
**文件路径**: [app/services/processors/scene_summarizer.py](app/services/processors/scene_summarizer.py)
**描述**: 使用 Qwen-VL 多模态大模型分析商品图片，提取场景特征、卖点和细节。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `process` | `product: ProductInput` | `SceneSummary` | **核心处理**<br>1. **图片加载**: 优先使用 `product.image`，若不存在则尝试 `white_bg_main.jpg` 等备选名。<br>2. **详情图拼接**: 将详情图每 9 张拼成一个 3x3 九宫格，减少 Token 消耗。<br>3. **LLM 分析**: 调用 Qwen-VL 输出结构化 JSON 总结。 |
| `stitch_images_9_patch` | `image_paths: list[Path]`, `output_path: Path` | `str` (Base64) | 将最多 9 张图片拼合成一张 3x3 的大图，以减少 LLM Token 消耗并保留细节。 |
| `encode_image` | `image_path: Path` | `str` (Base64) | 读取图片并调整大小为 512x512，转为 Base64 编码。 |

### 2.2 场景优化 (`app/services/processors/scene_refiner.py`)
**文件路径**: [app/services/processors/scene_refiner.py](app/services/processors/scene_refiner.py)
**描述**: 使用 Qwen-Plus (纯文本 LLM) 基于视觉分析结果，扩展和优化电商营销场景。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `process` | `product: ProductInput`, `summary: SceneSummary` | `RefinedScene` | **核心处理**<br>执行两个子任务：<br>1. **优化 (Optimize)**: 润色 `SceneSummary` 中已有的场景。<br>2. **扩展 (Expand)**: 基于商品属性头脑风暴 5 个新的营销场景。<br>最终合并输出结构化的场景列表。 |

### 2.3 提示词生成 (`app/services/processors/phrase_generator.py`)
**文件路径**: [app/services/processors/phrase_generator.py](app/services/processors/phrase_generator.py)
**描述**: 将自然语言的场景描述转换为具体的生图 Prompt（支持结构化或文本模板）。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `process` | `product: ProductInput`, `refined_scene: RefinedScene` | `PhraseResult` | **核心处理**<br>1. **场景筛选**: 解析配置 `PHRASE_SCENE_SOURCE_CONFIG` (如 "optimized:3, new:2")，从 Refiner 结果中挑选指定数量的场景。<br>2. **提示词加载**: 根据 `prompt_type` (`structured`/`text`) 动态加载对应的 System Prompt 和 Template。<br>3. **LLM 调用**: 使用 Function Calling 模式生成参数。<br>   - **Structured 模式**: LLM 生成 `scene_name`, `description`, `details` 等字段，代码端负责填充到 `POSITIVE_TEMPLATE`。<br>   - **Text 模式**: LLM 直接生成完整的 `scene_description`。<br>4. **结果组装**: 返回包含最终 Prompt 的 `PhraseResult`。 |
| `_get_system_prompt` | `image_num`, `product_name` 等 | `str` | 格式化 System Prompt 模板，注入商品信息和场景列表。 |

### 2.4 图像生成控制 (`app/services/processors/image_generator.py`)
**文件路径**: [app/services/processors/image_generator.py](app/services/processors/image_generator.py)
**描述**: 图像生成的业务层，负责调用底层的 `ImageProvider` 并处理文件保存。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `__init__` | 无 | - | 初始化 Provider。优先使用 `SCENE_GEN_PROVIDER`，否则回退到 `IMAGE_PROVIDER`。 |
| `process` | `product`, `phrase_result`, `output_dir`, `metadata` | `ImageGenerationResult` | **核心处理**<br>1. 遍历 Prompt 列表。<br>2. 构造包含元数据的文件名 (如 `ID_sceneX_models...png`)。<br>3. 调用 `self.provider.generate_image` 执行生图。<br>4. 保存成功生成的图片路径。 |

### 2.5 白底图生成 (`app/services/processors/white_bg_generator.py`)
**文件路径**: [app/services/processors/white_bg_generator.py](app/services/processors/white_bg_generator.py)
**描述**: 专门用于生成白底图的处理器。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `__init__` | 无 | - | 初始化 Provider。优先使用 `WHITE_BG_PROVIDER`，否则回退到 `IMAGE_PROVIDER`。 |
| `process` | `image_path: Path` | `Path` | **核心处理**<br>1. 使用固定的白底图 Prompt (`Simple white background...`)。<br>2. 调用 `ImageProvider` 生成图片。<br>3. 返回新生成的白底图路径。 |


### 2.6 提示词管理 (`app/services/processors/prompt_manager.py`)
**文件路径**: [app/services/processors/prompt_manager.py](app/services/processors/prompt_manager.py)
**描述**: 管理 Prompt 模板的动态加载。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `get_prompt` | `prompt_type: str`, `version: str` | `(str, str)` | 动态导入 `app.resources.prompts.{type}.{version}` 模块，返回 `SYSTEM_PROMPT` 和 `POSITIVE_TEMPLATE`。 |

### 2.7 提示词模板库 (`app/resources/prompts/`)
系统支持两种类型的 Prompt 模板，分别适用于不同的生图模型或风格需求。

#### 1. Structured 模式 (`app/resources/prompts/structured/v1.py`)
**文件路径**: [app/resources/prompts/structured/v1.py](app/resources/prompts/structured/v1.py)
**适用场景**: 需要高度控制画面元素、光影、构图的场景，通常对接支持复杂指令的生图模型（如 Gemini 2.0 Flash）。
**原理**:
*   **System Prompt**: 指导 LLM 输出 `scene_name`, `description`, `details` 等结构化字段。
*   **Positive Template**: 一个 JSON 格式的指令模板，包含 `foreground`, `background`, `photography` 等字段。Python 代码会将 LLM 生成的字段填充到此 JSON 模板中，形成最终发给生图模型的指令。

#### 2. Text 模式 (`app/resources/prompts/text/v1.py`)
**文件路径**: [app/resources/prompts/text/v1.py](app/resources/prompts/text/v1.py)
**适用场景**: 只需要简单的自然语言描述，或者对接的模型对长指令支持不佳。
**原理**:
*   **System Prompt**: 指导 LLM 直接输出一段完整的场景描述短语 (20-40字)。
*   **Positive Template**: 一个简单的文本模板 (如 "把图像中的商品，放在带有{{}}的场景中...")。Python 代码将 LLM 生成的短语直接填入 `{{}}` 处。

#### 3. 提示词生成逻辑 (`app/services/processors/phrase_generator.py`)
`PhraseGenerator` 会根据全局配置 `PHRASE_PROMPT_TYPE` 自动选择不同的生成策略。核心在于构造 LLM 的 `tools` 定义时，使用了不同的 JSON Schema：

*   **当 `PHRASE_PROMPT_TYPE="structured"` 时**：
    构造复杂的 `tools` 参数，要求 LLM 返回包含 `scene_name`, `description`, `surrounding_objects`, `details`, `selling_point` 等字段的 JSON 对象。
    代码收到响应后，会将这些字段一一替换到 `structured/v1.py` 定义的 `POSITIVE_TEMPLATE` 中。

*   **当 `PHRASE_PROMPT_TYPE="text"` 时**：
    构造简单的 `tools` 参数，仅要求 LLM 返回 `scene_description` 字段。
    代码收到响应后，直接将该描述填入 `text/v1.py` 定义的简单模板中。

## 3. 图像提供商 (Image Providers)

### 3.1 抽象基类 (`app/services/processors/image_providers/base_provider.py`)
**文件路径**: [app/services/processors/image_providers/base_provider.py](app/services/processors/image_providers/base_provider.py)
**描述**: 定义所有图像生成服务商必须实现的接口。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `generate_image` | `prompt: str`, `original_image: Image`, `output_path: Path` | `bool` | **抽象方法**<br>子类必须实现此方法以对接具体的 API。成功返回 `True`，失败返回 `False`。 |

### 3.2 工厂类 (`app/services/processors/image_providers/provider_factory.py`)
**文件路径**: [app/services/processors/image_providers/provider_factory.py](app/services/processors/image_providers/provider_factory.py)
**描述**: 简单工厂模式，用于创建 Provider 实例。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `create` | `provider_name: str`, `model_name: str` | `BaseImageProvider` | 根据名称 (`gemini`, `147api`, `grsai`, `deerapi`) 实例化对应的 Provider 类。 |

### 3.3 具体实现 (Implementations)

以下脚本位于 `app/services/processors/image_providers/` 目录下，均实现了 `generate_image` 接口。

| 脚本文件 | Provider 名称 | 特点与逻辑 |
| :--- | :--- | :--- |
| `gemini_official_provider.py` | `GeminiOfficial` | **Google Gemini API**<br>使用 `google.generativeai` 库。模型默认为 `gemini-2.0-flash-exp`。支持原生 Image-to-Image。 |
| `grsai_provider.py` | `Grsai` | **Grsai API**<br>通过 HTTP POST 请求 `/v1/chat/completions`。支持 OpenAI 格式的调用。 |
| `api147_provider.py` | `147api` | **147 API**<br>HTTP POST 请求。参数包含 `prompt`, `image_base64`, `model` 等。 |
| `deerapi_provider.py` | `DeerAPI` | **Deer API**<br>HTTP POST 请求。**特殊处理**: 参数键名采用 snake_case (如 `guidance_scale`)，而非常见的 camelCase。 |

---

## 4. 数据模型 (Data Models)

### 4.1 数据定义 (`app/schemas.py`)
**文件路径**: [app/schemas.py](app/schemas.py)
**描述**: 定义全系统通用的 Pydantic 数据模型。

| 类名 | 用途 | 关键字段 |
| :--- | :--- | :--- |
| `ProductInput` | 原始商品输入 | `name`, `detail`, `attributes`, `image` (Path), `sample_dir` |
| `SceneSummary` | 场景总结结果 | `is_match`, `scenes` (List[SceneItem]) |
| `RefinedScene` | 场景优化结果 | `scenes` (List[SceneItem]) |
| `PhraseResult` | 提示词结果 | `phrases` (List[ScenePhrase]), `positive_prompt_template` |
| `GenerationTask` | 任务状态聚合 | `task_id`, `status`, `summary`, `refined_scene`, `phrase_result`, `image_result` |
| `GenerateRequest` | API 请求体 | `name`, `image_url`, `gallery_images`, `need_white_bg`, `save_to_data` |

---

## 5. 前端插件 (Frontend Plugin: ext-detail-generator)

本文档部分涵盖 `ext-detail-generator` 目录下的浏览器插件代码，该插件基于 [WXT](https://wxt.dev/) 框架和 Vue 3 开发。

### 5.1 核心 UI 组件 (`components/VisualGenerator.vue`)
**文件路径**: [ext-detail-generator/components/VisualGenerator.vue](ext-detail-generator/components/VisualGenerator.vue)
**描述**: 插件的主界面组件，负责 1688 商品数据抓取、用户交互、API 调用及流程控制。

| 函数/方法 | 输入参数 | 返回值 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `handleGrab` | 无 | `void` | **抓取流程入口**<br>1. 调用 `grabProductInfo` 获取页面数据。<br>2. 切换状态至 `grabbed`。<br>3. 自动生成白底图（调用 `handleGenerateWhiteBg`）。 |
| `grabProductInfo` | 无 | `Promise<{title, galleryUrls, ...}>` | **数据抓取核心**<br>1. 从 DOM 中提取标题 (h1)。<br>2. 提取橱窗图 (`#gallery`)，处理 lazyload 属性。<br>3. 提取属性表格 (`.offer-attr-list`)。<br>4. 提取详情图 (`.desc-img-loaded`)。 |
| `handleGenerateWhiteBg` | 无 | `void` | **白底图生成**<br>1. 构造 `GenerateRequest`。<br>2. 发送 `API_REQUEST` 消息给 Background Script。<br>3. 轮询任务状态直至完成或失败。<br>4. 成功后切换状态至 `white_bg_review`。 |
| `handleGenerate` | `useWhiteBg: boolean` | `void` | **全流程生成**<br>用户确认白底图后触发（或直接生成）。调用后端 API (`need_white_bg: false`) 执行完整生图流程，并启动轮询。 |
| `startPolling` | 无 | `void` | **状态轮询**<br>每 2 秒调用一次 API (`GET /api/task/{taskId}`) 查询任务状态。处理 `processing`, `completed`, `failed` 状态。 |

### 5.2 内容脚本 (`entrypoints/generator.content.ts`)
**文件路径**: [ext-detail-generator/entrypoints/generator.content.ts](ext-detail-generator/entrypoints/generator.content.ts)
**描述**: 注入到 1688 详情页的内容脚本，负责创建隔离的 Shadow DOM UI 容器。

| 函数/属性 | 类型/参数 | 描述 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `matches` | `Array<string>` | 配置 | 定义插件生效的 URL 规则，目前匹配 `detail.1688.com/offer/*.html` 等。 |
| `main` | `ctx` | `void` | **入口函数**<br>1. 使用 `createShadowRootUi` 创建 Shadow DOM 容器 (避免样式冲突)。<br>2. 将 Vue 应用挂载到 Shadow Root 中。<br>3. 注入位置：`body` 标签末尾。 |

### 5.3 后台脚本 (`entrypoints/background.ts`)
**文件路径**: [ext-detail-generator/entrypoints/background.ts](ext-detail-generator/entrypoints/background.ts)
**描述**: 运行在后台 Service Worker 中，作为 Content Script 与外部 API 之间的代理，解决 CORS 跨域问题。

| 监听事件 | 消息类型 | 处理逻辑 | 功能描述 |
| :--- | :--- | :--- | :--- |
| `browser.runtime.onMessage` | `API_REQUEST` | 代理请求 | 接收前端的 API 请求配置 (url, method, body)，在后台发起真实的 `fetch` 请求，并将结果回传给 Content Script。 |

### 5.4 插件配置 (`wxt.config.ts`)
**文件路径**: [ext-detail-generator/wxt.config.ts](ext-detail-generator/wxt.config.ts)
**描述**: WXT 框架的配置文件。

| 配置项 | 值/内容 | 作用 |
| :--- | :--- | :--- |
| `modules` | `['@wxt-dev/module-vue']` | 启用 Vue 3 支持。 |
| `manifest.permissions` | `['storage']` | 申请浏览器存储权限。 |
| `manifest.host_permissions` | `['http://localhost:8000/*']` | 允许插件访问本地后端 API。 |


