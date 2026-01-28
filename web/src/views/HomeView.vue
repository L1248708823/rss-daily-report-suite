<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Menu, MenuButton, MenuItem, MenuItems } from '@headlessui/vue'
import { Check, ChevronDown, ChevronLeft, ChevronRight, Search, X } from 'lucide-vue-next'
import { fetchNewsDay, fetchNewsIndex } from '@/lib/newsApi'
import type { NewsDayData, NewsDayIndex, NewsItem } from '@/lib/types'

const index = ref<NewsDayIndex | null>(null)
const day = ref<NewsDayData | null>(null)

const selectedDate = ref<string>('')
const query = ref<string>('')
const activeCategory = ref<string>('')
const activePlatform = ref<string>('')
const showSummaries = ref(true) // 你已确认：摘要/导读默认展示
const searchOpen = ref(false)
const searchInputEl = ref<HTMLInputElement | null>(null)

const loading = ref(false)
const error = ref<string | null>(null)

const days = computed(() => index.value?.days ?? [])
const dayPosition = computed(() => days.value.findIndex((d) => d.date === selectedDate.value))
const olderDate = computed(() => (dayPosition.value >= 0 ? days.value[dayPosition.value + 1]?.date ?? '' : ''))
const newerDate = computed(() => (dayPosition.value > 0 ? days.value[dayPosition.value - 1]?.date ?? '' : ''))

const items = computed<NewsItem[]>(() => day.value?.items ?? [])
const backfillItems = computed<NewsItem[]>(() => day.value?.backfill_items ?? [])

function displayTitle(item: NewsItem): string {
  return item.title_zh?.trim() || item.title
}

function formatPublished(published?: string | null): string {
  if (!published) return ''
  // published 可能是 ISO / RFC2822 / 自定义格式；尽量避免原样展示 ISO（含 T/+00:00）
  const parsed = formatTs(published, { seconds: true })
  if (parsed && parsed !== published) return parsed
  // 兜底：如果包含 ISO 痕迹，做一次最小清洗
  const cleaned = published.replace('T', ' ').replace(/\+\d{2}:\d{2}$/, '').trim()
  return cleaned.length > 19 ? cleaned.slice(0, 19) : cleaned
}

function formatTs(ts?: string | null, opts?: { seconds?: boolean }): string {
  if (!ts) return ''
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  const pad = (n: number) => String(n).padStart(2, '0')
  const y = d.getFullYear()
  const m = pad(d.getMonth() + 1)
  const dd = pad(d.getDate())
  const hh = pad(d.getHours())
  const mm = pad(d.getMinutes())
  const ss = pad(d.getSeconds())
  return opts?.seconds ? `${y}-${m}-${dd} ${hh}:${mm}:${ss}` : `${y}-${m}-${dd} ${hh}:${mm}`
}

function includesQuery(item: NewsItem, q: string): boolean {
  const title = (item.title_zh || item.title || '').toLowerCase()
  const summary = (item.summary || '').toLowerCase()
  const platform = (item.platform || '').toLowerCase()
  const category = (item.category || '').toLowerCase()
  return [title, summary, platform, category].some((x) => x.includes(q))
}

function applyFilters(list: NewsItem[]): NewsItem[] {
  let out = list
  if (activeCategory.value) out = out.filter((x) => (x.category || '') === activeCategory.value)
  if (activePlatform.value) out = out.filter((x) => (x.platform || '') === activePlatform.value)
  const q = query.value.trim().toLowerCase()
  if (q) out = out.filter((x) => includesQuery(x, q))
  return out
}

const filteredItems = computed(() => applyFilters(items.value))
const filteredBackfillItems = computed(() => applyFilters(backfillItems.value))

const featured = computed<NewsItem | null>(() => {
  const list = filteredItems.value
  if (!list.length) return null
  const withScore = [...list].sort((a, b) => (b.quality_score ?? -1) - (a.quality_score ?? -1))
  return withScore[0] ?? null
})

const pinnedLead = computed(() => filteredItems.value.find((x) => x.pin === 'lead') ?? null)
const pinnedTop = computed(() => filteredItems.value.filter((x) => x.pin === 'top').slice(0, 5))

