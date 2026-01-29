# 云服务器安装 Codex CLI（Linux）手把手

> 适用：Ubuntu/Debian/CentOS 等常见发行版；要求 Node.js ≥ 18。当前日期：2026-01-28。

## 1. 基础依赖
```bash
sudo apt update && sudo apt install -y curl ca-certificates
# CentOS/RedHat 可用：sudo yum install -y curl ca-certificates
```

## 2. 安装 Node.js（推荐 22.x LTS，若已≥18可跳过）
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v    # 确认 ≥18
```

## 3. 安装 Codex CLI（官方 npm 包）
```bash
sudo npm i -g @openai/codex
codex --version
```
- 若机器不允许全局 npm，先装 nvm/fnm，再 `npm i -g @openai/codex`。
- 备选：直接下载二进制（x86_64/aarch64）：`https://github.com/openai/codex/releases/latest`，解压后把 `codex` 放到 `/usr/local/bin/`。

## 4. 首次登录
```bash
codex
```
- 选择 “Sign in with ChatGPT” 最简单（需 Plus/Pro/Business/Edu/Enterprise 账户）。  
- 如用 API Key：导出环境变量后运行：
  ```bash
  export OPENAI_API_KEY="sk-..."
  codex
  ```
- 登录信息保存在 `~/.codex/`，重登可删 `~/.codex/auth.json` 再运行 `codex login`。

## 5. 权限与审批模式（建议先保守）
- 默认“建议模式”需你确认每次编辑/命令。  
- 想降低摩擦：`codex --auto-edit` 或 `codex --full-auto`，但务必在服务器上保持目录最小化、敏感文件外移。  
- 进入 TUI 后 `/approvals` 可切换。

## 6. 常用命令
```bash
codex --upgrade          # 升级 CLI
codex --help             # 查看全局参数
codex --status           # 会话内查看当前模型/模式
/model gpt-5-codex       # 会话内切换模型
```

## 7. 服务器使用注意
- 建议为 Codex 单独建工作目录，避免误操作全盘。  
- 若需要代理，设置 `HTTPS_PROXY`/`HTTP_PROXY` 环境变量。  
- 防火墙或出网受限需放行 api.openai.com 443。  
- 日志与缓存：`~/.codex/`（可定期清理）。

## 8. 失败排查速查
- `codex: command not found`：确认 npm 全局 bin 已在 PATH（`npm config get prefix`，常见 `/usr/local/bin`）。  
- `node: not found` 或版本过低：重装 Node.js 22.x。  
- 登录卡住/打不开浏览器：选择“复制链接到浏览器”，完成后回终端。  
- 反复 401：检查账号权限或更换 API Key。

> 按以上步骤执行即可在 Linux 云服务器上装好 Codex；若遇到发行版差异或无 npm 权限，改用发布页二进制方案。
