bro # Web 部署方案备选（供 Review）

> 目标：把 `web/` 阅读页面部署到公网可访问，并且每天自动生成/更新 `NewsReport/data/*.json` 与日报 Markdown；同时保留“需要在生成阶段做编辑挑选（rss-editor-picks）”的能力。

## 0. 现状与约束（决定方案边界）

### 0.1 生成侧（数据怎么来）
- 生成命令：`python3 .codex/skills/rss-daily-report/scripts/run.py`
- 生成产物：
  - `NewsReport/data/YYYY-MM-DD.json` + `NewsReport/data/index.json`
  - `NewsReport/YYYY-MM-DD-rss-daily-report.md`
- 后处理：脚本会自动调用 `rss-editor-picks` 回写 `pin/title_zh/summary` 并把“头条/精选”区块写入 Markdown。
- 当前实现不依赖任何 API/key（可选 OpenAI 仅是增强项，不是必需）。

### 0.2 展示侧（Web 如何读取数据）
`web` 前端通过固定接口读数据：
- `GET /api/news/index.json`
- `GET /api/news/YYYY-MM-DD.json`

注意：这是“绝对路径”。如果部署在 GitHub Pages 这类“非站点根路径”（如 `/repo/`）的场景，需要做一次适配（后续再改代码即可，本文件先只说明风险）。

另外：本仓库的 `web` 在开发态（`pnpm dev`）由 Vite 中间件临时提供 `/api/news/*`；生产部署（EdgeOne/Pages）必须确保发布目录里真实存在 `api/news/*.json`，否则会 404。

### 0.3 域名与 HTTPS
- **没有域名也能部署**：可以用服务器 IP 访问，或用平台提供的默认子域名（如 `*.pages.dev / *.vercel.app / EdgeOne 项目域名`）。
- **没有域名也能 HTTPS 吗？**
  - 平台默认子域名一般自带 HTTPS。
  - 自建服务器用 IP 做 HTTPS 通常不方便（证书签发与浏览器信任问题），但 HTTP 访问完全可用；也可以后续再加域名。

---

## 1) 方案 A：腾讯云服务器单机部署（推荐：最贴近你现在的约束）

### A1. “最省事”版本：服务器 + 定时任务 + Nginx/Caddy 静态托管
- 数据生成：服务器上用 `cron/systemd timer` 每天跑一次 `rss-daily-report`。
- Web 托管：
  - 部署 `web` 的构建产物（`dist/`）到如 `/var/www/rss/`
  - 配置静态路由把 `/api/news/` 映射到 `NewsReport/data/`
- 访问方式：`http://<服务器IP>/`（无域名可用）。

优点
- 不需要域名、不依赖第三方平台。
- “生成+托管”都在一台机器上，链路最短，排障最简单。
- 生成时需要的任何本地能力（比如未来你想加别的脚本）都能直接跑。

缺点
- 你要自己运维（Nginx、日志、磁盘、备份）。
- 没域名时 HTTPS 体验一般（可先接受 HTTP）。

适用
- 你优先要“稳定可控 + 生成链路不折腾”，并且可接受 IP 访问。

### A2. “更省 Node”版本：直接用 `site/` 旧站静态页
如果你不强依赖 `web/` 新前端，可以直接让 Nginx 托管 `site/`：
- `rss-daily-report` 已会更新 `site/assets/data.js`（`--build-site` 默认开）。

优点：几乎不需要 Node 构建流程  
缺点：UI 是旧站，功能与体验可能弱于 `web/`

---

## 2) 方案 B：服务器生成 → 推送 Git → Pages 平台托管（Git 驱动部署）

核心思路：
- 生成发生在你的腾讯云服务器（cron 跑）。
- 生成产物推送到一个“部署专用分支/仓库”（比如 `gh-pages` 分支或单独的 `news-data` 仓库）。
- Pages 平台监听 Git 推送，自动发布静态站点。

### B1. GitHub Pages
优点
- 稳定、成本低、无需自建 Web 服务。
- 提供 `*.github.io` 域名（不需要自购域名）。

风险/成本
- 生成产物入库会让仓库变大；建议用专用分支/专用仓库承载 `dist + data`。
- 如果你的抓取需要代理/特殊网络环境，GitHub Actions 可能不如自建服务器可控（但本方案是“服务器生成”，所以问题不大）。

