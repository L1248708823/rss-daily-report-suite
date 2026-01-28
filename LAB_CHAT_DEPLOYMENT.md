# Lab Chat（静态站）+ Node 代理部署说明

本页面（`web/src/views/LabChatView.vue`）用于验证“OpenAI 兼容”的国内中转站是否可用（含图片输入）。由于静态站在浏览器侧直连上游通常会遇到 CORS/Key 泄露问题，推荐架构是：

- 静态站：只负责 UI
- Node 代理：同源/近源转发到上游中转站，并处理 CORS/注入 Key/路径前缀等

本仓库提供的零依赖代理脚本：`tools/lab-openai-proxy.mjs`

---

## 目标架构（推荐）

1) 用户访问静态站（例如 `https://site.example.com`）
2) 静态站请求同源 `https://site.example.com/v1/chat/completions`
3) 站点的反向代理把 `/v1/*` 转发到 Node 代理
4) Node 代理再转发到上游中转站（例如 `https://right.codes/codex`）

这样做的好处：

- 浏览器不跨域（或跨域最小化）
- API Key 不需要出现在前端代码里（可由 Node 代理注入）
- 代理层可统一处理限流、日志、白名单、审计等

---

## 本地开发流程（你在本机执行）

### 1) 启动 Node 代理（零依赖）

仅开发时允许 CORS 到 Vite dev server：

```bash
LAB_OPENAI_UPSTREAM_BASE=https://right.codes/codex \
LAB_OPENAI_ALLOW_ORIGIN=http://localhost:5173 \
LAB_OPENAI_API_KEY=你的key \
node tools/lab-openai-proxy.mjs --port 8787
```

### 2) 启动前端

```bash
npm -C web run dev
```

说明：

- `LabChatView` 默认在 dev 环境会请求 `http://localhost:8787`（可用 `VITE_LAB_CHAT_PROXY_BASE` 覆盖）。
- 默认模型为 `gpt-5.2`（可用 `VITE_LAB_CHAT_MODEL` 覆盖）。
- 建议 Key 只放在代理环境变量 `LAB_OPENAI_API_KEY`，而不是前端。

---

## 生产部署：Node 代理

### 方式 A：独立域名/端口（简单，但会跨域）

- 静态站：`https://site.example.com`
- Node 代理：`https://api.example.com`（或 `https://site.example.com:8787`）

需要做的事：

- Node 代理设置 `LAB_OPENAI_ALLOW_ORIGIN=https://site.example.com`
- 前端构建时设置 `VITE_LAB_CHAT_PROXY_BASE=https://api.example.com`

缺点：

- 仍是跨域，依赖 CORS 正确配置

### 方式 B：同域路径反代（推荐）

- 静态站：`https://site.example.com`
- Node 代理：运行在内网 `http://127.0.0.1:8787`
- Nginx/网关：把 `https://site.example.com/openai/*` 转发到 Node

你可以让前端用同源路径作为代理 base：

- 构建环境设置：`VITE_LAB_CHAT_PROXY_BASE=/openai`
- Node 代理设置：`LAB_OPENAI_STRIP_PREFIX=/openai`

这样浏览器请求 `https://site.example.com/openai/v1/chat/completions`，
Node 会先剥离 `/openai`，再转发到上游 `/v1/chat/completions`。

---

## Node 代理可用环境变量（重点）

- `LAB_OPENAI_UPSTREAM_BASE`：上游中转站 Base URL（默认 `https://right.codes/codex`）
- `LAB_OPENAI_PORT`：监听端口（默认 8787）
- `LAB_OPENAI_ALLOW_ORIGIN`：CORS allow-origin（生产建议写死你的站点域名）
- `LAB_OPENAI_STRIP_PREFIX`：当代理挂载在子路径（如 `/openai`）时剥离前缀
- `LAB_OPENAI_API_KEY`：由代理注入 `Authorization: Bearer ...`（推荐）
- `LAB_OPENAI_FORCE_API_KEY=1`：强制覆盖客户端的 Authorization（更安全）

---

## 静态托管网站需要调整的内容（Checklist）

### 前端需要做的事

- 只需要预留 1 个“代理地址字段”：`VITE_LAB_CHAT_PROXY_BASE`
  - 本地 dev：默认 `http://localhost:8787`
  - 生产（推荐同域反代）：**不设置**（自动走同源 `/v1/*`）
  - 生产（同域挂在子路径）：设置为 `/openai`（配合 `LAB_OPENAI_STRIP_PREFIX=/openai`）
  - 生产（独立 API 域名）：设置为 `https://api.example.com`（会跨域，需要 CORS）
- （可选）设置默认模型：`VITE_LAB_CHAT_MODEL=gpt-5.2`
- 图片上传已在前端实现预览与发送（使用 `image_url` 的 Data URL 形式）

### 你需要在部署侧提供/确认的东西

- 你的静态站域名（例如 `https://site.example.com`）
- Node 代理部署位置
  - 是独立域名/端口，还是同域路径反代
- 是否有 Nginx/网关/边缘函数能力（决定能否做“同域反代”）
- 上游中转站是否需要额外 Header/鉴权形式（目前按 OpenAI Bearer Key）
- 允许的 CORS Origin 白名单（生产不建议用 `*`）
- 预计最大图片大小/并发量（图片用 base64 可能非常大，需要评估带宽与上游限制）

---

## 风险提示（建议你确认）

- 不建议把 Key 写进前端：静态站任何人都能查看构建产物。
- 推荐做法：Key 只放在代理环境变量 `LAB_OPENAI_API_KEY`，并开启 `LAB_OPENAI_FORCE_API_KEY=1` 强制覆盖客户端 Authorization。
- 图片用 base64 Data URL 会明显增大请求体：上游/代理可能有 body size 限制。
- 如果你用“独立域名”的代理方式，CORS 必须严格收敛到站点域名，否则容易被滥用。
