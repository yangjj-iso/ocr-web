'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import dayjs from 'dayjs'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Calendar,
  ChevronRight,
  Clock,
  File,
  FileText,
  Loader2,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-react'

import { getTaskThumbnailUrl, searchTasks } from '@/api/ocr'
import { getModeLabel, getStatusLabel } from '@/lib/ui-copy'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'

const STATUS_DOT: Record<string, string> = {
  done: 'bg-emerald-500',
  failed: 'bg-rose-500',
  human_review: 'bg-violet-500',
  processing: 'bg-amber-400',
  pending: 'bg-muted-foreground/40',
}

const MODE_CLASS: Record<string, string> = {
  vl: 'bg-primary/10 text-primary',
  layout: 'bg-blue-100 text-blue-700',
  ocr: 'bg-emerald-100 text-emerald-700',
}

interface SearchFilters {
  dateRange: 'all' | '7d' | '30d' | '90d' | 'custom'
  status: string[]
  mode: string[]
  sortBy: 'relevance' | 'date_desc' | 'date_asc'
}

const DEFAULT_FILTERS: SearchFilters = {
  dateRange: 'all',
  status: [],
  mode: [],
  sortBy: 'relevance',
}

const DATE_OPTIONS = [
  { value: 'all', label: '全部时间' },
  { value: '7d', label: '最近 7 天' },
  { value: '30d', label: '最近 30 天' },
  { value: '90d', label: '最近 90 天' },
]

const STATUS_OPTIONS = [
  { value: 'done', label: '已完成' },
  { value: 'processing', label: '处理中' },
  { value: 'failed', label: '失败' },
  { value: 'human_review', label: '人工审核' },
]

const MODE_OPTIONS = [
  { value: 'vl', label: 'VL 模型' },
  { value: 'layout', label: '版面分析' },
  { value: 'ocr', label: '传统 OCR' },
]

const SORT_OPTIONS = [
  { value: 'relevance', label: '相关度' },
  { value: 'date_desc', label: '最新优先' },
  { value: 'date_asc', label: '最早优先' },
]

function canOpenResult(item: any) {
  return ['done', 'failed', 'human_review'].includes(String(item?.status || ''))
}

function formatTime(value?: string) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'
}

function highlightSnippet(text: string, keyword: string) {
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  if (!keyword) return escaped
  const re = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escaped.replace(new RegExp(`(${re})`, 'gi'), '<mark class="bg-amber-200/60 px-0.5 rounded">$1</mark>')
}

const PAGE_SIZE = 20