const lead = computed(() => pinnedLead.value ?? featured.value)

const topStories = computed(() => {
  if (pinnedTop.value.length) return pinnedTop.value
  const leadUrl = lead.value?.url
  const byScore = [...filteredItems.value].sort((a, b) => (b.quality_score ?? -1) - (a.quality_score ?? -1))
  return byScore.filter((x) => x.url !== leadUrl).slice(0, 5)
})

const allStories = computed(() => {
  const exclude = new Set<string>()
  if (lead.value) exclude.add(lead.value.url)
  for (const it of topStories.value) exclude.add(it.url)
  return filteredItems.value.filter((x) => !exclude.has(x.url))
})

const categoryStats = computed(() => {
  const map = new Map<string, number>()
  for (const it of items.value) {
    const key = (it.category || '').trim()
    if (!key) continue
    map.set(key, (map.get(key) ?? 0) + 1)
  }
  return [...map.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 18)
})

const platformStats = computed(() => {
  const map = new Map<string, number>()
  for (const it of items.value) {
    const key = (it.platform || '').trim()
    if (!key) continue
    map.set(key, (map.get(key) ?? 0) + 1)
  }
  return [...map.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 16)
})

const categoryOptions = computed(() => [{ name: '全部', value: '', count: items.value.length }, ...categoryStats.value.map((x) => ({ ...x, value: x.name }))])
const platformOptions = computed(() => [{ name: '全部', value: '', count: items.value.length }, ...platformStats.value.map((x) => ({ ...x, value: x.name }))])

const navCategoriesPrimary = computed(() => categoryOptions.value.slice(0, 9))
const navCategoriesMore = computed(() => categoryOptions.value.slice(9))

const issueHumanDate = computed(() => {
  if (!selectedDate.value) return ''
  const d = new Date(`${selectedDate.value}T00:00:00`)
  if (Number.isNaN(d.getTime())) return selectedDate.value
  const weekday = d.toLocaleDateString('en-US', { weekday: 'long' })
  const monthDayYear = d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  return `${weekday} · ${monthDayYear}`
})

const market = computed(() => {
  const m = day.value?.meta?.market
  const indicators = m?.indicators ?? []
  const sse = indicators.find((x) => x.id === 'sh000001')
  const goldCny = indicators.find((x) => x.id === 'gds_AU9999')
  return {
    fetchedAt: m?.fetched_at || null,
    note: m?.note || null,
    errors: m?.errors ?? [],
    sse,
    goldCny,
  }
})

function pickChangeClass(changePct?: number | null): string {
  if (typeof changePct !== 'number') return 'text-[color:var(--muted)]'
  if (changePct > 0) return 'text-emerald-700'
  if (changePct < 0) return 'text-rose-700'
  return 'text-[color:var(--muted)]'
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

function goOlder() {
  if (!olderDate.value) return
  selectedDate.value = olderDate.value
}

function goNewer() {
  if (!newerDate.value) return
  selectedDate.value = newerDate.value
}

function clearFilters() {
  activeCategory.value = ''
  activePlatform.value = ''
}

function openSearch() {
  searchOpen.value = true
  queueMicrotask(() => searchInputEl.value?.focus())
}

function closeSearchIfEmpty() {
  if (!query.value.trim()) searchOpen.value = false
}

function closeSearch() {
  query.value = ''
  searchOpen.value = false
}

function onSearchKeydown(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  closeSearch()
}

function onGlobalKeydown(e: KeyboardEvent) {
  if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return
  const t = e.target as HTMLElement | null
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.getAttribute('contenteditable') === 'true')) return
  e.preventDefault()
  openSearch()
}

onMounted(loadIndex)
onMounted(() => window.addEventListener('keydown', onGlobalKeydown))
onUnmounted(() => window.removeEventListener('keydown', onGlobalKeydown))
watch(selectedDate, (d) => void loadDay(d), { immediate: false })
</script>

