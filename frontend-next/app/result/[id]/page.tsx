'use client'

import * as React from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, ChevronLeft, ChevronRight, Copy, Download, FileText, Loader2 } from 'lucide-react'

import { useResultViewState } from '@/hooks/use-result-view-state'
import { getTaskFileUrl, getTaskPageImageUrl } from '@/api/ocr'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'

export default function ResultPage() {
  const params = useParams()
  const router = useRouter()
  const taskId = params?.id as string

  const rv = useResultViewState(taskId)

  const isTaskProcessing = rv.task && !['done', 'failed', 'human_review'].includes(rv.task.status) && !rv.pages.length
  const isTaskFailed = rv.task?.status === 'failed' && !rv.pages.length

  function goBack() { router.push('/') }

  if (rv.loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (rv.error) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-destructive">{rv.error}</div>
    )
  }

  if (isTaskProcessing) {
    return (
      <div className="flex h-screen items-center justify-center bg-background px-6">
        <div className="w-full max-w-lg rounded-2xl border border-border bg-card px-6 py-8 text-center shadow-card">
          <Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" />
          <p className="mt-4 text-lg font-semibold text-foreground">当前材料正在识别处理中</p>
          <p className="mt-2 text-sm leading-7 text-muted-foreground">系统会在后台持续完成识别与结构整理，处理结束后会自动刷新当前页面。</p>
          <Button variant="outline" className="mt-5" onClick={goBack}>返回工作台</Button>
        </div>
      </div>
    )
  }

  if (isTaskFailed) {
    return (
      <div className="flex h-screen items-center justify-center bg-background px-6">
        <div className="w-full max-w-lg rounded-2xl border border-destructive/30 bg-destructive/5 px-6 py-8 text-center">
          <p className="mt-4 text-lg font-semibold text-destructive">当前材料处理异常</p>
          <p className="mt-2 text-sm leading-7 text-destructive/80">{rv.task?.error_message || '当前记录未能生成可展示的识别结果。'}</p>
          <Button variant="outline" className="mt-5 border-destructive/30 text-destructive hover:bg-destructive/10" onClick={goBack}>返回工作台</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* Top bar */}
      <div className="flex shrink-0 items-center justify-between border-b border-border bg-card px-4 py-2">
        <div className="flex min-w-0 items-center gap-3">
          <button className="rounded-lg p-1.5 transition hover:bg-muted" onClick={goBack}><ArrowLeft className="h-5 w-5 text-muted-foreground" /></button>
          <div className="min-w-0">
            <h2 className="truncate text-sm font-medium text-foreground">{rv.task?.filename || '加载中...'}</h2>
            <p className="text-xs text-muted-foreground">{rv.task?.page_count || 0} 页</p>
          </div>
          <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${rv.modeClass}`}>{rv.modeLabel}</span>
          <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${rv.statusClass(rv.task?.status)}`}>{rv.statusLabel(rv.task?.status)}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {rv.polling && <span className="text-primary">后台处理中，结果会自动刷新</span>}
          <span>{rv.task?.updated_at ? rv.formatTime(rv.task.updated_at) : ''}</span>
        </div>
      </div>

      {/* Main content */}
      <div className="flex min-h-0 flex-1">
        {/* Folder sidebar */}
        {rv.folderPath && (
          <aside className="flex min-h-0 w-[32%] min-w-[320px] max-w-[420px] shrink-0 flex-col border-r border-border bg-muted/30">
            <div className="border-b border-border bg-card px-4 py-3">
              <p className="truncate text-sm font-semibold text-foreground">{rv.folderLabel}</p>
              <p className="mt-1 text-xs text-muted-foreground">{rv.folderTasks.length} 份材料</p>
            </div>
            {rv.folderLoading ? (
              <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">目录加载中...</div>
            ) : !rv.folderTasks.length ? (
              <div className="flex flex-1 items-center justify-center px-4 text-center text-xs text-muted-foreground/70">暂无可展示材料</div>
            ) : (
              <div className="flex-1 space-y-1 overflow-y-auto p-2">
                {rv.folderTasks.map((t: any) => (
                  <div key={t.id} className={`flex cursor-pointer items-center rounded-lg border px-3 py-2 text-xs transition ${String(t.id) === String(taskId) ? 'border-primary/30 bg-primary/5' : 'border-transparent bg-white hover:border-border'}`} onClick={() => rv.switchTask(t.id)}>
                    <FileText className="mr-2 h-4 w-4 shrink-0 text-muted-foreground/60" />
                    <span className="min-w-0 flex-1 truncate text-foreground">{t.filename || `#${t.id}`}</span>
                    <span className={`ml-2 rounded px-1 py-0.5 text-[10px] font-medium ${rv.statusClass(t.status)}`}>{rv.statusLabel(t.status)}</span>
                  </div>
                ))}
              </div>
            )}
          </aside>
        )}

        {/* Result viewer */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Tabs */}
          <div className="flex items-center justify-between border-b border-border bg-card px-4 py-2">
            <Tabs value={rv.activeTab} onValueChange={(v: any) => rv.setActiveTab(v)}>
              <TabsList>
                <TabsTrigger value="parsed">识别结果</TabsTrigger>
                <TabsTrigger value="json">结构数据</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={rv.copyAll}><Copy className="mr-1 h-3.5 w-3.5" />复制全文</Button>
              <Button variant="ghost" size="sm" onClick={rv.downloadTxt}><Download className="mr-1 h-3.5 w-3.5" />导出TXT</Button>
            </div>
          </div>

          {/* Page navigation */}
          {rv.totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 border-b border-border/50 bg-card py-2 text-xs">
              <button className="rounded-lg p-1 hover:bg-muted disabled:opacity-30" disabled={rv.pageNum <= 1} onClick={() => rv.setPageNum(rv.pageNum - 1)}><ChevronLeft className="h-4 w-4" /></button>
              <span className="font-mono text-foreground">{rv.pageNum} / {rv.totalPages}</span>
              <button className="rounded-lg p-1 hover:bg-muted disabled:opacity-30" disabled={rv.pageNum >= rv.totalPages} onClick={() => rv.setPageNum(rv.pageNum + 1)}><ChevronRight className="h-4 w-4" /></button>
            </div>
          )}

          {/* Content area */}
          <div className="flex min-h-0 flex-1 overflow-hidden">
            {rv.activeTab === 'parsed' ? (
              <div className="flex min-h-0 flex-1">
                {/* Image preview */}
                <div className="flex w-1/2 items-center justify-center overflow-auto border-r border-border bg-muted/30 p-4">
                  {rv.isPdf ? (
                    <img src={getTaskPageImageUrl(taskId, rv.pageNum)} className="max-h-full max-w-full rounded-lg shadow-card" alt="page" />
                  ) : (
                    <img src={getTaskFileUrl(taskId)} className="max-h-full max-w-full rounded-lg shadow-card" alt="file" />
                  )}
                </div>
                {/* Regions */}
                <div className="w-1/2 overflow-y-auto p-4">
                  {rv.currentPage.regions?.length ? (
                    <div className="space-y-3">
                      {rv.currentPage.regions.map((region: any, idx: number) => (
                        <div key={`r-${idx}`} className="rounded-lg border border-border bg-white p-3">
                          <div className="mb-1 flex items-center justify-between">
                            <span className="text-[10px] font-medium text-muted-foreground/70">区域 {idx + 1} · {region.type || 'text'}</span>
                            <button className="text-[10px] text-primary hover:underline" onClick={() => rv.copyRegion(region)}>复制</button>
                          </div>
                          {region.table_data ? (
                            <div className="overflow-x-auto">
                              <table className="w-full border-collapse text-xs">
                                <tbody>
                                  {region.table_data.map((row: any[], ri: number) => (
                                    <tr key={ri}>{row.map((cell, ci) => <td key={ci} className="border border-border px-2 py-1">{cell}</td>)}</tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="whitespace-pre-wrap text-xs leading-6 text-foreground">{region.content}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : rv.currentPage.lines?.length ? (
                    <div className="space-y-1">
                      {rv.currentPage.lines.map((line: any, idx: number) => (
                        <p key={`l-${idx}`} className="text-xs leading-6 text-foreground">{line.text}</p>
                      ))}
                    </div>
                  ) : (
                    <p className="py-8 text-center text-xs text-muted-foreground">当前页暂无识别内容。</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 overflow-auto p-4">
                <pre className="whitespace-pre-wrap rounded-lg border border-border bg-white p-4 font-mono text-xs text-foreground">{rv.jsonText}</pre>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Toast */}
      {rv.toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-lg bg-foreground px-4 py-2 text-xs text-white shadow-float">{rv.toast}</div>
      )}
    </div>
  )
}
