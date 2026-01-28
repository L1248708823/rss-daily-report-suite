#!/usr/bin/env node
import http from 'node:http'
import { Readable } from 'node:stream'

function parseArgs(argv) {
  const out = {
    port: undefined,
    upstream: undefined,
    allowOrigin: undefined,
    allowDynamicUpstream: undefined,
    stripPrefix: undefined,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i]
    if (a === '--help' || a === '-h') {
      out.help = true
      continue
    }
    if (a === '--port') {
      out.port = Number(argv[i + 1])
      i += 1
      continue
    }
    if (a === '--upstream') {
      out.upstream = argv[i + 1]
      i += 1
      continue
    }
    if (a === '--allow-origin') {
      out.allowOrigin = argv[i + 1]
      i += 1
      continue
    }
    if (a === '--allow-dynamic-upstream') {
      out.allowDynamicUpstream = true
      continue
    }
    if (a === '--strip-prefix') {
      out.stripPrefix = argv[i + 1]
      i += 1
      continue
    }
  }

  return out
}

function normalizeBaseUrl(u) {
  return String(u || '').trim().replace(/\/+$/, '')
}

function boolFromEnv(v) {
  const s = String(v || '').trim().toLowerCase()
  return s === '1' || s === 'true' || s === 'yes' || s === 'on'
}

function writeJson(res, statusCode, obj) {
  res.statusCode = statusCode
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(obj))
}

function setCors(req, res, allowOrigin) {
  const origin = allowOrigin || '*'
  res.setHeader('Access-Control-Allow-Origin', origin)
  res.setHeader('Vary', 'Origin')
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS')
  res.setHeader(
    'Access-Control-Allow-Headers',
    String(req.headers['access-control-request-headers'] || 'authorization,content-type'),
  )
  res.setHeader('Access-Control-Max-Age', '86400')
}

const args = parseArgs(process.argv.slice(2))

if (args.help) {
  console.log([
    'lab-openai-proxy (zero-deps)',
    '',
    '用途：把浏览器请求转发到“OpenAI 兼容”的国内中转站，并加上 CORS 响应头。',
    '',
    '用法：',
    '  node tools/lab-openai-proxy.mjs --upstream https://example.com/codex --port 8787',
    '',
    '环境变量（可选）：',
      '  LAB_OPENAI_UPSTREAM_BASE=...   上游 Base URL（默认用这个）',
      '  LAB_OPENAI_PORT=8787          监听端口',
      '  LAB_OPENAI_ALLOW_ORIGIN=*     CORS allow-origin（例如 http://localhost:5173）',
      '  LAB_OPENAI_ALLOW_DYNAMIC=1    允许用请求头 x-lab-upstream-base 动态指定上游（注意安全）',
      '  LAB_OPENAI_STRIP_PREFIX=/api  反代挂载在子路径时，剥离该前缀再转发（例如 /api/openai）',
      '  LAB_OPENAI_API_KEY=...        在代理侧注入 Authorization（避免把 Key 放前端）',
      '  LAB_OPENAI_FORCE_API_KEY=1    强制使用 LAB_OPENAI_API_KEY 覆盖客户端 Authorization',
      '',
      '参数：',
      '  --upstream <url>              同 LAB_OPENAI_UPSTREAM_BASE',
      '  --port <n>                    同 LAB_OPENAI_PORT',
      '  --allow-origin <origin>       同 LAB_OPENAI_ALLOW_ORIGIN',
      '  --allow-dynamic-upstream      同 LAB_OPENAI_ALLOW_DYNAMIC=1',
      '  --strip-prefix <path>         同 LAB_OPENAI_STRIP_PREFIX',
    ].join('\n'))
  process.exit(0)
}

const port = Number(args.port ?? process.env.LAB_OPENAI_PORT ?? 8787)
const allowOrigin = args.allowOrigin ?? process.env.LAB_OPENAI_ALLOW_ORIGIN ?? '*'
const allowDynamicUpstream = args.allowDynamicUpstream ?? boolFromEnv(process.env.LAB_OPENAI_ALLOW_DYNAMIC)
const stripPrefix = String(args.stripPrefix ?? process.env.LAB_OPENAI_STRIP_PREFIX ?? '').trim()
const upstreamApiKey = String(process.env.LAB_OPENAI_API_KEY ?? '').trim()
const forceUpstreamApiKey = boolFromEnv(process.env.LAB_OPENAI_FORCE_API_KEY)

const DEFAULT_UPSTREAM_BASE = 'https://right.codes/codex'
const fixedUpstream = normalizeBaseUrl(args.upstream ?? process.env.LAB_OPENAI_UPSTREAM_BASE ?? DEFAULT_UPSTREAM_BASE)

