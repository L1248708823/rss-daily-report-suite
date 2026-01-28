<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

type Role = 'system' | 'user' | 'assistant'

type ChatMessage = {
  id: string
  role: Role
  content: string
  createdAt: number
}

const PROXY_BASE_URL =
  (import.meta as any).env?.VITE_LAB_CHAT_PROXY_BASE ? String((import.meta as any).env.VITE_LAB_CHAT_PROXY_BASE) : (import.meta as any).env?.DEV ? 'http://localhost:8787' : ''
const DEFAULT_API_KEY = (import.meta as any).env?.VITE_LAB_CHAT_API_KEY ? String((import.meta as any).env.VITE_LAB_CHAT_API_KEY) : ''
const DEFAULT_MODEL = (import.meta as any).env?.VITE_LAB_CHAT_MODEL ? String((import.meta as any).env.VITE_LAB_CHAT_MODEL) : 'gpt-5.2'
const ENDPOINT_PATH = '/v1/chat/completions'

type ImageAttachment = {
  id: string
  name: string
  mime: string
  size: number
  dataUrl: string
}

function uid(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`
}

function lsGet(key: string, fallback = ''): string {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

function lsSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // ignore
  }
}

const STORAGE_PREFIX = 'rss-lab-chat:'

const settingsOpen = ref<boolean>(lsGet(`${STORAGE_PREFIX}settingsOpen`, '0') === '1')
const apiKey = ref<string>(lsGet(`${STORAGE_PREFIX}apiKey`, DEFAULT_API_KEY))
const model = ref<string>(lsGet(`${STORAGE_PREFIX}model`, DEFAULT_MODEL))
const customModel = ref<string>(lsGet(`${STORAGE_PREFIX}customModel`, ''))
const temperature = ref<number>(Number(lsGet(`${STORAGE_PREFIX}temperature`, '0.2')) || 0.2)

const systemPrompt = ref<string>(lsGet(`${STORAGE_PREFIX}systemPrompt`, '你是一个严谨的中文助手。'))
const draft = ref<string>('')
const sending = ref(false)
const error = ref<string | null>(null)
const lastRawResponse = ref<string>('')

const messages = ref<ChatMessage[]>([])

const imageAttachments = ref<ImageAttachment[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)

const models = ref<string[]>([])
const modelsLoading = ref(false)
const modelsError = ref<string | null>(null)

const proxyBaseLabel = computed(() => (normalizeBaseUrl(PROXY_BASE_URL) ? normalizeBaseUrl(PROXY_BASE_URL) : '同源（当前站点）'))

const canSend = computed(
  () =>
    !sending.value &&
    (draft.value.trim().length > 0 || imageAttachments.value.length > 0),
)

function persistSettings() {
  lsSet(`${STORAGE_PREFIX}settingsOpen`, settingsOpen.value ? '1' : '0')
  lsSet(`${STORAGE_PREFIX}apiKey`, apiKey.value)
  lsSet(`${STORAGE_PREFIX}model`, model.value)
  lsSet(`${STORAGE_PREFIX}customModel`, customModel.value)
  lsSet(`${STORAGE_PREFIX}temperature`, String(temperature.value))
  lsSet(`${STORAGE_PREFIX}systemPrompt`, systemPrompt.value)
}

function normalizeBaseUrl(u: string): string {
  const t = u.trim().replace(/\/+$/, '')
  return t
}

function resolveModelId(): string {
  const picked = model.value.trim()
  if (picked && picked !== '__custom__') return picked
  return customModel.value.trim()
}

function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const k = apiKey.value.trim()
  if (k) headers.Authorization = `Bearer ${k}`
  return headers
}

async function fetchModels() {
  modelsError.value = null
  modelsLoading.value = true
  try {
    persistSettings()
    const base = normalizeBaseUrl(PROXY_BASE_URL)
    const url = `${base}/v1/models`
    const resp = await fetch(url, { method: 'GET', headers: buildHeaders() })
    const text = await resp.text()
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${text.slice(0, 400)}`)
    }
    const data = JSON.parse(text) as any
    const ids: unknown[] = Array.isArray(data?.data) ? data.data.map((x: any) => x?.id).filter(Boolean) : []
    const unique = [...new Set(ids.map((x) => String(x)))].sort()
    models.value = unique
    if (unique.length && !resolveModelId()) {
      model.value = unique[0] ?? '__custom__'
    }
  } catch (e) {
    modelsError.value = e instanceof Error ? e.message : String(e)
  } finally {
    modelsLoading.value = false
  }
}

function resetFileInput() {
  if (!fileInputRef.value) return
  fileInputRef.value.value = ''
}

