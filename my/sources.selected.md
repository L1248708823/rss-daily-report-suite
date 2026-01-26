# 精选源列表（手动维护）
#
# 目的：
# - 避免 RSS源.md 里“同名多端点”带来的大量失效/低质量链接
# - 仍保留必要的冗余：同平台多个 URL 全部请求 -> 去重 -> 再按数量裁剪
#
# 格式（每行一个源）：
#   名字<TAB>URL
# 可选扩展：
#   名字|80|limit=15|fallback=https://mirror.example.com/feed<TAB>URL

## 社区 / 讨论
V2EX	https://v2ex.com/index.xml
V2EX	http://www.v2ex.com/index.xml
V2EX - 技术	https://www.v2ex.com/feed/tab/tech.xml

## 中文内容 / 观点
知乎日报	https://plink.anyfeeder.com/zhihu/daily
# 以下两条经常不稳定，但留作冗余；如影响整体成功率可删除
知乎每日精选	https://www.zhihu.com/rss
知乎热榜	https://plink.anyfeeder.com/zhihu/hotlist

阮一峰的网络日志	https://www.ruanyifeng.com/blog/atom.xml
caoz的梦呓	https://plink.anyfeeder.com/weixin/caozsay
虹膜	https://plink.anyfeeder.com/weixin/IrisMagazine

## 市场 / 财经
# 该 URL 有时会返回非 XML（可能被拦/跳转），建议后续补一个替补国际财经源
路透中文	https://plink.anyfeeder.com/reuters/cn

经济学人	https://plink.anyfeeder.com/weixin/theeconomist

雪球	https://xueqiu.com/hots/topic/rss
雪球	https://plink.anyfeeder.com/weixin/xueqiujinghua
# 该 URL 偶尔返回 HTML，先注释，确认稳定后再开启
# 今日话题 - 雪球	https://plink.anyfeeder.com/xueqiu/hot

## 工程 / 开源
HelloGitHub 月刊	http://hellogithub.com/rss
美团技术团队	https://tech.meituan.com/feed/
有赞技术团队	https://tech.youzan.com/rss/

