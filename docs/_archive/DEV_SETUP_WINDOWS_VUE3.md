# Windows 本地开发环境搭建（你来操作 / 给 Codex 配合用）

你这台电脑是 **Windows**，而 Codex 在 **WSL** 里改代码；所以安装 Node/Vue 相关工具这部分需要你在 Windows 上完成。本文档的目标是：让你在 Windows 侧把前端环境装好、把 `web/`（Vue3 + Vite）脚手架创建出来，后续我在 WSL 里负责写代码与维护仓库文件。

## 0. 推荐终端与目录
- 推荐用 **Windows Terminal** + **PowerShell**。
- 仓库路径（示例）：`E:\skills\rss-daily-report-suite`
- 你后续的命令都在仓库根目录执行（除非注明 `cd web`）。

## 1. 安装 Node.js（Windows）
二选一即可（选你熟悉的）：

### 方案 A：直接装 Node LTS（最简单）
1) 去 Node.js 官网下载并安装 LTS（一路 Next）。
2) 新开 PowerShell，验证：
```powershell
node -v
npm -v
```

### 方案 B：用 fnm（推荐，方便切换版本）
1) 安装 fnm（Windows 版）
```powershell
winget install Schniz.fnm
```
2) 配置 PowerShell 启动脚本（照着 fnm 提示做；不同版本提示略有差异）。
3) 安装并启用 LTS：
```powershell
fnm install --lts
fnm use --lts
node -v
```

## 2. 启用 pnpm（用 corepack）
```powershell
corepack enable
corepack prepare pnpm@latest --activate
pnpm -v
```

> 如果提示 `corepack` 不存在：说明 Node 版本过旧，请回到上一步换成 LTS。

## 3. 创建 Vue3 项目（目录 `web/`）
在仓库根目录：
```powershell
pnpm create vue@latest web
```

交互选项建议（MVP）：
- TypeScript：Yes
- Vue Router：Yes
- Pinia：No（先不用）
- ESLint：Yes
- Prettier：Yes
- Vitest/Cypress：No（后面再加）

安装依赖：
```powershell
cd web
pnpm install
```

## 4. 启动前端开发服务
```powershell
pnpm dev
```

浏览器打开：
- `http://localhost:5173`

## 5. 你需要回传给我的信息（用于我在 WSL 侧对齐）
请把以下命令输出贴给我：
```powershell
node -v
pnpm -v
type web\\package.json
```

## 6. 常见坑（按出现概率排序）
- `pnpm install` 很慢：多数是网络/代理问题；如果你在用代理，请在 Windows 侧配置 npm/pnpm 代理或设置系统代理。
- 文件被 WSL/Windows 同时占用：尽量不要同时在 WSL 和 Windows 跑 `pnpm install`；以 Windows 为准装依赖即可。
- 路径带中文/空格导致脚本异常：尽量把仓库放在英文路径（你现在 `E:\skills\...` 就很好）。

