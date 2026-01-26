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
  quality_score?: number | null
  keywords?: string[] | null
  summary?: string | null
  key_points?: string[] | null
}

export type NewsDayData = {
  date: string
  generated_at?: string
  meta?: Record<string, unknown>
  items: NewsItem[]
}

