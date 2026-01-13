# WXT + Vue 3

This template should help get you started developing with Vue 3 in WXT.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar).


## 安装
pnpm dlx wxt@latest init .

pnpm install

## 开发预览
pnpm dev

## 构建
pnpm build

## 打包
pnpm zip

## 调试方法
1. 运行 pnpm dev 启动开发服务器
2. 打开Chrome浏览器 -> 扩展程序 -> 勾选开发者模式 -> 加载未打包的扩展程序 -> 选择项目output目录中的chrome-mv3-dev目录
3. 浏览器会加载扩展程序，你可以在扩展程序列表中找到它
4. 打开浏览器控制台，查看控制台输出（这是页面console输出）
5. 回到扩展程序，点击插件的检查视图 Service Worker（这是扩展程序后端console输出，就是background.js中的console输出）