function clearImages() {
  imageAttachments.value = []
  resetFileInput()
}

function removeImage(id: string) {
  imageAttachments.value = imageAttachments.value.filter((x) => x.id !== id)
  resetFileInput()
}

function pickImages() {
  fileInputRef.value?.click()
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error ?? new Error('read file failed'))
    reader.readAsDataURL(file)
  })
}

async function onFilesChange(e: Event) {
  const input = e.target as HTMLInputElement | null
  const files = input?.files ? Array.from(input.files) : []
  if (!files.length) return

  const maxFiles = 4
  const maxBytes = 5 * 1024 * 1024
  const picked = files.slice(0, maxFiles)

  const next: ImageAttachment[] = []
  for (const f of picked) {
    if (!String(f.type || '').startsWith('image/')) continue
    if (Number(f.size || 0) > maxBytes) {
      error.value = `图片过大：${f.name}（限制 5MB/张）`
      continue
    }
    const dataUrl = await readAsDataUrl(f)
    next.push({
      id: uid(),
      name: f.name,
      mime: String(f.type || ''),
      size: Number(f.size || 0),
      dataUrl,
    })
  }

  imageAttachments.value = [...imageAttachments.value, ...next].slice(0, maxFiles)
  resetFileInput()
}

const previewImage = ref<ImageAttachment | null>(null)
function openPreview(img: ImageAttachment) {
  previewImage.value = img
}
function closePreview() {
  previewImage.value = null
}

function toggleSettings() {
  settingsOpen.value = !settingsOpen.value
  persistSettings()
}

