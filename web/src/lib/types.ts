export type NewsDayIndex = {
  updated_at?: string
  days: Array<{
    date: string
    count?: number
  }>
}

export type NewsItem = {
  date?: string
  platform?: string
  source?: string
  source_url?: string
  title: string
  title_zh?: string | null
  url: string
  published?: string | null
  category?: string | null
  carrier?: string | null
  pin?: 'lead' | 'top' | null
  quality_score?: number | null
  keywords?: string[] | null
  summary?: string | null
  key_points?: string[] | null
}

export type NewsDayData = {
  date: string
  generated_at?: string
  meta?: {
    market?: {
      requested_date?: string
      fetched_at?: string
      note?: string
      indicators?: Array<{
        id: string
        name?: string
        value?: number
        change?: number | null
        change_pct?: number | null
        prev_close?: number | null
        unit?: string | null
        currency?: string | null
        provider?: string | null
        source_url?: string | null
        as_of?: string | null
      }>
      errors?: string[]
    }
  } & Record<string, unknown>
  items: NewsItem[]
  backfill_items?: NewsItem[]
}
