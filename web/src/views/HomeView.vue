<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { fetchNewsDay, fetchNewsIndex } from '@/lib/newsApi'
import type { NewsDayData, NewsDayIndex, NewsItem } from '@/lib/types'

const index = ref<NewsDayIndex | null>(null)
const day = ref<NewsDayData | null>(null)

const selectedDate = ref<string>('')
const query = ref<string>('')
const loading = ref(false)
const error = ref<string | null>(null)

const days = computed(() => index.value?.days ?? [])
const filteredItems = computed<NewsItem[]>(() => {
  const items = day.value?.items ?? []
  const q = query.value.trim().toLowerCase()
  if (!q) return items
  return items.filter((it) => {
    const title = (it.title_zh || it.title || '').toLowerCase()
    const summary = (it.summary || '').toLowerCase()
    const platform = (it.platform || '').toLowerCase()
    const category = (it.category || '').toLowerCase()
    return [title, summary, platform, category].some((x) => x.includes(q))
  })
})

const marketCards = computed(() => {
  const m = day.value?.meta?.market
  const indicators = m?.indicators ?? []
  const sse = indicators.find((x) => x.id === 'sh000001')
  const goldCny = indicators.find((x) => x.id === 'gds_AU9999')
  return {
    fetchedAt: m?.fetched_at || null,
    note: m?.note || null,
    sse,
    goldCny,
    errors: m?.errors ?? [],
  }
})

function displayTitle(item: NewsItem): string {
  return item.title_zh?.trim() || item.title
}

