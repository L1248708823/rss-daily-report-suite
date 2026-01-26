# 本地开发（MVP）

## 1) 选源：只改一个文件
- 勾选/取消勾选：`my/sources.checklist.md`
- 同步生成启用列表（会写 `my/sources.md`）：  
  `python3 .codex/skills/rss-daily-report/scripts/sync_sources.py`

## 2) 生成日报数据（会写入 NewsReport/data）
```bash
python3 .codex/skills/rss-daily-report/scripts/run.py
# 或指定日期
python3 .codex/skills/rss-daily-report/scripts/run.py 2026-01-26
```

## 3) 启动 Vue3 前端
```powershell
cd web
pnpm dev
```
浏览器打开：`http://localhost:5173`

## 4) 常见问题
- V2EX 你浏览器能开但脚本超时：通常是 WSL 网络/代理不同步；把代理填到 `my/config.json` 的 `defaults.proxy`。
- 今日条目很少：先看日报里的“抓取明细/失败原因”，再看是否被 `min_score`/平台限额过滤。

