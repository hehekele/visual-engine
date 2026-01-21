# Visual Engine

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-green)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.0%2B-42b883)](https://vuejs.org/)
[![WXT](https://img.shields.io/badge/WXT-Extension-orange)](https://wxt.dev/)

## 🌟 核心特性

*   **全流程自动化**：从商品抓取 -> 视觉理解 -> 场景策划 -> 提示词生成 -> 图像生成，一键完成。
*   **智能视觉理解**：集成 **Qwen-VL** 多模态大模型，深度分析商品材质、卖点与适用场景。
*   **多模型协同**：
    *   **Scene Refiner**: 使用 **Qwen-Plus** 扩展和优化营销场景。
    *   **Image Generator**: 支持 **Google Gemini**等多种生图引擎。
*   **浏览器插件集成**: 提供基于 **WXT + Vue 3** 的 Chrome 插件，直接在 1688 详情页进行可视化操作。
*   **白底图工作流**: 内置智能抠图与白底图生成，确保 AI 生图的主体一致性。

## 🏗️ 系统架构

系统由两部分组成：

1.  **Backend (Visual Engine API)**: 基于 FastAPI 的核心服务，负责 AI 任务调度与流水线编排。
2.  **Frontend (Extension)**: 运行在浏览器端的侧边栏插件，负责数据采集与结果展示。

### 目录结构
```text
visual-engine/
├── api_server.py           # 后端服务入口
├── app/                    # 后端核心代码
│   ├── core/               # 全局配置 (Config, Logging)
│   ├── services/           # 业务逻辑
│   │   ├── pipeline.py     # 核心流水线指挥官
│   │   └── processors/     # AI 处理器 (Summarizer, Refiner, Generator...)
│   └── schemas.py          # 数据模型定义
├── data/                   # 数据存储 (生成的图片、JSON 记录)
├── ext-detail-generator/   # 前端浏览器插件源码 (WXT + Vue3)
├── requirements.txt        # 后端依赖
└── TECH_DOC.md             # 技术文档
└── .env                    # 配置文件
```

## 🚀 快速开始

### 1. 环境准备

*   Python 3.10+
*   Node.js 18+ 
*   API Key

### 2. 后端部署

1.  **克隆项目并安装依赖**:
    ```bash
    git clone <repository_url>
    cd visual-engine
    pip install -r requirements.txt
    ```

2.  **配置环境变量**:
    在项目根目录创建 `.env` 文件，填入必要的 API Key：
    ```env
    QWEN_API_KEY=your_qwen_api_key
    GEMINI_API_KEY=your_gemini_api_key
    # 可选配置
    IMAGE_PROVIDER=gemini
    ```

3.  **启动服务**:
    ```bash
    python api_server.py
    ```
    服务将运行在 `http://localhost:8000`。
    API 文档地址: `http://localhost:8000/docs`

### 3. 前端插件安装

1.  **进入插件目录**:
    ```bash
    cd ext-detail-generator
    pnpm install
    ```

2.  **开发模式运行**:
    ```bash
    pnpm dev
    ```
    这将自动打开一个安装了插件的 Chrome 浏览器实例。

3.  **手动安装**:
    运行 `pnpm build`，然后在 Chrome 扩展管理页加载 `.output/chrome-mv3` 目录。

## 💡 使用指南

1.  确保后端服务已启动。
2.  在 Chrome 中打开任意 **1688 商品详情页**。
3.  点击页面右侧的 **"AI 视觉助手"** 悬浮按钮展开面板。
4.  点击 **"一键抓取商品"** 获取当前商品信息。
5.  确认或生成 **白底图**。
6.  点击 **"生成商品主图"**，系统将自动分析商品并生成多张营销场景图。

## 📖 技术文档

更详细的模块说明、接口定义及函数列表，请查阅 TECH_DOC.md  
