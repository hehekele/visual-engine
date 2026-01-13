# Visual Generator Extension

这是一个专门用于商品详情页的 AI 场景图生成插件。

## 功能
1. **自动抓取**：在 1688 或 AliExpress 商品详情页，点击“抓取信息”自动提取标题和主图。
2. **AI 生成**：调用后端 `visual-engine` 接口，基于抓取的商品信息生成电商场景图。
3. **结果展示**：直接在浏览器插件内查看并下载生成的场景图。

## 开发与安装

### 1. 启动后端服务器
在项目根目录下运行：
```bash
python api_server.py
```
服务器将运行在 `http://localhost:8000`。

### 2. 编译插件
进入 `ext-detail-generator` 目录：
```bash
pnpm install
pnpm dev
```

### 3. 加载插件
1. 打开 Chrome 浏览器 -> 扩展程序 -> 开启开发者模式。
2. 点击“加载已解压的扩展程序”。
3. 选择 `ext-detail-generator/output/chrome-mv3-dev` 目录。

## 适配网站
- 1688 详情页 (`detail.1688.com/offer/*.html`)
- AliExpress 详情页 (`aliexpress.com/item/*.html`)
