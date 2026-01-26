# WSL 本地开发环境搭建（Vue 3 + 本仓库）

本文给你一份“照着复制粘贴就能跑”的清单：在 **WSL（Ubuntu/Debian）** 内安装 Node + pnpm，并创建/启动 Vue3 项目（Vite）。

## 0. 前置确认
- 你在 WSL 终端执行（不是 Windows PowerShell）。
- WSL 能访问外网（能 `curl https://registry.npmjs.org -I`）。

## 1. 安装 Node（推荐 nvm）
1) 安装基础依赖
```bash
sudo apt update
sudo apt install -y curl ca-certificates build-essential
```

2) 安装 nvm（Node 版本管理器）
```bash
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
```

3) 让 nvm 生效（任选其一）
- 方式 A：关闭并重新打开 WSL 终端
- 方式 B：手动加载
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
```

4) 安装并使用 LTS Node
```bash
nvm install --lts
nvm use --lts
node -v
npm -v
```

## 2. 安装 pnpm（推荐 corepack）
```bash
corepack enable
corepack prepare pnpm@latest --activate
pnpm -v
```

> 如果 `corepack` 不存在：说明 Node 版本过旧，请回到上一步用 `nvm install --lts`。

## 3. 在仓库内创建 Vue3 项目（目录 `web/`）
在仓库根目录执行（你现在就在 `/mnt/e/skills/rss-daily-report-suite`）：
```bash
pnpm create vue@latest web
```

交互选项建议（MVP）：
- TypeScript：Yes
- Vue Router：Yes
- Pinia：No（先不用）
- ESLint：Yes
- Prettier：Yes
- Vitest/Cypress：No（后面再加）

然后安装依赖：
```bash
cd web
pnpm install
```

## 4. 启动 Vue3 本地开发（Windows 浏览器可访问）
```bash
pnpm dev --host 0.0.0.0 --port 5173
```

在 Windows 浏览器打开：
- `http://localhost:5173`

## 5.（可选）验证本仓库 Python 日报脚本仍可运行
在仓库根目录：
```bash
python3 -m pip install -U pip
python3 -m pip install requests
python3 .codex/skills/rss-daily-report/scripts/run.py --dry-run --per-feed-limit 5 --max-items 10
```

## 6. 你需要回传给我确认的 3 个信息
你执行完后，把以下输出贴给我（我用来对齐代码与脚本）：
```bash
node -v
pnpm -v
cat web/package.json
```

## 7. 常见故障排查（最少够用版）
- `pnpm create vue@latest` 很慢/卡住：通常是网络或 DNS；先确认 `curl https://registry.npmjs.org -I`。
- Windows 访问不到 dev server：确保用 `--host 0.0.0.0`，并确认端口没被占用（换 `--port 5174`）。
- 权限/编译报错：确保装了 `build-essential`（第 1 步已装）。

