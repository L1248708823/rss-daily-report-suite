# TODO（滚动迭代清单）

> 说明：以 MVP 本地可用为第一目标；每次新增需求先补到 `PRD.md`，再拆到这里。

## P0 · MVP（本地开发）
- [x] 输出 WSL 安装与创建 Vue3 的操作文档（`DEV_SETUP_WSL_VUE3.md`）
- [x] 输出 Windows 安装与创建 Vue3 的操作文档（`DEV_SETUP_WINDOWS_VUE3.md`）
- [x] 输出 MVP 联调流程文档（`DEV_MVP_WORKFLOW.md`）
- [x] 新建 Vue3（Vite）前端项目目录（`web/`）
- [x] 打通数据读取：Vite dev 下通过 `/api/news/*.json` 读取 `NewsReport/data`
- [x] 首页 MVP：日期选择 + 搜索 + 条目列表渲染（先不做重设计）
- [x] 生成市场指标数据：上证指数 + 黄金写入 `NewsReport/data/*`（meta.market）
- [ ] 前端展示市场指标卡：上证指数 + 黄金（先简单展示，后续再做视觉设计）
- [ ] 本地开发脚本：一键生成今日数据 + 启动前端（可先用两个命令）

## P1 · 自动化（先不做部署，先把流水线跑通）
- [ ] 增加“每日 09:00（Asia/Shanghai）运行”的 CI 方案草案（GitHub Actions/其他）
- [ ] 失败可观测：输出失败源、状态码、content-type 与响应前 200 字节（便于定位）

## P2 · 源多样性与质量治理
- [ ] 增加“栏目配比/上限”配置项（技术/经济/产品/其他）
- [ ] 重复治理：跨源转载/同题不同链接的近似去重（规则可配置）
- [ ] 源健康度：连续失败的源临时熔断（带冷却时间）

## P3 · Vue3 站点体验（等你确认设计方向后再做）
- [ ] 视觉与交互重设计（使用 `$frontend-design`，先出方向再开工）
- [ ] 收藏/稍后读、热词/趋势、分享/复制 Markdown
- [ ] 源管理可视化：从 `RSS源.md` 勾选生成 `my/sources.selected.md`
