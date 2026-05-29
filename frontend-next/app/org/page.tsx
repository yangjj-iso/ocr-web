'use client'

import * as React from 'react'
import dayjs from 'dayjs'
import { motion } from 'framer-motion'
import { toast } from 'sonner'
import {
  CheckCircle2,
  Clock,
  Loader2,
  Shield,
  ShieldCheck,
  UserCheck,
  UserX,
  Users,
  XCircle,
} from 'lucide-react'

import { getAllUsers, approveUser, rejectUser, setUserAdmin } from '@/api/auth'
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

type UserItem = {
  id: number
  username: string
  status: string
  is_admin: boolean
  created_at: string
}

const STATUS_MAP: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  active: { label: '正常', color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle2 },
  pending: { label: '待审批', color: 'bg-amber-100 text-amber-700', icon: Clock },
  rejected: { label: '已拒绝', color: 'bg-red-100 text-red-700', icon: XCircle },
}

export default function OrgPage() {
  const [users, setUsers] = React.useState<UserItem[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')
  const [actionTarget, setActionTarget] = React.useState<{ user: UserItem; action: string } | null>(null)
  const [acting, setActing] = React.useState(false)

  const loadUsers = React.useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await getAllUsers()
      setUsers(data?.items || [])
    } catch (e: any) {
      const status = e?.response?.status
      if (status === 401 || status === 403) {
        setError('需要管理员权限才能查看组织成员。')
      } else {
        setError('加载成员列表失败，请稍后重试。')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => { loadUsers() }, [loadUsers])

  async function doAction() {
    if (!actionTarget) return
    setActing(true)
    try {
      const { user, action } = actionTarget
      if (action === 'approve') await approveUser(user.id)
      else if (action === 'reject') await rejectUser(user.id)
      else if (action === 'grant-admin') await setUserAdmin(user.id, true)
      else if (action === 'revoke-admin') await setUserAdmin(user.id, false)
      const successText: Record<string, string> = {
        approve: `已批准用户 "${user.username}"`,
        reject: `已拒绝用户 "${user.username}"`,
        'grant-admin': `已将 "${user.username}" 设为管理员`,
        'revoke-admin': `已撤销 "${user.username}" 的管理员权限`,
      }
      setActionTarget(null)
      await loadUsers()
      toast.success(successText[action] || '操作成功')
    } catch (_) {
      // 错误已由 axios 拦截器统一弹出 toast，此处仅保持对话框关闭状态不变
    } finally { setActing(false) }
  }

  function actionLabel() {
    if (!actionTarget) return ''
    switch (actionTarget.action) {
      case 'approve': return '批准'
      case 'reject': return '拒绝'
      case 'grant-admin': return '授予管理员'
      case 'revoke-admin': return '撤销管理员'
      default: return '确认'
    }
  }

  function actionDescription() {
    if (!actionTarget) return ''
    const name = actionTarget.user.username
    switch (actionTarget.action) {
      case 'approve': return `确认批准用户 "${name}" 的注册申请？批准后该用户可正常使用系统。`
      case 'reject': return `确认拒绝用户 "${name}" 的注册申请？`
      case 'grant-admin': return `确认将用户 "${name}" 设为管理员？管理员可管理所有用户和系统设置。`
      case 'revoke-admin': return `确认撤销用户 "${name}" 的管理员权限？`
      default: return ''
    }
  }

  const pendingUsers = users.filter(u => u.status === 'pending')
  const activeUsers = users.filter(u => u.status === 'active')
  const rejectedUsers = users.filter(u => u.status === 'rejected')

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-foreground">组织架构</h1>
        <p className="mt-1 text-sm text-muted-foreground">管理系统成员、审批注册申请、分配管理员权限。</p>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 text-sm text-muted-foreground">
          <Loader2 className="mb-2 h-5 w-5 animate-spin text-primary" />
          加载中...
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-20 text-sm text-muted-foreground">
          <Shield className="mb-3 h-10 w-10 text-muted-foreground/30" strokeWidth={1.5} />
          <p>{error}</p>
          <Button variant="outline" size="sm" className="mt-4" onClick={loadUsers}>重试</Button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground">总成员</p>
              <p className="mt-1 text-2xl font-bold text-foreground">{users.length}</p>
            </div>
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-xs text-amber-600">待审批</p>
              <p className="mt-1 text-2xl font-bold text-amber-700">{pendingUsers.length}</p>
            </div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <p className="text-xs text-emerald-600">正常</p>
              <p className="mt-1 text-2xl font-bold text-emerald-700">{activeUsers.length}</p>
            </div>
          </div>

          {/* Pending section */}
          {pendingUsers.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-700">
                <Clock className="h-4 w-4" /> 待审批（{pendingUsers.length}）
              </h2>
              <div className="space-y-2">
                {pendingUsers.map((user, i) => (
                  <UserRow key={user.id} user={user} index={i} onAction={setActionTarget} />
                ))}
              </div>
            </div>
          )}

          {/* Active section */}
          {activeUsers.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Users className="h-4 w-4" /> 正常成员（{activeUsers.length}）
              </h2>
              <div className="space-y-2">
                {activeUsers.map((user, i) => (
                  <UserRow key={user.id} user={user} index={i} onAction={setActionTarget} />
                ))}
              </div>
            </div>
          )}

          {/* Rejected section */}
          {rejectedUsers.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                <XCircle className="h-4 w-4" /> 已拒绝（{rejectedUsers.length}）
              </h2>
              <div className="space-y-2">
                {rejectedUsers.map((user, i) => (
                  <UserRow key={user.id} user={user} index={i} onAction={setActionTarget} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Confirm dialog */}
      <AlertDialog open={!!actionTarget} onOpenChange={(open) => { if (!open) setActionTarget(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{actionLabel()}</AlertDialogTitle>
            <AlertDialogDescription>{actionDescription()}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction disabled={acting} onClick={doAction}>
              {acting ? '处理中...' : actionLabel()}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function UserRow({ user, index, onAction }: { user: UserItem; index: number; onAction: (t: { user: UserItem; action: string }) => void }) {
  const statusInfo = STATUS_MAP[user.status] || STATUS_MAP.pending
  const StatusIcon = statusInfo.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03 }}
      className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 transition hover:shadow-sm"
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold text-foreground">
        {user.username.charAt(0).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-foreground">{user.username}</span>
          {user.is_admin && (
            <span className="flex items-center gap-0.5 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
              <ShieldCheck className="h-3 w-3" /> 管理员
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          注册于 {user.created_at ? dayjs(user.created_at).format('YYYY-MM-DD HH:mm') : '-'}
        </p>
      </div>
      <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-medium ${statusInfo.color}`}>
        <StatusIcon className="h-3 w-3" /> {statusInfo.label}
      </span>
      <div className="flex shrink-0 items-center gap-1">
        {user.status === 'pending' && (
          <>
            <Button size="sm" variant="outline" className="h-7 gap-1 text-xs text-emerald-600 hover:bg-emerald-50" onClick={() => onAction({ user, action: 'approve' })}>
              <UserCheck className="h-3 w-3" /> 批准
            </Button>
            <Button size="sm" variant="outline" className="h-7 gap-1 text-xs text-red-600 hover:bg-red-50" onClick={() => onAction({ user, action: 'reject' })}>
              <UserX className="h-3 w-3" /> 拒绝
            </Button>
          </>
        )}
        {user.status === 'active' && !user.is_admin && (
          <Button size="sm" variant="ghost" className="h-7 gap-1 text-xs" onClick={() => onAction({ user, action: 'grant-admin' })}>
            <ShieldCheck className="h-3 w-3" /> 设为管理员
          </Button>
        )}
        {user.status === 'active' && user.is_admin && (
          <Button size="sm" variant="ghost" className="h-7 gap-1 text-xs text-muted-foreground" onClick={() => onAction({ user, action: 'revoke-admin' })}>
            <Shield className="h-3 w-3" /> 撤销管理员
          </Button>
        )}
        {user.status === 'rejected' && (
          <Button size="sm" variant="outline" className="h-7 gap-1 text-xs text-emerald-600 hover:bg-emerald-50" onClick={() => onAction({ user, action: 'approve' })}>
            <UserCheck className="h-3 w-3" /> 重新批准
          </Button>
        )}
      </div>
    </motion.div>
  )
}
