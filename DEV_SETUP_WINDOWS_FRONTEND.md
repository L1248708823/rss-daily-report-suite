# Windows 前端依赖安装清单（web/ · 重新来过版）

> 目标：按你指定的画风做一套「Cursor / PostHog 的精致产品感 + 微量“老报纸排版气质”」的阅读 UI。  
> 你只负责执行 `pnpm` 命令；我负责改代码与配置。

## 0) 前置条件

- Windows 10/11
- Node.js 版本满足 `web/package.json#engines`：`^20.19.0` 或 `>=22.12.0`
- 包管理器：`pnpm`（仓库已有 `web/pnpm-lock.yaml`）

## 1) 安装/确认 pnpm

```powershell
pnpm -v
```

如果没有 `pnpm`：

```powershell
npm i -g pnpm
pnpm -v
```

## 2) 安装 web/ 基础依赖（先跑起来）

```powershell
cd <你的仓库路径>\web
pnpm install
pnpm run dev
```

确认能打开页面后再继续装 UI 栈（避免“环境问题”和“代码问题”混在一起）。

## 3) 安装 UI 栈（我们接下来会用）

### 3.1 Tailwind（必选）

Tailwind v4 + 官方 Vite 插件（重点：**用 Vite 插件，避免 Tailwind 不生效**）：

```powershell
pnpm add -D tailwindcss @tailwindcss/vite @tailwindcss/typography @tailwindcss/forms
```

### 3.2 动效（轻量，克制使用）

VueUse Motion（用于“翻页/切换日期”的轻动效、列表入场节奏；不会做花里胡哨的大动效）：

```powershell
pnpm add @vueuse/motion
```

### 3.3 UI 原语（可选，但建议装上）

Headless UI（Vue 3 的无样式可访问组件原语，用于 Dropdown/Menu/Dialog 等，样式完全我们自己写，避免“组件库味”）：

```powershell
pnpm add @headlessui/vue
```

### 3.4 图标（可选）

```powershell
pnpm add lucide-vue-next
```

## 4) 安装后验证（必须做）

```powershell
pnpm run dev
pnpm run type-check
```

如果你遇到 pnpm “build scripts 被忽略（esbuild 等）”导致 Vite 启动失败：

```powershell
pnpm approve-builds
pnpm run dev
```

如果你怀疑 Tailwind 没生效，最快自检：
- 页面里随便给一个元素临时加 `class="text-red-500"`，刷新后应当立刻变红；
- 或者 F12 查看 computed style，确认 `flex/grid/gap/max-w` 等 Tailwind class 真在生效。

## 5) UI 调试（给我截图用）

你每次拉到最新代码后，只需要在 Windows 下执行：

```powershell
cd <你的仓库路径>\web
pnpm install
pnpm run dev
```

然后给我两张截图（不需要全屏，能看到版面即可）：
- 顶部报头（双横线）+ 工具条 + Market 顶栏（确认“报头像报纸、控件不抢头条”）
- Lead + Top stories（大卡片）+ All stories（细分隔列表两栏）（确认“Top 强于 All，且没有‘打开’箭头”）

> 提醒：我不会在 WSL 里做任何安装/依赖操作；所有 `pnpm install/add` 都由你在 Windows 里执行。

## 6) 你装完后我会做的代码改动（你不用动手）

- `vite.config.ts` 引入并启用 `@tailwindcss/vite`
- `src/assets/main.css` 引入 `@import "tailwindcss";`
- `main.ts` 注册 `MotionPlugin`（让 `v-motion` 指令可用）
- 重做 Home 页：不是“长文列表”，而是“头条 + 分栏版面 + 分类块 + 市场条 + 翻页”，整体像一份现代产品化的“数字报纸”