async function send() {
  if (!canSend.value) return
  error.value = null
  lastRawResponse.value = ''

  persistSettings()

  const userText = draft.value.trim()
  const imagesForThisSend = imageAttachments.value.slice()
  draft.value = ''

  const userId = uid()
  const displayUserContent =
    (userText ? userText : '') + (imagesForThisSend.length ? `${userText ? '\n' : ''}[已附加图片 ${imagesForThisSend.length} 张]` : '')
  messages.value.push({ id: userId, role: 'user', content: displayUserContent, createdAt: Date.now() })

  const sys = systemPrompt.value.trim()
  const payloadMessages = [
    ...(sys ? [{ role: 'system', content: sys } as const] : []),
    ...messages.value.map((m) => {
      if (m.role === 'user' && m.id === userId && imagesForThisSend.length) {
        const content: any[] = []
        if (userText) content.push({ type: 'text', text: userText })
        for (const img of imagesForThisSend) {
          content.push({ type: 'image_url', image_url: { url: img.dataUrl } })
        }
        return { role: m.role, content }
      }
      return { role: m.role, content: m.content }
    }),
  ].filter((m) => m.role !== 'assistant' || m.content.trim())

  sending.value = true
  try {
    const base = normalizeBaseUrl(PROXY_BASE_URL)
    const url = `${base}${ENDPOINT_PATH}`
    const headers = buildHeaders()

    const body = JSON.stringify({
      model: resolveModelId() || undefined,
      messages: payloadMessages,
      temperature: Number.isFinite(temperature.value) ? temperature.value : 0.2,
    })

    const resp = await fetch(url, { method: 'POST', headers, body })
    const text = await resp.text()
    lastRawResponse.value = text

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${text.slice(0, 400)}`)
    }

    let content = ''
    try {
      const data = JSON.parse(text) as any
      content =
        data?.choices?.[0]?.message?.content ??
        data?.choices?.[0]?.text ??
        data?.output_text ??
        data?.output?.[0]?.content?.map?.((x: any) => x?.text).filter(Boolean).join('\n') ??
        ''
    } catch {
      content = text
    }
    content = String(content || '').trim()
    if (!content) content = '(空响应：请查看 Raw Response)'

    messages.value.push({ id: uid(), role: 'assistant', content, createdAt: Date.now() })
    clearImages()

    await nextTick()
    queueMicrotask(() => {
      const el = document.getElementById('lab-chat-bottom')
      el?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    messages.value.push({
      id: uid(),
      role: 'assistant',
      content:
        '请求失败。常见原因：1) 中转站未开启 CORS；2) URL/路径不对；3) Key 无效；4) 目标接口不是 OpenAI chat.completions 兼容。',
      createdAt: Date.now(),
    })
  } finally {
    sending.value = false
  }
}

function clearChat() {
  messages.value = []
  error.value = null
  lastRawResponse.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter') return
  if (e.shiftKey || e.metaKey || e.ctrlKey || e.altKey) return
  e.preventDefault()
  void send()
}

onMounted(() => {
  // start with a tiny hint message
  if (!messages.value.length) {
    messages.value.push({
      id: uid(),
      role: 'assistant',
      content:
        `这是一个隔离的连通性测试页：不会影响日报功能。\n\nProxy Base：${proxyBaseLabel.value}\nEndpoint：${ENDPOINT_PATH}\n（静态站建议配同源反代或正确配置 CORS）\n\nKey 只保存在 localStorage 或从 web/.env.local 读取，不会写入仓库。`,
      createdAt: Date.now(),
    })
  }
})
</script>

<template>
  <div class="mx-auto max-w-5xl px-4 py-6">
    <div class="flex items-start justify-between gap-4">
      <div>
        <div class="text-sm uppercase tracking-[0.24em] text-[color:var(--muted)]">lab</div>
        <h1 class="mt-1 text-2xl font-semibold">Chat API 连通性测试</h1>
        <p class="mt-2 text-sm text-[color:var(--muted)]">目标：验证静态页面 + Node 代理能否调用 OpenAI 兼容中转站（含图片）。</p>
      </div>
      <div class="flex gap-2">
        <button
          class="rounded-md border border-[var(--rule)] px-3 py-2 text-sm hover:bg-black/5"
          type="button"
          @click="toggleSettings"
        >
          {{ settingsOpen ? '收起设置' : '设置' }}
        </button>
        <button class="rounded-md border border-[var(--rule)] px-3 py-2 text-sm hover:bg-black/5" type="button" @click="clearChat">
          清空
        </button>
        <a class="rounded-md border border-[var(--rule)] px-3 py-2 text-sm hover:bg-black/5" href="/" title="回到日报">
          回日报
        </a>
      </div>
    </div>

    <div v-if="settingsOpen" class="mt-5 rounded-xl border border-[var(--rule)] bg-white/70 p-4">
      <div class="text-sm font-medium">设置（可选）</div>

      <div class="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div>
          <label class="block text-xs font-medium text-[color:var(--muted)]">Proxy Base（已固化）</label>
          <div class="mt-1 w-full rounded-md border border-[var(--rule)] bg-black/5 px-3 py-2 text-sm text-black/70">
            {{ proxyBaseLabel }}
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-[color:var(--muted)]">Endpoint（已固化）</label>
          <div class="mt-1 w-full rounded-md border border-[var(--rule)] bg-black/5 px-3 py-2 text-sm text-black/70">
            {{ ENDPOINT_PATH }}
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-[color:var(--muted)]">API Key（仅本机存储）</label>
          <input
            v-model="apiKey"
            class="mt-1 w-full rounded-md border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-black/30"
            placeholder="sk-..."
            autocomplete="off"
            @blur="persistSettings"
          />
          <p class="mt-2 text-xs text-[color:var(--muted)]">注意：不要把 Key 写进仓库文件。此处只写入浏览器 localStorage。</p>
        </div>
      </div>

      <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div>
          <label class="block text-xs font-medium text-[color:var(--muted)]">Model</label>
          <select
            v-model="model"
            class="mt-1 w-full rounded-md border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-black/30"
            @change="persistSettings"
          >
            <template v-if="models.length">
              <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
            </template>
            <option value="__custom__">自定义…</option>
          </select>
          <input
            v-if="model === '__custom__'"
            v-model="customModel"
            class="mt-2 w-full rounded-md border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-black/30"
            placeholder="例如：gpt-5.2"
            @blur="persistSettings"
          />
          <div class="mt-2 flex items-center gap-2">
            <button
              class="rounded-md border border-[var(--rule)] px-2 py-1 text-xs hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              :disabled="modelsLoading"
              @click="fetchModels"
            >
              {{ modelsLoading ? '加载中…' : '刷新模型列表' }}
            </button>
            <span class="text-[11px] text-[color:var(--muted)]">
              {{ models.length ? `已加载 ${models.length} 个` : '未加载（可手动自定义）' }}
            </span>
          </div>
          <div v-if="modelsError" class="mt-2 text-[11px] text-rose-700">
            {{ modelsError }}
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-[color:var(--muted)]">Temperature</label>
          <input
            v-model.number="temperature"
            class="mt-1 w-full rounded-md border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-black/30"
            type="number"
            min="0"
            max="2"
            step="0.1"
            @blur="persistSettings"
          />
        </div>

        <div>
          <label class="block text-xs font-medium text-[color:var(--muted)]">System Prompt（可选）</label>
          <textarea
            v-model="systemPrompt"
            class="mt-1 h-24 w-full resize-none rounded-md border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-black/30"
            @blur="persistSettings"
          ></textarea>
        </div>
      </div>

      <div v-if="error" class="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
        {{ error }}
      </div>
    </div>

	    <div class="mt-5 rounded-xl border border-[var(--rule)] bg-white/70">
        <div class="flex items-center justify-between border-b border-[var(--rule)] px-4 py-3">
          <div class="text-sm font-medium">对话</div>
          <div class="text-xs text-[color:var(--muted)]">Enter 发送 · Shift+Enter 换行</div>
        </div>

        <div class="h-[60vh] overflow-auto px-4 py-4">
          <div v-for="m in messages" :key="m.id" class="mb-3">
            <div class="text-[11px] uppercase tracking-[0.22em] text-[color:var(--muted)]">
              {{ m.role }}
            </div>
            <div class="mt-1 whitespace-pre-wrap rounded-lg px-3 py-2 text-sm" :class="m.role === 'user' ? 'bg-black/5' : 'bg-white'">
              {{ m.content }}
            </div>
          </div>
          <div id="lab-chat-bottom"></div>
        </div>

        <div class="border-t border-[var(--rule)] p-4">
          <div class="mb-3">
            <div class="flex items-center justify-between gap-3">
              <div class="text-xs font-medium text-[color:var(--muted)]">图片（可选）</div>
              <input ref="fileInputRef" class="hidden" type="file" accept="image/*" multiple @change="onFilesChange" />
              <div class="flex items-center gap-2">
                <button class="rounded-md border border-[var(--rule)] px-2 py-1 text-xs hover:bg-black/5" type="button" @click="pickImages">
                  选择图片
                </button>
                <button
                  class="rounded-md border border-[var(--rule)] px-2 py-1 text-xs hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-60"
                  type="button"
                  :disabled="!imageAttachments.length"
                  @click="clearImages"
                >
                  清空
                </button>
              </div>
            </div>

            <div v-if="imageAttachments.length" class="mt-2">
              <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <div
                  v-for="img in imageAttachments"
                  :key="img.id"
                  class="group relative overflow-hidden rounded-md border border-[var(--rule)] bg-white"
                  role="button"
                  tabindex="0"
                  @click="openPreview(img)"
                >
                  <img :src="img.dataUrl" :alt="img.name" class="h-20 w-full object-cover" />
                  <div class="absolute inset-x-0 bottom-0 bg-black/50 px-2 py-1 text-left text-[11px] text-white/90">
                    <div class="truncate">{{ img.name }}</div>
                  </div>
                  <button
                    class="absolute right-1 top-1 rounded bg-black/60 px-2 py-1 text-[11px] text-white hover:bg-black/80"
                    type="button"
                    @click.stop="removeImage(img.id)"
                  >
                    移除
                  </button>
                </div>
              </div>
              <div class="mt-2 text-[11px] text-[color:var(--muted)]">限制：最多 4 张，每张 ≤ 5MB（base64 体积较大，中转站可能有限制）。</div>
            </div>
          </div>

          <textarea
            v-model="draft"
            class="h-24 w-full resize-none rounded-md border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-black/30"
            placeholder="输入一条消息，测试 API 是否可用…"
            @keydown="onKeydown"
          ></textarea>
          <div class="mt-2 flex items-center justify-between gap-3">
            <div class="text-xs text-[color:var(--muted)]">
              Raw Response：{{ lastRawResponse ? '已捕获（见下方）' : '无' }}
            </div>
            <button
              class="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              :disabled="!canSend"
              @click="send"
            >
              {{ sending ? '发送中…' : '发送' }}
            </button>
          </div>
          <details v-if="lastRawResponse" class="mt-3 rounded-md border border-[var(--rule)] bg-white px-3 py-2">
            <summary class="cursor-pointer text-xs font-medium">查看 Raw Response</summary>
            <pre class="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-5">{{ lastRawResponse }}</pre>
          </details>
        </div>
      </div>

    <div
      v-if="previewImage"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      @click="closePreview"
    >
      <div class="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-xl" @click.stop>
        <div class="flex items-center justify-between border-b border-[var(--rule)] px-4 py-3">
          <div class="truncate text-sm font-medium">{{ previewImage.name }}</div>
          <div class="flex items-center gap-2">
            <button class="rounded-md border border-[var(--rule)] px-3 py-2 text-sm hover:bg-black/5" type="button" @click="removeImage(previewImage.id)">
              移除
            </button>
            <button class="rounded-md border border-[var(--rule)] px-3 py-2 text-sm hover:bg-black/5" type="button" @click="closePreview">关闭</button>
          </div>
        </div>
        <div class="max-h-[calc(90vh-56px)] overflow-auto bg-black/5 p-4">
          <img :src="previewImage.dataUrl" :alt="previewImage.name" class="mx-auto max-h-[70vh] max-w-full rounded-md bg-white object-contain" />
        </div>
      </div>
    </div>
  </div>
</template>
