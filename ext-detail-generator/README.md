# Visual Generator Extension

这是一个基于 [WXT](https://wxt.dev/) + Vue 3 开发的 Chrome 浏览器插件，作为 **Visual Engine** 的前端交互界面。它专门针对 1688 商品详情页设计，能够自动抓取商品数据并与后端 AI 服务联动，实现“一键生成电商场景图”的工作流。

## ✨ 核心功能

1.  **智能抓取 (Smart Grabbing)**
    *   自动识别并提取 1688 商品详情页的 **标题**、**橱窗主图**、**规格属性** 和 **详情图**。
    *   支持处理 Lazyload 图片和 Shadow DOM 中的隐藏内容。
    *   提供可视化界面供用户选择主图。

2.  **白底图生成与确认 (White BG Workflow)**
    *   在生成复杂场景前，先自动生成高质量白底图。
    *   提供对比预览功能，用户确认白底图无误后再进行后续生成，确保主体准确性。

3.  **AI 场景生成 (Scene Generation)**
    *   调用后端 Visual Engine API，基于商品信息和白底图自动生成多张营销场景图。
    *   支持实时轮询任务进度，动态展示生成结果。

4.  **非侵入式 UI**
    *   使用 Shadow DOM 技术注入页面，避免与原网页样式冲突。
    *   侧边栏抽屉式设计，可随时收起/展开。

## 🛠️ 技术栈

*   **框架**: [WXT](https://wxt.dev/) (Web Extension Tools)
*   **UI**: Vue 3 + TypeScript
*   **样式**: Scoped CSS (Shadow DOM 隔离)
*   **通信**: Background Script 代理请求 (解决 CORS 问题)

## 🚀 开发与安装

### 前置条件
确保后端服务 **Visual Engine API** 已在本地启动并运行于 `http://localhost:8000`。
*(详见项目根目录 `api_server.py`)*

### 1. 安装依赖
进入插件目录：
```bash
cd ext-detail-generator
pnpm install
```

### 2. 开发模式 (热重载)
```bash
pnpm dev
```
此命令会自动打开 Chrome 浏览器并加载插件。修改代码后会自动重新加载。

### 3. 构建生产版本
```bash
pnpm build
```
构建产物位于 `.output/chrome-mv3` 目录。

### 4. 手动加载插件
1.  打开 Chrome/Edge 浏览器，进入 **扩展程序管理页** (`chrome://extensions/`)。
2.  开启右上角的 **“开发者模式”**。
3.  点击 **“加载已解压的扩展程序”**。
4.  选择 `ext-detail-generator/.output/chrome-mv3` (构建后) 或 `ext-detail-generator/.wxt/chrome-mv3` (开发模式) 目录。

## 📂 目录结构

```text
ext-detail-generator/
├── components/
│   └── VisualGenerator.vue  # 核心 UI 组件：包含抓取、展示、交互逻辑
├── entrypoints/
│   ├── background.ts        # 后台脚本：负责代理 API 请求，跨域访问 localhost
│   └── generator.content.ts # 内容脚本：负责在 1688 页面注入 Shadow DOM
├── wxt.config.ts            # WXT 配置文件 (权限、Host 配置)
└── package.json
```

## ⚠️ 注意事项

*   **API 连接**: 插件默认连接 `http://localhost:8000`。如果后端端口变更，请修改 `components/VisualGenerator.vue` 中的 `BACKEND_URL` 常量。
*   **页面适配**: 目前仅适配 1688 商品详情页 (`detail.1688.com/offer/*.html`)。
*   **权限**: 插件仅申请了必要的 `storage` 权限和对本地 API 的访问权限。
