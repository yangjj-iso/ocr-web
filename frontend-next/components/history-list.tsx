'use client'

import * as React from 'react'
import dayjs from 'dayjs'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight, FileText, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { deleteTasksBySubmission, getTaskSubmissions, getTasks } from '@/api/ocr'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

type HistoryGroup = {
  submission_id: string
  submission_name?: string
  submitter_username?: string
  batch_id?: string
  count: number
  last_time?: string
}

type HistoryListProps = {
  onViewResult?: (payload: { taskId: string | number; folder: string; submissionId: string; batchId: string }) => void
  onBatchContext?: (payload: { submissionId: string; batchId: string }) => void
}

export type HistoryListHandle = {
  refresh: () => void
}

function inferFolderPath(filePath = '') {
  const normalized = String(filePath || '')
  if (!normalized) return ''
  const slashIndex = Math.max(normalized.lastIndexOf('/'), normalized.lastIndexOf('\\'))
  return slashIndex >= 0 ? normalized.slice(0, slashIndex) : ''
}

function formatTime(value?: string) {
  return value ? dayjs(value).format('MM-DD HH:mm') : '-'
}

function canOpenTask(task: any) {
  return ['done', 'failed', 'human_review'].includes(String(task?.status || ''))
}

function submissionLabel(group: HistoryGroup) {
  return group?.submission_name || '未命名提交'
}

function submissionMeta(group: HistoryGroup) {
  const username = group?.submitter_username || '匿名用户'
  const batchSuffix = group?.batch_id ? ` · 批次 ${group.batch_id}` : ''
  return `提交人：${username}${batchSuffix}`
}

