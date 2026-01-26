import type { NewsDayData, NewsDayIndex } from './types'

export async function fetchNewsIndex(): Promise<NewsDayIndex> {
  const r = await fetch('/api/news/index.json', { cache: 'no-store' })
  if (!r.ok) {
    throw new Error(`fetchNewsIndex failed: ${r.status}`)
  }
  return (await r.json()) as NewsDayIndex
}

export async function fetchNewsDay(date: string): Promise<NewsDayData> {
  const r = await fetch(`/api/news/${date}.json`, { cache: 'no-store' })
  if (!r.ok) {
    throw new Error(`fetchNewsDay failed: ${r.status}`)
  }
  return (await r.json()) as NewsDayData
}