export default function SearchPage() {
  const router = useRouter()
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [query, setQuery] = React.useState('')
  const [lastQuery, setLastQuery] = React.useState('')
  const [results, setResults] = React.useState<any[]>([])
  const [total, setTotal] = React.useState(0)
  const [page, setPage] = React.useState(1)
  const [loading, setLoading] = React.useState(false)
  const [searched, setSearched] = React.useState(false)
  const [filters, setFilters] = React.useState<SearchFilters>(DEFAULT_FILTERS)
  const [showFilters, setShowFilters] = React.useState(false)
  const debounceRef = React.useRef<number | null>(null)

  React.useEffect(() => { inputRef.current?.focus() }, [])

  const totalPageCount = Math.ceil(total / PAGE_SIZE)
  const hasActiveFilters = filters.dateRange !== 'all' || filters.status.length > 0 || filters.mode.length > 0 || filters.sortBy !== 'relevance'

  async function doSearch(resetPage = true) {
    const keyword = query.trim()
    if (!keyword) return
    const p = resetPage ? 1 : page
    if (resetPage) setPage(1)
    setLoading(true)
    setSearched(true)
    setLastQuery(keyword)
    try {
      const { data } = await searchTasks(keyword, p, PAGE_SIZE)
      setResults(data.tasks || [])
      setTotal(data.total || 0)
    } catch (_) { setResults([]); setTotal(0) }
    finally { setLoading(false) }
  }

  function onInput(e: React.ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (e.target.value.trim().length >= 2) {
      debounceRef.current = window.setTimeout(() => doSearch(), 400)
    }
  }

  function goPage(nextPage: number) {
    setPage(nextPage)
    doSearch(false)
  }

  function toggleFilter(key: 'status' | 'mode', value: string) {
    setFilters((prev) => ({
      ...prev,
      [key]: prev[key].includes(value) ? prev[key].filter((v) => v !== value) : [...prev[key], value],
    }))
  }

  function clearFilters() {
    setFilters(DEFAULT_FILTERS)
  }

  return (
    <div className="flex h-[calc(100vh-57px)]">
      <AnimatePresence>
        {showFilters && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 260, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="shrink-0 overflow-hidden border-r border-border bg-muted/20"
          >
            <div className="flex h-full w-[260px] flex-col">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <span className="text-sm font-medium text-foreground">筛选条件</span>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setShowFilters(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6">
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">时间范围</p>
                  <div className="space-y-1">
                    {DATE_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setFilters((f) => ({ ...f, dateRange: opt.value as SearchFilters['dateRange'] }))}
                        className={cn(
                          'flex w-full items-center rounded-lg px-3 py-2 text-sm transition',
                          filters.dateRange === opt.value ? 'bg-primary/10 font-medium text-primary' : 'text-foreground hover:bg-muted'
                        )}
                      >
                        <Calendar className="mr-2 h-3.5 w-3.5" />
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">处理状态</p>
                  <div className="space-y-1">
                    {STATUS_OPTIONS.map((opt) => (
                      <label key={opt.value} className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-muted">
                        <Checkbox
                          checked={filters.status.includes(opt.value)}
                          onCheckedChange={() => toggleFilter('status', opt.value)}
                        />
                        <span className={cn('h-2 w-2 rounded-full', STATUS_DOT[opt.value])} />
                        {opt.label}
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">识别模式</p>
                  <div className="space-y-1">
                    {MODE_OPTIONS.map((opt) => (
                      <label key={opt.value} className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-muted">
                        <Checkbox
                          checked={filters.mode.includes(opt.value)}
                          onCheckedChange={() => toggleFilter('mode', opt.value)}
                        />
                        {opt.label}
                      </label>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">排序方式</p>
                  <div className="space-y-1">
                    {SORT_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setFilters((f) => ({ ...f, sortBy: opt.value as SearchFilters['sortBy'] }))}
                        className={cn(
                          'flex w-full items-center rounded-lg px-3 py-2 text-sm transition',
                          filters.sortBy === opt.value ? 'bg-primary/10 font-medium text-primary' : 'text-foreground hover:bg-muted'
                        )}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {hasActiveFilters && (
                <div className="border-t border-border px-4 py-3">
                  <Button variant="secondary" size="sm" className="w-full" onClick={clearFilters}>
                    清除所有筛选
                  </Button>
                </div>
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="shrink-0 border-b border-border bg-card/50 px-6 py-5">
          <div className="mx-auto max-w-4xl">
            <div className="flex items-center gap-3">
              <Button
                variant={showFilters || hasActiveFilters ? 'default' : 'outline'}
                className={cn(
                  'h-10 gap-2',
                  (showFilters || hasActiveFilters) && 'bg-primary/10 text-primary hover:bg-primary/20 border-primary/30'
                )}
                onClick={() => setShowFilters(!showFilters)}
              >
                <SlidersHorizontal className="h-4 w-4" />
                筛选
                {hasActiveFilters && (
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white">
                    {(filters.status.length + filters.mode.length + (filters.dateRange !== 'all' ? 1 : 0))}
                  </span>
                )}
              </Button>
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={onInput}
                  onKeyDown={(e) => e.key === 'Enter' && doSearch()}
                  placeholder="Search..."
                  className="h-10 w-full rounded-lg border border-border bg-white pl-9 pr-24 text-sm shadow-sm transition focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
                {searched && (
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                    {total} results
                  </span>
                )}
              </div>
            </div>

            {hasActiveFilters && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {filters.dateRange !== 'all' && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                    {DATE_OPTIONS.find((d) => d.value === filters.dateRange)?.label}
                    <button onClick={() => setFilters((f) => ({ ...f, dateRange: 'all' }))} className="ml-0.5 rounded-full hover:bg-primary/20"><X className="h-3 w-3" /></button>
                  </span>
                )}
                {filters.status.map((s) => (
                  <span key={s} className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                    {STATUS_OPTIONS.find((o) => o.value === s)?.label}
                    <button onClick={() => toggleFilter('status', s)} className="ml-0.5 rounded-full hover:bg-primary/20"><X className="h-3 w-3" /></button>
                  </span>
                ))}
                {filters.mode.map((m) => (
                  <span key={m} className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                    {MODE_OPTIONS.find((o) => o.value === m)?.label}
                    <button onClick={() => toggleFilter('mode', m)} className="ml-0.5 rounded-full hover:bg-primary/20"><X className="h-3 w-3" /></button>
                  </span>
                ))}
                {filters.sortBy !== 'relevance' && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                    {SORT_OPTIONS.find((o) => o.value === filters.sortBy)?.label}
                    <button onClick={() => setFilters((f) => ({ ...f, sortBy: 'relevance' }))} className="ml-0.5 rounded-full hover:bg-primary/20"><X className="h-3 w-3" /></button>
                  </span>
                )}
                <button onClick={clearFilters} className="text-xs text-muted-foreground hover:text-foreground">全部清除</button>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="mx-auto max-w-4xl">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-20">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="mt-3 text-sm text-muted-foreground">正在检索...</p>
              </div>
            ) : searched && !results.length ? (
              <div className="flex flex-col items-center justify-center py-20">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
                  <Search className="h-7 w-7 text-muted-foreground" />
                </div>
                <p className="mt-4 text-sm font-medium text-foreground">未找到相关结果</p>
                <p className="mt-1 text-xs text-muted-foreground">没有找到包含"{lastQuery}"的记录，请尝试其他关键词</p>
              </div>
            ) : !searched ? (
              <div className="flex flex-col items-center justify-center py-20">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
                  <FileText className="h-7 w-7 text-primary" />
                </div>
                <p className="mt-4 text-sm font-medium text-foreground">全文档检索</p>
                <p className="mt-1 max-w-sm text-center text-xs text-muted-foreground">
                  基于 Elasticsearch 的全文检索引擎，支持文件名、正文内容、结构化字段的模糊匹配与精确查询
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {['档号', '责任者', '题名', '日期', '密级'].map((tag) => (
                    <span key={tag} className="rounded-full border border-border bg-card px-3 py-1 text-xs text-muted-foreground">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {results.map((item, i) => (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className={cn(
                      'group flex overflow-hidden rounded-xl border border-border bg-white transition-all',
                      canOpenResult(item) ? 'cursor-pointer hover:border-primary/30 hover:shadow-card' : 'cursor-not-allowed opacity-70'
                    )}
                    onClick={() => canOpenResult(item) && router.push(`/result/${item.id}`)}
                  >
                    <div className="relative h-24 w-28 shrink-0 overflow-hidden bg-muted">
                      <img src={getTaskThumbnailUrl(item.id)} className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" alt="" />
                    </div>
                    <div className="min-w-0 flex-1 px-4 py-3">
                      <div className="mb-1 flex items-center gap-2">
                        <File className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <h3 className="truncate text-sm font-semibold text-foreground">{item.filename}</h3>
                        <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium', MODE_CLASS[item.mode] || 'bg-muted text-muted-foreground')}>
                          {getModeLabel(item.mode)}
                        </span>
                      </div>
                      {item.snippet && (
                        <p
                          className="mb-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground"
                          dangerouslySetInnerHTML={{ __html: highlightSnippet(item.snippet, lastQuery) }}
                        />
                      )}
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{item.page_count || 0} 页</span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatTime(item.created_at)}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className={cn('h-1.5 w-1.5 rounded-full', STATUS_DOT[item.status] || 'bg-muted-foreground/40')} />
                          {getStatusLabel(item.status)}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center px-3 text-muted-foreground/40 transition group-hover:text-primary">
                      <ChevronRight className="h-5 w-5" />
                    </div>
                  </motion.div>
                ))}

                {total > PAGE_SIZE && (
                  <div className="flex items-center justify-center gap-1.5 pt-6">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => goPage(page - 1)}
                    >
                      上一页
                    </Button>
                    {Array.from({ length: Math.min(totalPageCount, 7) }, (_, i) => {
                      let p: number
                      if (totalPageCount <= 7) p = i + 1
                      else if (page <= 4) p = i + 1
                      else if (page >= totalPageCount - 3) p = totalPageCount - 6 + i
                      else p = page - 3 + i
                      return (
                        <Button
                          key={p}
                          variant={page === p ? 'default' : 'ghost'}
                          size="icon"
                          className="h-8 w-8 text-xs"
                          onClick={() => goPage(p)}
                        >
                          {p}
                        </Button>
                      )
                    })}
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPageCount}
                      onClick={() => goPage(page + 1)}
                    >
                      下一页
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