export const HistoryList = React.forwardRef<HistoryListHandle, HistoryListProps>(
  function HistoryList({ onViewResult, onBatchContext }, ref) {
    const [groups, setGroups] = React.useState<HistoryGroup[]>([])
    const [loading, setLoading] = React.useState(true)
    const [loadMessage, setLoadMessage] = React.useState('')
    const [expanded, setExpanded] = React.useState<Record<string, boolean>>({})
    const [submissionTasks, setSubmissionTasks] = React.useState<Record<string, { loading: boolean; tasks: any[] }>>({})
    const [deleteTarget, setDeleteTarget] = React.useState<HistoryGroup | null>(null)
    const [deleting, setDeleting] = React.useState(false)

    const loadSubmissions = React.useCallback(async () => {
      setLoading(true)
      setLoadMessage('')
      try {
        const { data } = await getTaskSubmissions()
        setGroups(data || [])
      } catch (error: any) {
        setGroups([])
        const text = `${error?.response?.data?.detail || ''} ${error?.message || ''}`.trim()
        const status = Number(error?.response?.status || 0)
        if (status === 502 || status === 503 || status === 504 || /ECONNREFUSED/i.test(text)) {
          setLoadMessage('后端服务暂未启动或尚未就绪，处理记录将在服务恢复后显示。')
        } else if (/ERR_NETWORK|network\s+error/i.test(text)) {
          setLoadMessage('网络环境已变化，请稍后重试。')
        } else {
          setLoadMessage('处理记录暂时无法加载，请稍后重试。')
        }
      } finally {
        setLoading(false)
      }
    }, [])

    const refresh = React.useCallback(() => {
      setExpanded({})
      setSubmissionTasks({})
      loadSubmissions()
    }, [loadSubmissions])

    React.useImperativeHandle(ref, () => ({ refresh }), [refresh])
    React.useEffect(() => { loadSubmissions() }, [loadSubmissions])

    async function toggleSubmission(submissionId: string) {
      const isExpanding = !expanded[submissionId]
      setExpanded((prev) => ({ ...prev, [submissionId]: isExpanding }))
      if (isExpanding && !submissionTasks[submissionId]) {
        setSubmissionTasks((prev) => ({ ...prev, [submissionId]: { loading: true, tasks: [] } }))
        const group = groups.find((g) => g.submission_id === submissionId)
        if (group?.batch_id) onBatchContext?.({ submissionId, batchId: group.batch_id })
        try {
          const { data } = await getTasks(1, 200, '', submissionId)
          setSubmissionTasks((prev) => ({ ...prev, [submissionId]: { loading: false, tasks: data?.tasks || [] } }))
        } catch (_) {
          setSubmissionTasks((prev) => ({ ...prev, [submissionId]: { loading: false, tasks: [] } }))
        }
      }
    }

    async function doDelete() {
      if (!deleteTarget?.submission_id) return
      const count = deleteTarget.count || 0
      setDeleting(true)
      try {
        await deleteTasksBySubmission(deleteTarget.submission_id)
        setDeleteTarget(null)
        await loadSubmissions()
        toast.success(`已删除 ${count} 份材料`)
      } catch (_) {
        // 错误已由 axios 拦截器统一弹出 toast
      } finally { setDeleting(false) }
    }

    if (loading) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
          <Loader2 className="mb-2 h-5 w-5 animate-spin text-primary" />
          正在加载处理记录...
        </div>
      )
    }

    if (!groups.length) {
      return (
        <div className="flex flex-col items-center justify-center py-14 text-sm text-muted-foreground">
          <FileText className="mb-3 h-10 w-10 text-muted-foreground/30" strokeWidth={1.5} />
          {loadMessage || '暂无处理记录，请先提交材料。'}
        </div>
      )
    }

    return (
      <div>
        <div className="space-y-2">
          {groups.map((group, gi) => (
            <motion.div
              key={group.submission_id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: gi * 0.04 }}
              className="overflow-hidden rounded-xl border border-border bg-white transition-shadow hover:shadow-card"
            >
              <div className="group flex cursor-pointer items-center px-4 py-3 transition hover:bg-muted/50" onClick={() => toggleSubmission(group.submission_id)}>
                <motion.div animate={{ rotate: expanded[group.submission_id] ? 90 : 0 }} transition={{ duration: 0.2 }}>
                  <ChevronRight className="mr-2 h-4 w-4 text-muted-foreground" />
                </motion.div>
                <div className={`mr-3 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition ${expanded[group.submission_id] ? 'bg-primary text-white' : 'bg-muted text-primary'}`}>
                  <FileText className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-foreground">{submissionLabel(group)}</span>
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">{group.count} 份材料</span>
                    {group.batch_id && <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] font-medium text-violet-700">可做批次分析</span>}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{submissionMeta(group)}</p>
                </div>
                <div className="ml-3 flex shrink-0 items-center gap-2">
                  <span className="text-xs text-muted-foreground">{formatTime(group.last_time)}</span>
                  <button className={`flex h-6 w-6 items-center justify-center rounded-md transition hover:bg-destructive/10 ${expanded[group.submission_id] ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} onClick={(e) => { e.stopPropagation(); setDeleteTarget(group) }}>
                    <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                  </button>
                </div>
              </div>

              <AnimatePresence>
                {expanded[group.submission_id] && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden border-t border-border"
                  >
                    {submissionTasks[group.submission_id]?.loading ? (
                      <div className="flex items-center justify-center py-6 text-xs text-muted-foreground"><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />加载材料列表...</div>
                    ) : submissionTasks[group.submission_id]?.tasks?.length ? (
                      <div className="max-h-[360px] overflow-y-auto">
                        {submissionTasks[group.submission_id].tasks.map((task: any) => (
                          <div key={task.id} className={`flex items-center border-b border-border/50 px-4 py-2.5 transition last:border-b-0 ${canOpenTask(task) ? 'cursor-pointer hover:bg-primary/5' : 'cursor-not-allowed opacity-60'}`} onClick={() => canOpenTask(task) && onViewResult?.({ taskId: task.id, folder: inferFolderPath(task.file_path), submissionId: group.submission_id, batchId: group.batch_id || task.batch_id || '' })}>
                            <div className="ml-6 mr-3 flex h-6 w-6 shrink-0 items-center justify-center">
                              <FileText className="h-4 w-4 text-muted-foreground/60" />
                            </div>
                            <div className="min-w-0 flex-1"><span className="truncate text-sm text-foreground">{task.filename || `任务 #${task.id}`}</span></div>
                            <div className="ml-2 flex shrink-0 items-center gap-2">
                              <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${task.status === 'done' ? 'bg-emerald-100 text-emerald-700' : task.status === 'failed' ? 'bg-red-100 text-red-700' : task.status === 'human_review' ? 'bg-violet-100 text-violet-700' : 'bg-amber-100 text-amber-700'}`}>
                                {task.status === 'done' ? '完成' : task.status === 'failed' ? '失败' : task.status === 'human_review' ? '待复核' : '处理中'}
                              </span>
                              <span className="text-[11px] text-muted-foreground">{formatTime(task.created_at)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="py-6 text-center text-xs text-muted-foreground">本次提交暂无材料记录。</div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>

        {/* Delete confirmation */}
        <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null) }}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>删除记录确认</AlertDialogTitle>
              <AlertDialogDescription>
                将删除提交记录 "{deleteTarget ? submissionLabel(deleteTarget) : ''}" 中的 {deleteTarget?.count || 0} 份材料。
                {deleteTarget && <span className="mt-1 block text-muted-foreground/70">{submissionMeta(deleteTarget)}</span>}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                disabled={deleting}
                onClick={doDelete}
              >
                {deleting ? '删除中...' : '确认删除'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    )
  }
)

