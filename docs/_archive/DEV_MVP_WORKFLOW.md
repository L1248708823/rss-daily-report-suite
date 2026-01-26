# MVP 本地联调流程（日报数据 + Vue3 前端）

目标：本地看到「日期选择 + 搜索 + 列表」能正常加载 `NewsReport/data` 的日报条目。

## 方式 A（推荐）：WSL 生成数据 + Windows 跑前端
1) 在 WSL 终端（仓库根目录）生成今天数据（示例日期可替换）
```bash
python3 .codex/skills/rss-daily-report/scripts/run.py 2026-01-26
```

2) 在 Windows PowerShell（仓库根目录）启动前端
```powershell
cd web
pnpm dev
```

3) 浏览器打开
- `http://localhost:5173`

> 说明：前端 dev 模式下通过 Vite 中间件读取仓库根目录的 `NewsReport/data`，对应接口：
> - `/api/news/index.json`
> - `/api/news/YYYY-MM-DD.json`

## 方式 B：全在 Windows（你习惯 Windows Python 的话）
1) Windows PowerShell 生成今天数据
```powershell
python .codex/skills/rss-daily-report/scripts/run.py 2026-01-26
```

2) 启动前端
```powershell
cd web
pnpm dev
```

## 排查清单（出现空白/报错时）
- 先确认 `NewsReport/data/index.json` 存在且有 `days`：`type NewsReport\\data\\index.json`
- 前端页面提示 `index.json not found`：说明你还没跑过生成脚本或目录不在仓库根。
- 页面提示 `day json not found`：说明所选日期文件不存在，先生成对应日期。
- 生成脚本跑完但列表仍为空：打开浏览器控制台，看是否 `/api/news/*.json` 404/500（把错误截图/日志贴我）。

