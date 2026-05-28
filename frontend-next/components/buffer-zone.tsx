'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FolderOpen, Settings2, X, Clock, Play, Download, Sparkles, BarChart3, Users } from 'lucide-react'

import { useBatchUpload, formatSize } from '@/hooks/use-batch-upload'
import { buildMergedDocumentViews } from '@/lib/merge-document-display'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { ShimmerButton } from '@/components/aceternity/shimmer-button'
import { CardHoverEffect } from '@/components/aceternity/card-hover-effect'

type ModelConfig = {
  mode: string
  name: string
  desc: string
  badge?: string
  color?: string
  icon?: string
}

type BufferZoneProps = {
  model: ModelConfig
  onStartBatch?: () => void
  onBatchCompleted?: (payload: any) => void
  onViewResult?: (payload: { taskId: string | number; batchId: string }) => void
}

function pct(value: any) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`
}

export function BufferZone({ model, onStartBatch, onBatchCompleted, onViewResult }: BufferZoneProps) {
  const router = useRouter()
  const [dragover, setDragover] = React.useState(false)
  const [batchDialogOpen, setBatchDialogOpen] = React.useState(false)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const folderInputRef = React.useRef<HTMLInputElement>(null)

  const batch = useBatchUpload(model.mode, {
    onSubmitted: () => onStartBatch?.(),
    onCompleted: (payload) => onBatchCompleted?.(payload),
  })

  const mergedDocuments = React.useMemo(() => buildMergedDocumentViews(batch.aiMergeResult), [batch.aiMergeResult])
  const operationalMetrics = batch.aiMetrics?.operational_metrics || null
  const hasQueueItems = batch.queue.length > 0 || batch.pathQueue.length > 0
  const hasImportActivity = hasQueueItems || batch.processing || batch.batchDone || batch.importStage !== 'idle'
  const previewQueueFiles = batch.queueExpanded ? batch.queue : batch.queue.slice(0, 2)
  const previewPathFiles = batch.queueExpanded ? batch.pathQueue : batch.pathQueue.slice(0, 3)
  const hiddenQueueCount = Math.max(0, batch.queue.length + batch.pathQueue.length - previewQueueFiles.length - previewPathFiles.length)
  const showQueueToggle = batch.queue.length + batch.pathQueue.length > 5
  const activeProcessingCount = batch.processingCount + batch.pendingCount

  React.useEffect(() => {
    if (hasImportActivity) setBatchDialogOpen(true)
  }, [hasImportActivity])

  const stageMeta = React.useMemo(() => {
    switch (batch.importStage) {
      case 'scanning': return { eyebrow: '目录整理', title: '正在整理导入材料', description: '系统正在核对目录中的可识别材料，完成后再展示摘要和明细。' }
      case 'ready': return { eyebrow: '待开始处理', title: '材料已整理完成', description: '可以先查看摘要，再按需展开明细并发起批量处理。' }
      case 'uploading': return { eyebrow: '材料提交', title: '正在提交材料', description: '材料正在进入后台队列，请保持页面开启。' }
      case 'processing': return { eyebrow: '后台识别', title: '正在识别处理中', description: '系统正在后台完成识别和归档整理，可先查看阶段进度。' }
      case 'completed': return { eyebrow: '处理完成', title: '本次处理已完成', description: '可以导出目录清单、查看批次概览或继续发起智能整合。' }
      default: return { eyebrow: '批量处理', title: '等待导入材料', description: '支持本地文件、目录和授权路径导入，系统会先整理摘要再展示明细。' }
    }
  }, [batch.importStage])

  const actionButtonLabel = React.useMemo(() => {
    if (batch.processing) {
      if (batch.importStage === 'uploading') return '材料提交中…'
      if (batch.importStage === 'processing') return '后台识别中…'
      return '处理中…'
    }
    return batch.scheduledTime ? '定时开始处理' : '开始处理'
  }, [batch.processing, batch.importStage, batch.scheduledTime])

  function openTask(taskId: string | number) {
    if (!taskId) return
    onViewResult?.({ taskId, batchId: String(batch.lastBatchId || '').trim() })
  }

  function openBatchInsights() {
    if (!batch.lastBatchId) return
    router.push(`/batch-insights/${encodeURIComponent(batch.lastBatchId)}`)
  }

  function openBoundaryReview() {
    if (!batch.lastBatchId) return
    router.push(`/batch-insights/${encodeURIComponent(batch.lastBatchId)}?tab=truth`)
  }

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <motion.div
          animate={{ borderColor: dragover ? 'hsl(245 58% 51%)' : 'hsl(220 13% 91%)' }}
          className={`cursor-pointer rounded-xl border-2 border-dashed px-8 py-16 text-center transition-colors ${dragover ? 'bg-primary/5' : 'hover:border-primary/40 hover:bg-muted/50'}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragover(true) }}
          onDragLeave={() => setDragover(false)}
          onDrop={(e) => { e.preventDefault(); setDragover(false); batch.onDrop(e) }}
        >
          <motion.div
            animate={dragover ? { scale: 1.1, y: -4 } : { scale: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 300 }}
          >
            <Upload className="mx-auto mb-4 h-12 w-12 text-muted-foreground/50" strokeWidth={1.5} />
          </motion.div>
          <p className="text-sm font-medium text-foreground">拖拽材料到这里，或 <span className="text-primary">点击选择</span></p>
          <p className="mt-2 text-xs text-muted-foreground">支持 JPG / PNG / PDF，可批量导入文件或本地目录</p>
        </motion.div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-3.5 w-3.5" /> 选择文件
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => folderInputRef.current?.click()}>
            <FolderOpen className="h-3.5 w-3.5" /> 选择目录
          </Button>
          <Button variant="ghost" size="sm" className="gap-1.5 border border-dashed border-border" onClick={batch.toggleViewMode}>
            <Settings2 className="h-3.5 w-3.5" /> {batch.isAdvancedView ? '收起高级设置' : '高级设置'}
          </Button>
        </div>

        {/* Advanced settings */}
        <AnimatePresence>
          {batch.isAdvancedView && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-3 rounded-xl border border-border bg-muted/50 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-xs font-medium text-foreground">高级设置</p>
                  <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={batch.toggleViewMode}>收起</Button>
                </div>
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input type="text" placeholder="输入已授权的目录路径" value={batch.folderPath} onChange={(e) => batch.setFolderPath(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && batch.importFromPath()} className="w-full rounded-lg border border-border bg-white px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30" />
                    <Button size="sm" className="shrink-0" disabled={!batch.folderPath.trim() || batch.scanning} onClick={() => batch.importFromPath()}>
                      {batch.scanning ? '导入中…' : '目录导入'}
                    </Button>
                  </div>
                  <input type="text" placeholder="归档目录导出位置（可选）" value={batch.excelPath} onChange={(e) => batch.setExcelPath(e.target.value)} className="w-full rounded-lg border border-border bg-white px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30" />
                  <input type="text" placeholder="处理结果保存位置（可选）" value={batch.outputDir} onChange={(e) => batch.setOutputDir(e.target.value)} className="w-full rounded-lg border border-border bg-white px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/30" />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <input ref={fileInputRef} type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.tiff,.tif,.pdf" className="hidden" onChange={batch.onFileSelect} />
        <input ref={folderInputRef} type="file" multiple className="hidden" onChange={batch.onFolderSelect} {...{ webkitdirectory: '' } as any} />
      </div>

      {/* Batch processing dialog */}
      <Dialog open={batchDialogOpen} onOpenChange={(open) => { if (!open && !batch.processing) { setBatchDialogOpen(false); batch.clearQueue() } }}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden p-0">
          <DialogHeader className="border-b border-border px-6 py-4">
            <DialogTitle>{stageMeta.title}</DialogTitle>
            <DialogDescription>{batch.importMessage || stageMeta.description}</DialogDescription>
          </DialogHeader>
          <div className="max-h-[calc(85vh-140px)] space-y-4 overflow-y-auto px-6 py-4">
            {/* Progress */}
            <div>
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold uppercase tracking-wider text-primary">{stageMeta.eyebrow}</span>
                <span className="rounded-full border border-border px-2.5 py-0.5 font-mono font-medium text-foreground">{Math.round(batch.importProgressPercent)}%</span>
              </div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border/50">
                <motion.div className="h-full rounded-full bg-primary" initial={{ width: 0 }} animate={{ width: `${batch.importProgressPercent}%` }} transition={{ duration: 0.3 }} />
              </div>
              {batch.displayQueueSummary.totalFiles > 0 && (
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  <div className="rounded-lg border border-border bg-muted/30 px-3 py-2"><p className="text-muted-foreground">材料数量</p><p className="mt-0.5 font-semibold text-foreground">{batch.displayQueueSummary.totalFiles} 份</p></div>
                  <div className="rounded-lg border border-border bg-muted/30 px-3 py-2"><p className="text-muted-foreground">涉及目录</p><p className="mt-0.5 font-semibold text-foreground">{batch.displayQueueSummary.folderCount || 0} 个</p></div>
                  <div className="rounded-lg border border-border bg-muted/30 px-3 py-2"><p className="text-muted-foreground">总大小</p><p className="mt-0.5 font-semibold text-foreground">{batch.displayQueueSummary.totalSizeLabel}</p></div>
                </div>
              )}
              {batch.totalCount > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
                  <div className="rounded-lg border border-border bg-muted/30 px-3 py-2"><p className="text-muted-foreground">批次总量</p><p className="mt-0.5 font-semibold text-foreground">{batch.totalCount} 份</p></div>
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2"><p className="text-emerald-600">已完成</p><p className="mt-0.5 font-semibold text-emerald-700">{batch.completedCount} 份</p></div>
                  <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2"><p className="text-blue-600">处理中</p><p className="mt-0.5 font-semibold text-blue-700">{activeProcessingCount} 份</p></div>
                  <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2"><p className="text-amber-600">异常数</p><p className="mt-0.5 font-semibold text-amber-700">{batch.failedCount} 份</p></div>
                </div>
              )}
              {batch.scanMsg && <p className={`mt-3 text-xs ${batch.scanError ? 'text-destructive' : 'text-emerald-600'}`}>{batch.scanMsg}</p>}
            </div>

            {/* Queue list */}
            {hasQueueItems && !batch.processing && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-medium text-muted-foreground">待处理明细（{batch.queue.length + batch.pathQueue.length}）</span>
                  <div className="flex items-center gap-2">
                    {showQueueToggle && <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={batch.toggleQueueExpanded}>{batch.queueExpanded ? '收起明细' : `展开全部（${batch.queue.length + batch.pathQueue.length}）`}</Button>}
                    <Button variant="link" size="sm" className="h-auto p-0 text-xs text-destructive" onClick={batch.clearQueue}>清空</Button>
                  </div>
                </div>
                <div className="max-h-44 space-y-1.5 overflow-y-auto">
                  {previewQueueFiles.map((file, index) => (
                    <div key={`file-${index}`} className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs">
                      <div className="min-w-0 flex-1 truncate text-foreground">{(file as any).webkitRelativePath || (file as any)._relativePath || file.name}<span className="ml-2 text-muted-foreground">{formatSize(file.size)}</span></div>
                      <button className="text-muted-foreground hover:text-destructive" onClick={() => batch.removeFile(index)}>移除</button>
                    </div>
                  ))}
                  {previewPathFiles.map((file, index) => (
                    <div key={`path-${index}`} className="flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs">
                      <div className="min-w-0 flex-1 truncate text-foreground">{file.rel_path}<span className="ml-2 text-muted-foreground">{formatSize(file.size)}</span></div>
                      <button className="text-muted-foreground hover:text-destructive" onClick={() => batch.removePathFile(index)}>移除</button>
                    </div>
                  ))}
                  {hiddenQueueCount > 0 && <div className="rounded-lg border border-dashed border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">还有 {hiddenQueueCount} 份材料未展开</div>}
                </div>
              </div>
            )}

            {/* Completed actions */}
            {batch.batchDone && batch.lastBatchId && !batch.processing && (
              <div className="grid grid-cols-2 gap-2">
                <Button size="sm" className="gap-1" onClick={batch.doExportInitExcel}><Download className="h-3 w-3" />导出目录清单</Button>
                <Button size="sm" className="gap-1 bg-emerald-600 hover:bg-emerald-700" onClick={batch.doExportExcel}><Download className="h-3 w-3" />导出本次归档</Button>
                <Button size="sm" className="gap-1 bg-violet-600 hover:bg-violet-700" disabled={batch.aiMerging} onClick={() => batch.runAiMergeExtract()}>
                  <Sparkles className="h-3 w-3" />{batch.aiMerging ? '智能整合中…' : '智能整合'}
                </Button>
                <Button size="sm" variant="secondary" className="gap-1" disabled={!batch.lastBatchId} onClick={openBatchInsights}>
                  <BarChart3 className="h-3 w-3" />质量概览
                </Button>
              </div>
            )}
            {batch.aiMergeError && <p className="text-xs text-destructive">{batch.aiMergeError}</p>}
            {batch.aiMergeResult && !batch.aiMerging && (
              <p className="text-xs text-emerald-600">智能整合已完成，已形成 {mergedDocuments.length || batch.aiMergeResult.summary?.documents_count} 份归并文件建议。</p>
            )}
          </div>

          {/* Footer with action button */}
          <div className="border-t border-border px-6 py-4">
            <div className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              <label className="text-xs text-muted-foreground">定时开始</label>
              <input type="datetime-local" value={batch.scheduledTime} onChange={(e) => batch.setScheduledTime(e.target.value)} className="flex-1 rounded-lg border border-border px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary/30" />
              {batch.scheduledTime && <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => batch.setScheduledTime('')}><X className="h-3.5 w-3.5" /></Button>}
            </div>
            <ShimmerButton className="mt-3 w-full" disabled={batch.processing || !hasQueueItems} onClick={() => batch.startBatch()}>
              <Play className="h-4 w-4" /> {actionButtonLabel}
            </ShimmerButton>
          </div>
        </DialogContent>
      </Dialog>

      {/* AI Merge Result Modal */}
      <Dialog open={!!batch.aiMergeResult} onOpenChange={(open) => { if (!open) batch.clearAiMergeResult() }}>
        <DialogContent className="max-h-[85vh] max-w-5xl overflow-hidden p-0">
          <DialogHeader className="border-b border-border px-6 py-4">
            <DialogTitle>智能整合结果</DialogTitle>
            <DialogDescription>已生成可核对的归并文件和字段建议。</DialogDescription>
          </DialogHeader>
          <div className="max-h-[calc(85vh-100px)] space-y-4 overflow-y-auto px-6 py-4">
            <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
              <div className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-muted-foreground">原始材料：<span className="font-medium text-foreground">{batch.aiMergeResult?.summary?.total_tasks}</span></div>
              <div className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-muted-foreground">可分析材料：<span className="font-medium text-foreground">{batch.aiMergeResult?.summary?.eligible_tasks}</span></div>
              <div className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-muted-foreground">判定分组：<span className="font-medium text-foreground">{batch.aiMergeResult?.summary?.groups_count}</span></div>
              <div className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-muted-foreground">归并文件：<span className="font-medium text-foreground">{batch.aiMergeResult?.summary?.documents_count}</span></div>
            </div>

            <div className="rounded-xl border border-border bg-muted/30 p-4">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-semibold text-foreground">统计概览</p>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" className="h-6 text-[11px]" disabled={batch.aiMerging} onClick={() => batch.runAiMergeExtract({ forceRefresh: true })}>{batch.aiMerging ? '分析中…' : '重新分析'}</Button>
                  <Button size="sm" className="h-6 text-[11px]" onClick={openBatchInsights}>查看质量概览</Button>
                  <Button variant="outline" size="sm" className="h-6 gap-1 text-[11px]" onClick={openBoundaryReview}><Users className="h-3 w-3" />人工校核归并</Button>
                </div>
              </div>
              {batch.aiMetricsLoading && <p className="text-xs text-muted-foreground">质量分析中…</p>}
              {batch.aiMetricsError && <p className="text-xs text-destructive">{batch.aiMetricsError}</p>}
              {operationalMetrics && (
                <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
                  <div className="rounded-lg bg-white px-3 py-2 text-foreground">字段完整率：<span className="font-semibold">{pct(operationalMetrics.field_fill_rate?.recommended)}</span></div>
                  <div className="rounded-lg bg-white px-3 py-2 text-foreground">待核对率：<span className="font-semibold">{pct(operationalMetrics.conflict_rate)}</span></div>
                  <div className="rounded-lg bg-white px-3 py-2 text-foreground">整合可信度：<span className="font-semibold">{pct(operationalMetrics.avg_same_document_confidence)}</span></div>
                  <div className="rounded-lg bg-white px-3 py-2 text-foreground">双路一致度：<span className="font-semibold">{pct(operationalMetrics.avg_rule_llm_agreement)}</span></div>
                </div>
              )}
            </div>

            {mergedDocuments.map((doc: any) => (
              <motion.div key={doc.key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-border bg-white p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div><p className="text-sm font-semibold text-foreground">归并文件 {doc.index}</p><p className="mt-0.5 text-xs text-muted-foreground">{doc.sourceSummary}</p></div>
                  <span className="rounded-full border border-border px-2 py-0.5 text-[11px] font-mono text-muted-foreground">可信度 {doc.sameDocumentConfidence.toFixed(2)}</span>
                </div>
                <div className="mb-3 rounded-lg border border-border bg-muted/30 px-4 py-3">
                  <p className="mb-1 text-[11px] font-medium text-muted-foreground">归并文件名</p>
                  <p className="text-sm font-semibold text-foreground">{doc.displayName}</p>
                  {doc.title && <p className="mt-1 text-xs text-muted-foreground">题名建议：{doc.title}</p>}
                  {doc.primaryTaskId && (
                    <Button variant="outline" size="sm" className="mt-2 h-6 text-[11px]" onClick={() => openTask(doc.primaryTaskId)}>{doc.sourceCount > 1 ? '查看首页' : '查看文件'}</Button>
                  )}
                </div>
                <div className="mb-3 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
                  <p className="mb-1 text-[11px] font-medium text-primary">判定依据</p>
                  <p className="text-xs leading-5 text-foreground">{doc.decisionReasons?.join('；') || '-'}</p>
                </div>
                {doc.document && (
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
                    <div className="mb-2 flex items-center justify-between text-xs text-emerald-700">
                      <span>合并页数：{doc.mergedPageCount}</span>
                      <span>协同一致度：{doc.agreementRatio?.toFixed(2)}</span>
                    </div>
                    <div className="grid gap-1.5 text-xs md:grid-cols-2">
                      {Object.entries(doc.recommendedFields || {}).map(([field, value]) => (
                        <div key={`${doc.key}-${field}`} className="rounded-lg bg-white px-3 py-1.5 text-foreground"><span className="text-muted-foreground">{field}：</span>{String(value || '-')}</div>
                      ))}
                    </div>
                    {doc.conflictFields?.length > 0 && <p className="mt-2 text-xs text-amber-600">待核对字段：{doc.conflictFields.join('、')}</p>}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