### B2. Cloudflare Pages / Vercel / EdgeOne Pages
共同点
- 通常提供默认子域名（不强制自有域名），HTTPS 也更省心。
- Git 推送触发构建/发布，适合“站点本体”托管。

差异（你需要重点关注“链接是否会过期”）
- 一般都有“项目域名（固定）”用于长期访问；不要依赖“预览链接（preview）”作为长期入口。
- EdgeOne Pages 的预览链接可能存在有效期/保留策略，因此长期应使用其项目域名或绑定自定义域名（有域名再说）。

优点
- 你不用自己维护 Nginx。
- 无域名也能拿到可长期访问的默认域名（取决于平台的“项目域名”策略）。

缺点
- 需要额外设计“如何把 /api/news/* 映射到静态文件路径”（后续会涉及一次前端 base/路由适配）。

---

## 3) 方案 C：对象存储（COS）+ CDN（可选 EdgeOne/Cloudflare）托管静态站

核心思路：
- 服务器定时生成：
  - `web` 构建产物（或旧站 `site/`）
  - `NewsReport/data/*.json`
- 把文件同步/上传到 COS（可选再挂 CDN 加速）。

优点
- 访问稳定、扩展性好、无需长期运行 Web Server。
- 无域名也能通过存储桶的默认访问地址（通常可用 HTTPS）。

缺点
- 上传/同步需要额外配置（凭证、路径、缓存策略）。
- 若要做“干净的 URL / SPA 路由回退”，需要配置静态站点规则（后续我们再做）。

---

## 4) 方案 D：前后端一体（小 API 服务 + 静态前端）

核心思路：
- 腾讯云服务器跑一个轻量服务（例如 Nginx + 小 API 或直接静态）。
- `/api/news/*` 由服务端直接读取 `NewsReport/data` 返回（路径天然对齐）。

优点
- 和当前 `web` 的 `/api/news/*` 约定天然一致。
- 最好排障、最少平台差异。

缺点
- 比“纯静态托管”更像传统运维模式。

---

## 5) 决策表（快速选型）

| 方案 | 无域名可用 | HTTPS 省心 | 运维成本 | 更新链路 | 最适合你现在 |
|---|---|---:|---:|---|---:|
| A1 服务器直托管（web+nginx） | 是（IP） | 一般 | 中 | cron → 本机落盘 | ✅✅✅ |
| A2 服务器托管旧站 site/ | 是（IP） | 一般 | 低 | cron → 本机落盘 | ✅✅ |
| B 服务器生成 + Pages 托管 | 是（平台子域名） | 好 | 低-中 | cron → git push → 自动部署 | ✅✅ |
| C COS + CDN | 是（默认域名） | 好 | 中 | cron → 上传同步 → 生效 | ✅ |
| D 小服务 + 静态 | 是（IP） | 一般 | 中 | cron → 本机落盘 | ✅✅ |

我的建议（你先 review 颗粒度）：
1) **短期最稳：A1 或 D**（腾讯云服务器直接跑生成 + 直接对外提供 Web）
2) **想少运维：B**（服务器只负责生成，站点托管交给 Pages）
3) **想走“静态+CDN”：C**（后期更像产品化）

---

## 6) 需要你确认的关键问题（决定我们后续改动颗粒度）

1) 你希望站点是否对公网开放？还是只给自己/小范围（IP 白名单/Basic Auth）？
2) 你能接受用 IP 访问（HTTP）作为第一阶段吗？还是必须 HTTPS？
3) 展示站点要用 `web/` 新前端还是 `site/` 旧站也可接受？
4) 数据更新频率：每天一次即可？还是希望“随时手动触发”？
5) 生成任务是否需要代理（`my/config.json` 的 proxy）？这会影响你更适合“服务器生成”还是“平台 actions 生成”。

---

## 7) EdgeOne 静态部署要点（避免 `/api/news/index.json` 404）

推荐流程（最少平台配置）：

1) 先生成数据：`python3 .codex/skills/rss-daily-report/scripts/run.py --no-ai`
2) 再构建前端（构建时会把 `NewsReport/data/*.json` 打包到 `dist/api/news/`）：`cd web && npm run build-only`（或 `pnpm build-only`）
3) EdgeOne 发布目录选择：`web/dist`

如果 EdgeOne 走“Git 构建”，务必保证构建前已经生成 `NewsReport/data/index.json`（否则构建仍会成功，但站点会缺数据）。