<template>
  <main class="mx-auto max-w-6xl px-4 pb-20 pt-10">
    <header class="relative">
      <!-- 顶部信息条（像报纸的头版横条） -->
      <div class="border-b border-[var(--rule)] pb-3">
        <div class="grid gap-2 text-xs text-[color:var(--muted)] sm:grid-cols-3 sm:items-center">
          <div class="flex items-center gap-3">
            <span class="uppercase tracking-[0.22em]">edition</span>
            <span class="tabular-nums text-[color:var(--ink)]">{{ selectedDate || '—' }}</span>
            <span class="opacity-50">·</span>
            <span v-if="loading">loading</span>
            <span v-else class="tabular-nums">{{ filteredItems.length }} stories</span>
          </div>
          <div class="text-left text-[11px] uppercase tracking-[0.28em] text-[color:var(--muted)] sm:text-center">
            {{ issueHumanDate || '—' }}
          </div>
          <div class="flex items-center gap-3 sm:justify-end">
            <span class="uppercase tracking-[0.22em]">issue</span>
            <span class="tabular-nums text-[color:var(--ink)]">{{ selectedDate || '—' }}</span>
            <span class="opacity-50">·</span>
            <span v-if="market.fetchedAt" class="tabular-nums">market {{ formatTs(market.fetchedAt, { seconds: true }) }}</span>
            <span v-else>market —</span>
          </div>
        </div>
      </div>

      <!-- masthead：更像报纸 -->
      <div class="mt-4 border-y border-[var(--rule-strong)] py-6 [border-top-width:2px]">
        <div class="grid items-center gap-4 sm:grid-cols-3">
          <div class="hidden sm:flex items-center justify-start">
            <div class="flex items-center gap-3">
              <div class="grid h-12 w-12 place-items-center rounded-full border border-[var(--rule-strong)] bg-white/70 text-[12px] font-semibold tracking-[0.18em] text-[color:var(--ink)]">
                NMQ
              </div>
              <div class="text-xs text-[color:var(--muted)]">
                <div class="uppercase tracking-[0.26em]">niu ma</div>
                <div class="tabular-nums">est. 2026</div>
              </div>
            </div>
          </div>

          <div class="text-center">
            <div class="text-[11px] uppercase tracking-[0.36em] text-[color:var(--muted)]">draft edition</div>
            <h1 class="mt-2 text-6xl font-semibold leading-none tracking-tight text-[color:var(--ink)] [font-family:var(--font-serif)]">
              牛马快讯
            </h1>
            <div class="mt-2 text-xs text-[color:var(--muted)]">
              <span class="uppercase tracking-[0.22em]">rss digest</span>
              <span class="mx-2 opacity-50">·</span>
              <span class="uppercase tracking-[0.22em]">local edition</span>
              <span class="mx-2 opacity-50">·</span>
              <span v-if="day?.generated_at" class="tabular-nums">generated {{ formatTs(day.generated_at, { seconds: true }) }}</span>
            </div>
          </div>

          <div class="hidden sm:flex items-center justify-end">
            <div class="text-right text-xs text-[color:var(--muted)]">
              <div class="uppercase tracking-[0.26em]">paper</div>
              <div class="tabular-nums text-[color:var(--ink)]">$0.00</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 报纸式栏目导航（替代“平平无奇”的下拉筛选） -->
      <nav class="mt-3 border-b border-[var(--rule)] pb-3">
        <div class="flex items-center gap-0 overflow-x-auto rounded-2xl border border-[var(--rule)] bg-white/55 px-2 py-1 no-scrollbar">
          <button
            v-for="c in navCategoriesPrimary"
            :key="c.name"
            class="shrink-0 border-r border-[var(--rule)] px-3 py-2 text-[11px] uppercase tracking-[0.26em] transition last:border-r-0"
            :class="activeCategory === c.value ? 'bg-[color:rgba(17,17,17,0.06)] text-[color:var(--ink)]' : 'text-[color:var(--muted)] hover:text-[color:var(--ink)]'"
            @click="activeCategory = c.value"
          >
            {{ c.name }}
          </button>

          <Menu v-if="navCategoriesMore.length" as="div" class="relative shrink-0">
            <MenuButton class="inline-flex items-center gap-2 px-3 py-2 text-[11px] uppercase tracking-[0.26em] text-[color:var(--muted)] hover:text-[color:var(--ink)]">
              more <ChevronDown class="h-4 w-4" />
            </MenuButton>
            <MenuItems class="absolute left-0 z-20 mt-2 w-64 overflow-hidden rounded-2xl border border-[var(--rule)] bg-[var(--paper-2)] shadow-[var(--shadow-soft)] focus:outline-none">
              <div class="max-h-80 overflow-auto p-1">
                <MenuItem v-for="c in navCategoriesMore" :key="c.name" v-slot="{ active }">
                  <button
                    class="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm"
                    :class="active ? 'bg-[color:rgba(17,17,17,0.06)]' : ''"
                    @click="activeCategory = c.value"
                  >
                    <span class="w-5">
                      <Check v-if="activeCategory === c.value" class="h-4 w-4 text-[color:var(--accent)]" />
                    </span>
                    <span class="min-w-0 flex-1 truncate text-[color:var(--ink)]">{{ c.name }}</span>
                    <span class="text-xs text-[color:var(--muted)] tabular-nums">{{ c.count }}</span>
                  </button>
                </MenuItem>
              </div>
            </MenuItems>
          </Menu>

          <div class="ml-auto flex items-center gap-2 pl-2">
            <Menu as="div" class="relative shrink-0">
              <MenuButton class="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-[11px] uppercase tracking-[0.26em] text-[color:var(--muted)] hover:text-[color:var(--ink)]">
                sources <ChevronDown class="h-4 w-4" />
              </MenuButton>
              <MenuItems class="absolute right-0 z-20 mt-2 w-72 overflow-hidden rounded-2xl border border-[var(--rule)] bg-[var(--paper-2)] shadow-[var(--shadow-soft)] focus:outline-none">
                <div class="border-b border-[var(--rule)] px-4 py-3 text-xs text-[color:var(--muted)]">选择来源平台</div>
                <div class="max-h-80 overflow-auto p-1">
                  <MenuItem v-for="p in platformOptions" :key="p.name" v-slot="{ active }">
                    <button
                      class="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm"
                      :class="active ? 'bg-[color:rgba(17,17,17,0.06)]' : ''"
                      @click="activePlatform = p.value"
                    >
                      <span class="w-5">
                        <Check v-if="activePlatform === p.value" class="h-4 w-4 text-[color:var(--accent)]" />
                      </span>
                      <span class="min-w-0 flex-1 truncate text-[color:var(--ink)]">{{ p.name }}</span>
                      <span class="text-xs text-[color:var(--muted)] tabular-nums">{{ p.count }}</span>
                    </button>
                  </MenuItem>
                </div>
              </MenuItems>
            </Menu>

            <button
              class="rounded-xl border border-transparent px-3 py-2 text-[11px] uppercase tracking-[0.26em] text-[color:var(--muted)] transition hover:border-[var(--rule)] hover:bg-white/50 hover:text-[color:var(--ink)]"
              @click="clearFilters"
            >
              reset
            </button>
          </div>
        </div>
      </nav>

      <!-- 交互条（尽量克制） -->
      <div class="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex flex-wrap items-center gap-2">
          <button
            class="inline-flex items-center gap-2 rounded-2xl border border-[var(--rule)] bg-white/55 px-3 py-2 text-sm text-[color:var(--ink)] transition hover:border-[var(--rule-strong)] hover:bg-white/70 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-40 disabled:active:translate-y-0"
            :disabled="!olderDate"
            @click="goOlder"
          >
            <ChevronLeft class="h-4 w-4" />
            前一天
          </button>

          <label
            class="inline-flex items-center gap-2 rounded-2xl border border-[var(--rule)] bg-white/55 px-3 py-2 text-sm transition hover:border-[var(--rule-strong)] hover:bg-white/70"
          >
            <span class="text-[color:var(--muted)]">日期</span>
            <select
              v-model="selectedDate"
              class="h-8 rounded-md border-0 bg-transparent pr-7 text-sm text-[color:var(--ink)] focus:ring-0"
              :disabled="!days.length"
            >
              <option v-for="d in days" :key="d.date" :value="d.date">
                {{ d.date }}{{ typeof d.count === 'number' ? `（${d.count}）` : '' }}
              </option>
            </select>
          </label>

          <button
            class="inline-flex items-center gap-2 rounded-2xl border border-[var(--rule)] bg-white/55 px-3 py-2 text-sm text-[color:var(--ink)] transition hover:border-[var(--rule-strong)] hover:bg-white/70 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-40 disabled:active:translate-y-0"
            :disabled="!newerDate"
            @click="goNewer"
          >
            后一天
            <ChevronRight class="h-4 w-4" />
          </button>
        </div>

        <div class="flex w-full items-center justify-end lg:w-auto">
          <div
            class="flex items-center overflow-hidden rounded-2xl border border-[var(--rule)] bg-white/55 shadow-[0_1px_0_rgba(17,17,17,0.06)] transition-[width,border-color,background-color] duration-200 ease-out hover:border-[var(--rule-strong)] hover:bg-white/70 focus-within:border-[var(--rule-strong)]"
            :class="searchOpen ? 'w-full lg:w-[420px]' : 'w-11'"
          >
            <button
              type="button"
              class="grid h-11 w-11 place-items-center rounded-xl leading-none text-[color:var(--muted)] transition hover:bg-white/55 hover:text-[color:var(--ink)]"
              @click="searchOpen ? closeSearch() : openSearch()"
              :aria-label="searchOpen ? 'Close search' : 'Open search'"
            >
              <Search v-if="!searchOpen" class="block h-4 w-4 translate-y-[0.5px] ml-3" />
              <X v-else class="block h-4 w-4 translate-y-[0.5px]" />
            </button>
            <input
              v-model="query"
              ref="searchInputEl"
              class="h-11 w-full min-w-0 border-0 bg-transparent text-sm text-[color:var(--ink)] placeholder:text-[color:var(--muted)] transition-[width,opacity] duration-200 ease-out focus:ring-0"
              :class="searchOpen ? 'opacity-100 pr-4' : 'pointer-events-none w-0 opacity-0 pr-0'"
              placeholder="Search…"
              @blur="closeSearchIfEmpty"
              @keydown="onSearchKeydown"
            />
          </div>
        </div>
      </div>
    </header>

    <section v-if="error" class="mt-6 rounded-[var(--radius)] border border-rose-200 bg-[var(--paper-2)] p-4 shadow-[var(--shadow-soft)]">
      <div class="text-sm font-semibold text-[color:var(--ink)]">加载失败</div>
      <div class="mt-2 text-xs text-[color:var(--muted)] [font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace]">
        {{ error }}
      </div>
    </section>

    <section
      v-else
      :key="selectedDate"
      class="mt-10"
      v-motion
      :initial="{ opacity: 0, y: 10 }"
      :enter="{ opacity: 1, y: 0, transition: { type: 'spring', stiffness: 140, damping: 20 } }"
    >
      <!-- 头条 + Markets（左右不齐，像头版版面） -->
      <div class="grid gap-6 lg:grid-cols-12 lg:items-start">
        <div class="lg:col-span-8">
          <article
            v-if="lead"
            class="rounded-[var(--radius)] border border-[var(--rule)] bg-[var(--paper-2)] p-7 shadow-[var(--shadow-soft)] [border-left-width:3px] [border-left-color:var(--rule-strong)]"
            v-motion
            :initial="{ opacity: 0, y: 10 }"
            :enter="{ opacity: 1, y: 0, transition: { type: 'spring', stiffness: 140, damping: 20, delay: 40 } }"
          >
            <div class="flex flex-wrap items-center gap-2 text-xs text-[color:var(--muted)]">
              <span class="uppercase tracking-[0.22em] text-[color:var(--accent-ink)]">lead</span>
              <span v-if="lead.category" class="rounded-full border border-[var(--rule)] bg-white/60 px-2 py-0.5">
                {{ lead.category }}
              </span>
              <span v-if="lead.platform" class="rounded-full border border-[var(--rule)] bg-white/60 px-2 py-0.5">
                {{ lead.platform }}
              </span>
              <span v-if="lead.published" class="ml-auto tabular-nums">{{ formatPublished(lead.published) }}</span>
            </div>

            <a
              class="mt-4 block text-[40px] font-semibold leading-[1.08] tracking-tight text-[color:var(--ink)] [font-family:var(--font-serif)] transition-colors hover:text-[color:var(--accent-ink)]"
              :href="lead.url"
              target="_blank"
              rel="noreferrer"
            >
              {{ displayTitle(lead) }}
            </a>

            <p
              v-if="lead.summary && showSummaries"
              class="mt-4 text-[15px] leading-relaxed text-[color:var(--muted)] first-letter:float-left first-letter:mr-2 first-letter:mt-1 first-letter:text-5xl first-letter:leading-none first-letter:text-[color:var(--ink)] first-letter:[font-family:var(--font-serif)]"
            >
              {{ lead.summary }}
            </p>

            <div v-if="lead.key_points?.length" class="mt-5 grid gap-2">
              <div class="text-xs uppercase tracking-[0.22em] text-[color:var(--muted)]">highlights</div>
              <ul class="grid gap-2 text-sm text-[color:var(--ink)]">
                <li v-for="(p, idx) in lead.key_points.slice(0, 3)" :key="idx" class="flex gap-2">
                  <span class="mt-2 h-1.5 w-1.5 flex-none rounded-full bg-[color:rgba(17,17,17,0.45)]" />
                  <span class="min-w-0">{{ p }}</span>
                </li>
              </ul>
            </div>

            <div class="mt-5 flex flex-wrap items-center gap-3 text-xs text-[color:var(--muted)]">
              <span v-if="typeof lead.quality_score === 'number'" class="tabular-nums">q {{ lead.quality_score.toFixed(2) }}</span>
              <span v-if="lead.source" class="truncate">源 {{ lead.source }}</span>
            </div>
          </article>
        </div>

        <div class="lg:col-span-4">
          <section
            class="print-halftone rounded-[var(--radius)] border border-[color:rgba(7,94,57,0.28)] bg-[color:rgba(11,143,84,0.085)] p-6 shadow-[var(--shadow-soft)]"
            v-motion
            :initial="{ opacity: 0, y: 14 }"
            :enter="{ opacity: 1, y: 0, transition: { type: 'spring', stiffness: 140, damping: 20, delay: 110 } }"
          >
            <div class="flex items-end justify-between border-b border-[var(--rule)] pb-3">
              <div>
                <div class="inline-flex items-center rounded-lg border-2 border-[color:rgba(17,17,17,0.78)] bg-[color:rgba(255,255,255,0.55)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:rgba(17,17,17,0.86)] shadow-[2px_2px_0_rgba(17,17,17,0.18)]">
                  markets
                </div>
                <div class="mt-1 text-sm text-[color:var(--muted)]">上海综合指数 · 沪金99</div>
              </div>
              <div v-if="market.fetchedAt" class="text-xs text-[color:var(--muted)] tabular-nums">as of {{ formatTs(market.fetchedAt, { seconds: true }) }}</div>
            </div>

            <div class="mt-5 grid gap-3">
              <div class="rounded-[var(--radius)] border border-[var(--rule)] bg-white/60 p-4">
                <div class="text-[11px] uppercase tracking-[0.22em] text-[color:var(--muted)]">sse</div>
                <div class="mt-2 text-3xl font-semibold text-[color:var(--ink)] tabular-nums">
                  {{ market.sse && typeof market.sse.value === 'number' ? market.sse.value.toFixed(2) : '—' }}
                </div>
                <div class="mt-2 flex items-center justify-between gap-3 text-sm">
                  <span class="truncate text-[color:var(--muted)]">{{ market.sse?.name || '上证指数' }}</span>
                  <span class="tabular-nums" :class="pickChangeClass(market.sse?.change_pct)">{{
                    typeof market.sse?.change_pct === 'number' ? `${market.sse.change_pct >= 0 ? '+' : ''}${market.sse.change_pct.toFixed(2)}%` : '—'
                  }}</span>
                </div>
              </div>

              <div class="rounded-[var(--radius)] border border-[var(--rule)] bg-white/60 p-4">
                <div class="text-[11px] uppercase tracking-[0.22em] text-[color:var(--muted)]">gold</div>
                <div class="mt-2 text-3xl font-semibold text-[color:var(--ink)] tabular-nums">
                  {{ market.goldCny && typeof market.goldCny.value === 'number' ? market.goldCny.value.toFixed(2) : '—' }}
                  <span class="ml-2 text-sm font-medium text-[color:var(--muted)]">元/克</span>
                </div>
                <div class="mt-2 flex items-center justify-between gap-3 text-sm">
                  <span class="truncate text-[color:var(--muted)]">{{ market.goldCny?.name || '沪金99' }}</span>
                  <span class="tabular-nums" :class="pickChangeClass(market.goldCny?.change_pct)">{{
                    typeof market.goldCny?.change_pct === 'number' ? `${market.goldCny.change_pct >= 0 ? '+' : ''}${market.goldCny.change_pct.toFixed(2)}%` : '—'
                  }}</span>
                </div>
                <div v-if="market.goldCny?.as_of" class="mt-1 text-xs text-[color:var(--muted)] tabular-nums">as_of {{ formatTs(market.goldCny.as_of, { seconds: true }) }}</div>
              </div>
            </div>

            <div v-if="market.errors.length" class="mt-4 rounded-xl border border-rose-200 bg-rose-50/50 p-4 text-xs text-rose-900">
              <div class="font-semibold">行情抓取有错误（不影响日报）</div>
              <ul class="mt-2 grid gap-1 text-rose-900/80">
                <li v-for="(e, idx) in market.errors" :key="idx">{{ e }}</li>
              </ul>
            </div>
          </section>
        </div>
      </div>

      <!-- 精选（由 editor picks 回写 pin=top） -->
      <div class="mt-10">

          <section>
            <div class="flex items-end justify-between border-b border-[var(--rule)] pb-2">
              <div>
                <div class="text-xs uppercase tracking-[0.26em] text-[color:var(--muted)]">top stories</div>
              </div>
              <div class="text-xs text-[color:var(--muted)]">editor’s picks</div>
            </div>

            <div class="mt-5 grid gap-4">
              <a
                v-for="(it, i) in topStories"
                :key="it.url"
                class="group rounded-[var(--radius)] border border-[var(--rule)] bg-[var(--paper-2)] p-6 shadow-[0_1px_0_rgba(17,17,17,0.06)] transition hover:border-[var(--rule-strong)] hover:[box-shadow:0_1px_0_rgba(17,17,17,0.06),0_14px_38px_rgba(17,17,17,0.08)]"
                :href="it.url"
                target="_blank"
                rel="noreferrer"
                v-motion
                :initial="{ opacity: 0, y: 10 }"
                :enter="{ opacity: 1, y: 0, transition: { type: 'spring', stiffness: 140, damping: 20, delay: 140 + i * 45 } }"
              >
                <div class="flex items-center justify-between gap-3 text-xs text-[color:var(--muted)]">
                  <div class="flex items-center gap-3">
                    <span class="text-[color:var(--accent-ink)] tabular-nums">#{{ i + 1 }}</span>
                    <span v-if="it.category" class="uppercase tracking-[0.18em]">{{ it.category }}</span>
                    <span v-if="it.platform" class="truncate">· {{ it.platform }}</span>
                  </div>
                  <span v-if="it.published" class="tabular-nums">{{ formatPublished(it.published) }}</span>
                </div>
                <div class="mt-2 line-clamp-2 text-[18px] font-semibold leading-snug text-[color:var(--ink)] [font-family:var(--font-serif)] transition-colors group-hover:text-[color:var(--accent-ink)]">
                  {{ displayTitle(it) }}
                </div>
                <div v-if="it.summary && showSummaries" class="mt-2 line-clamp-3 text-sm leading-relaxed text-[color:var(--muted)]">
                  {{ it.summary }}
                </div>
              </a>
            </div>
          </section>
      </div>

      <div class="mt-10">
        <div class="flex items-baseline justify-between border-b border-[var(--rule)] pb-2">
          <div class="text-xs uppercase tracking-[0.26em] text-[color:var(--muted)]">all stories</div>
          <div class="text-xs text-[color:var(--muted)]">混合流 · {{ allStories.length }} 条</div>
        </div>

        <div
          v-if="!allStories.length"
          class="mt-6 rounded-[var(--radius)] border border-dashed border-[var(--rule)] bg-[var(--paper-2)] p-6 text-sm text-[color:var(--muted)]"
        >
          没有匹配条目（试试清空搜索或取消筛选）。
        </div>

        <div v-else class="mt-6 overflow-hidden rounded-[var(--radius)] border border-[var(--rule)] bg-[var(--paper-2)]">
          <a
            v-for="(it, i) in allStories"
            :key="it.url"
            class="group block border-b border-[var(--rule)] transition-colors duration-150 hover:bg-[color:rgba(17,17,17,0.012)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:rgba(139,29,44,0.30)] last:border-b-0"
            :href="it.url"
            target="_blank"
            rel="noreferrer"
          >
            <div class="mx-auto max-w-3xl px-6 py-6">
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-[color:var(--muted)]">
                <span class="tabular-nums text-[color:var(--accent-ink)]">{{ String(i + 1).padStart(2, '0') }}</span>
                <span v-if="it.category" class="uppercase tracking-[0.24em]">{{ it.category }}</span>
                <span v-if="it.platform" class="truncate">· {{ it.platform }}</span>
                <span v-if="it.published" class="ml-auto tabular-nums">{{ formatPublished(it.published) }}</span>
              </div>

              <div class="mt-2 text-[16px] font-semibold leading-snug text-[color:var(--ink)] transition-colors group-hover:text-[color:var(--accent-ink)]">
                {{ displayTitle(it) }}
              </div>

              <div v-if="it.summary && showSummaries" class="mt-2 line-clamp-3 text-sm leading-relaxed text-[color:var(--muted)]">
                {{ it.summary }}
              </div>

              <div v-if="it.source || typeof it.quality_score === 'number'" class="mt-3 flex items-center gap-3 text-[11px] text-[color:var(--muted)]">
                <span v-if="typeof it.quality_score === 'number'" class="tabular-nums">q {{ it.quality_score.toFixed(2) }}</span>
                <span v-if="it.source" class="truncate">源 {{ it.source }}</span>
              </div>
            </div>
          </a>
        </div>
      </div>

      <div v-if="filteredBackfillItems.length" class="mt-10">
        <details class="rounded-[var(--radius)] border border-[var(--rule)] bg-[var(--paper-2)] p-5 shadow-[var(--shadow-soft)]">
          <summary class="cursor-pointer text-sm text-[color:var(--ink)]">
            补读（历史库存） · {{ filteredBackfillItems.length }} 条
            <span class="ml-2 text-xs text-[color:var(--muted)]">建议只扫标题，避免被“库存”稀释注意力</span>
          </summary>
          <div class="mt-4 grid gap-3 lg:grid-cols-2">
            <a
              v-for="it in filteredBackfillItems"
              :key="it.url"
              class="group rounded-[16px] border border-[var(--rule)] bg-white/60 px-4 py-3 transition hover:border-[var(--rule-strong)]"
              :href="it.url"
              target="_blank"
              rel="noreferrer"
            >
              <div class="flex flex-wrap items-center gap-2 text-xs text-[color:var(--muted)]">
                <span v-if="it.platform" class="rounded-full border border-[var(--rule)] bg-white/60 px-2 py-0.5">
                  {{ it.platform }}
                </span>
                <span v-if="it.category" class="truncate">{{ it.category }}</span>
                <span v-if="it.published" class="ml-auto">{{ formatPublished(it.published) }}</span>
              </div>
              <div class="mt-2 line-clamp-2 text-sm font-semibold text-[color:var(--ink)] transition-colors group-hover:text-[color:var(--accent-ink)]">
                {{ displayTitle(it) }}
              </div>
            </a>
          </div>
        </details>
      </div>
    </section>

    <div class="mx-auto mt-10 max-w-6xl px-4 pb-10">
      <div class="flex justify-end">
        <RouterLink
          to="/lab/chat"
          class="rounded-md border border-[var(--rule)] bg-white/60 px-3 py-2 text-xs text-[color:var(--muted)] transition hover:border-[var(--rule-strong)] hover:text-[color:var(--ink)]"
        >
          Lab：Chat API 测试
        </RouterLink>
      </div>
    </div>
  </main>
</template>