async function loadIndex() {
  loading.value = true
  error.value = null
  try {
    index.value = await fetchNewsIndex()
    selectedDate.value = index.value.days?.[0]?.date ?? ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function loadDay(date: string) {
  if (!date) return
  loading.value = true
  error.value = null
  try {
    day.value = await fetchNewsDay(date)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(loadIndex)
watch(selectedDate, (d) => void loadDay(d), { immediate: false })
</script>

<template>
  <main class="page">
    <header class="top">
      <div class="brand">
        <div class="title">耳朵日报（MVP）</div>
        <div class="sub">本地读取 `NewsReport/data`（dev 模式）</div>
      </div>

      <div class="controls">
        <label class="field">
          <span class="label">日期</span>
          <select v-model="selectedDate" class="input" :disabled="!days.length">
            <option v-for="d in days" :key="d.date" :value="d.date">
              {{ d.date }}{{ typeof d.count === 'number' ? `（${d.count}）` : '' }}
            </option>
          </select>
        </label>

        <label class="field grow">
          <span class="label">搜索</span>
          <input v-model="query" class="input" placeholder="标题 / 摘要 / 平台 / 分类…" />
        </label>
      </div>
    </header>

    <section v-if="error" class="notice error">
      <div class="strong">加载失败</div>
      <div class="mono">{{ error }}</div>
    </section>

    <section v-else class="meta">
      <div class="pill" v-if="loading">载入中…</div>
      <div class="pill" v-else>
        {{ selectedDate || '未选择日期' }} · {{ filteredItems.length }} 条
      </div>
    </section>

    <section class="market" v-if="marketCards.sse || marketCards.goldCny || marketCards.errors.length">
      <div class="marketTop">
        <div class="marketTitle">市场快照</div>
        <div class="marketSub" v-if="marketCards.fetchedAt">fetched_at: {{ marketCards.fetchedAt }}</div>
      </div>

      <div v-if="marketCards.errors.length" class="marketErr">
        <div class="muted">行情抓取有错误（不影响日报生成）：</div>
        <ul>
          <li v-for="(e, idx) in marketCards.errors" :key="idx" class="mono">{{ e }}</li>
        </ul>
      </div>

      <div class="marketGrid">
        <div v-if="marketCards.sse" class="mcard">
          <div class="mname">{{ marketCards.sse.name || '上证指数' }}</div>
          <div class="mvalue">
            {{ typeof marketCards.sse.value === 'number' ? marketCards.sse.value.toFixed(2) : '—' }}
            <span class="munit">点</span>
          </div>
          <div class="mmeta">
            <span v-if="typeof marketCards.sse.change_pct === 'number'" class="tag">
              {{ marketCards.sse.change_pct >= 0 ? '+' : '' }}{{ marketCards.sse.change_pct.toFixed(2) }}%
            </span>
            <span v-if="marketCards.sse.provider" class="muted">provider: {{ marketCards.sse.provider }}</span>
          </div>
        </div>

        <div v-if="marketCards.goldCny" class="mcard">
          <div class="mname">{{ marketCards.goldCny.name || '现货黄金' }}</div>
          <div class="mvalue">
            {{ typeof marketCards.goldCny.value === 'number' ? marketCards.goldCny.value.toFixed(2) : '—' }}
            <span class="munit">元/克</span>
          </div>
          <div class="mmeta">
            <span v-if="typeof marketCards.goldCny.change_pct === 'number'" class="tag">
              {{ marketCards.goldCny.change_pct >= 0 ? '+' : '' }}{{ marketCards.goldCny.change_pct.toFixed(2) }}%
            </span>
            <span v-if="marketCards.goldCny.as_of" class="muted">as_of: {{ marketCards.goldCny.as_of }}</span>
          </div>
        </div>
      </div>

      <div v-if="marketCards.note" class="marketNote">{{ marketCards.note }}</div>
    </section>

    <section class="list" v-if="filteredItems.length">
      <article v-for="it in filteredItems" :key="it.url" class="card">
        <div class="line">
          <a class="link" :href="it.url" target="_blank" rel="noreferrer">
            {{ displayTitle(it) }}
          </a>
        </div>
        <div class="meta2">
          <span v-if="it.platform" class="tag">{{ it.platform }}</span>
          <span v-if="it.category" class="tag muted">{{ it.category }}</span>
          <span v-if="typeof it.quality_score === 'number'" class="muted">score {{ it.quality_score.toFixed(2) }}</span>
          <span v-if="it.published" class="muted">{{ it.published }}</span>
        </div>
        <p v-if="it.summary" class="summary">{{ it.summary }}</p>
        <details v-if="it.key_points?.length" class="details">
          <summary>要点</summary>
          <ul>
            <li v-for="(p, idx) in it.key_points" :key="idx">{{ p }}</li>
          </ul>
        </details>
        <div v-if="it.title_zh && it.title_zh.trim() !== it.title.trim()" class="origin">
          原标题：{{ it.title }}
        </div>
      </article>
    </section>

    <section v-else class="empty">
      <div class="emptyTitle">没有匹配条目</div>
      <div class="emptySub">试试换个日期或清空搜索。</div>
    </section>
  </main>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}

.top {
  display: grid;
  gap: 12px;
}

.brand .title {
  font-size: 18px;
  font-weight: 600;
}

.brand .sub {
  font-size: 12px;
  opacity: 0.7;
}

.controls {
  display: grid;
  gap: 12px;
  grid-template-columns: 200px 1fr;
}

.field {
  display: grid;
  gap: 6px;
}

.field.grow {
  min-width: 0;
}

.label {
  font-size: 12px;
  opacity: 0.7;
}

.input {
  height: 36px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: var(--color-background-soft);
  color: inherit;
}

.meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.pill {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-background-soft);
  font-size: 12px;
}

.notice {
  border-radius: 12px;
  border: 1px solid var(--color-border);
  padding: 12px;
  background: var(--color-background-soft);
}

.notice.error {
  border-color: rgba(255, 0, 0, 0.35);
}

.strong {
  font-weight: 600;
  margin-bottom: 4px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  opacity: 0.8;
  overflow-wrap: anywhere;
}

.list {
  display: grid;
  gap: 12px;
}

.card {
  border-radius: 14px;
  border: 1px solid var(--color-border);
  background: var(--color-background-soft);
  padding: 12px 12px 10px;
}

.link {
  color: inherit;
  text-decoration: none;
  padding: 0;
}

.link:hover {
  text-decoration: underline;
  background: transparent;
}

.meta2 {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 6px;
  font-size: 12px;
}

.tag {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-background);
  font-size: 12px;
}

.muted {
  opacity: 0.7;
}

.summary {
  margin-top: 8px;
  font-size: 13px;
  opacity: 0.9;
}

.details {
  margin-top: 10px;
}

.details summary {
  cursor: pointer;
  font-size: 12px;
  opacity: 0.8;
}

.details ul {
  margin: 8px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  font-size: 13px;
}

.origin {
  margin-top: 10px;
  font-size: 12px;
  opacity: 0.7;
}

.empty {
  border-radius: 14px;
  border: 1px dashed var(--color-border);
  padding: 16px;
  background: var(--color-background-mute);
}

.emptyTitle {
  font-weight: 600;
}

.emptySub {
  margin-top: 4px;
  font-size: 12px;
  opacity: 0.7;
}

.market {
  border-radius: 14px;
  border: 1px solid var(--color-border);
  background: var(--color-background-soft);
  padding: 12px;
}

.marketTop {
  display: flex;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.marketTitle {
  font-weight: 600;
}

.marketSub {
  font-size: 12px;
  opacity: 0.7;
  overflow-wrap: anywhere;
  text-align: right;
}

.marketErr {
  margin-bottom: 10px;
}

.marketErr ul {
  margin: 6px 0 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
}

.marketGrid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.mcard {
  border-radius: 12px;
  border: 1px solid var(--color-border);
  background: var(--color-background);
  padding: 10px;
}

.mname {
  font-size: 12px;
  opacity: 0.75;
}

.mvalue {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 700;
}

.munit {
  font-size: 12px;
  font-weight: 500;
  opacity: 0.6;
  margin-left: 6px;
}

.mmeta {
  margin-top: 6px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 12px;
}

.marketNote {
  margin-top: 10px;
  font-size: 12px;
  opacity: 0.7;
}

@media (max-width: 720px) {
  .controls {
    grid-template-columns: 1fr;
  }

  .marketGrid {
    grid-template-columns: 1fr;
  }
}
</style>