const server = http.createServer(async (req, res) => {
  setCors(req, res, allowOrigin)

  if (req.method === 'OPTIONS') {
    res.statusCode = 204
    res.end()
    return
  }

  const rawUrl = req.url || '/'
  let url = rawUrl
  if (stripPrefix) {
    const p = stripPrefix.startsWith('/') ? stripPrefix : `/${stripPrefix}`
    if (url === p) url = '/'
    else if (url.startsWith(`${p}/`)) url = url.slice(p.length)
  }
  if (url === '/healthz') {
    writeJson(res, 200, { ok: true })
    return
  }

  const headerUpstream = normalizeBaseUrl(req.headers['x-lab-upstream-base'])
  const upstreamBase = allowDynamicUpstream ? (headerUpstream || fixedUpstream) : fixedUpstream
  if (!upstreamBase) {
    writeJson(res, 400, {
      error: 'missing_upstream_base',
      hint: '请设置 LAB_OPENAI_UPSTREAM_BASE 或使用 --upstream 指定；本地调试也可开启 LAB_OPENAI_ALLOW_DYNAMIC=1 用 x-lab-upstream-base 覆盖。',
    })
    return
  }

  let upstreamUrl = ''
  try {
    const u = new URL(upstreamBase)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') throw new Error('invalid protocol')
    let pathAndQuery = url
    if (String(upstreamBase).endsWith('/v1') && String(url).startsWith('/v1/')) {
      pathAndQuery = url.slice(3)
    }
    upstreamUrl = `${upstreamBase}${pathAndQuery.startsWith('/') ? '' : '/'}${pathAndQuery}`
  } catch {
    writeJson(res, 400, {
      error: 'invalid_upstream_base',
      value: upstreamBase,
      hint: '上游 Base URL 必须是合法的 http(s) URL，例如：https://xxx.example.com 或 https://xxx.example.com/prefix',
    })
    return
  }

  const forwardHeaders = {}
  for (const [k0, v0] of Object.entries(req.headers || {})) {
    if (!v0) continue
    const k = k0.toLowerCase()
    if (k === 'host') continue
    if (k === 'connection') continue
    if (k === 'content-length') continue
    if (k === 'accept-encoding') continue
    if (k === 'origin') continue
    if (k === 'referer') continue
    if (k === 'x-lab-upstream-base') continue
    forwardHeaders[k] = Array.isArray(v0) ? v0.join(',') : String(v0)
  }

  if (upstreamApiKey && (forceUpstreamApiKey || !forwardHeaders.authorization)) {
    forwardHeaders.authorization = `Bearer ${upstreamApiKey}`
  }

  const m = String(req.method || 'GET').toUpperCase()
  const hasBody = !['GET', 'HEAD'].includes(m)

  try {
    const upstreamResp = await fetch(upstreamUrl, {
      method: req.method,
      headers: forwardHeaders,
      body: hasBody ? req : undefined,
      duplex: hasBody ? 'half' : undefined,
    })

    res.statusCode = upstreamResp.status

    upstreamResp.headers.forEach((value, key) => {
      const k = key.toLowerCase()
      if (k === 'content-encoding') return
      if (k === 'transfer-encoding') return
      res.setHeader(key, value)
    })

    if (upstreamResp.body) {
      Readable.fromWeb(upstreamResp.body).pipe(res)
      return
    }

    res.end()
  } catch (e) {
    writeJson(res, 502, {
      error: 'upstream_fetch_failed',
      upstreamUrl,
      message: e instanceof Error ? e.message : String(e),
    })
  }
})

server.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log(`[lab-openai-proxy] listening on http://localhost:${port}`)
  // eslint-disable-next-line no-console
  console.log(`[lab-openai-proxy] allow-origin: ${allowOrigin}`)
  // eslint-disable-next-line no-console
  console.log(`[lab-openai-proxy] upstream: ${fixedUpstream || '(unset)'}`)
  // eslint-disable-next-line no-console
  console.log(`[lab-openai-proxy] allow-dynamic-upstream: ${allowDynamicUpstream ? 'yes' : 'no'}`)
  // eslint-disable-next-line no-console
  console.log(`[lab-openai-proxy] strip-prefix: ${stripPrefix || '(none)'}`)
  // eslint-disable-next-line no-console
  console.log(`[lab-openai-proxy] api-key: ${upstreamApiKey ? '(set)' : '(unset)'}${forceUpstreamApiKey ? ' (force)' : ''}`)
})
