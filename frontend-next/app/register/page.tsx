'use client'

import * as React from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { UserPlus } from 'lucide-react'

import { useAuthState } from '@/hooks/use-auth-state'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { BackgroundBeams } from '@/components/aceternity/background-beams'
import { TextGenerateEffect } from '@/components/aceternity/text-generate-effect'

export default function RegisterPage() {
  const authState = useAuthState()

  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [confirmPassword, setConfirmPassword] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState('')
  const [success, setSuccess] = React.useState('')

  async function submitRegister(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = username.trim()
    if (!name || !password || !confirmPassword) {
      setError('请完整填写注册信息。')
      setSuccess('')
      return
    }
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致。')
      setSuccess('')
      return
    }
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      const data: any = await authState.register(name, password)
      setSuccess(data?.message || '注册申请已提交，请等待管理员审核。')
      setPassword('')
      setConfirmPassword('')
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || '注册未完成，请稍后重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative isolate flex min-h-[calc(100vh-57px)] items-center justify-center overflow-hidden px-6 py-10">
      <BackgroundBeams />
      <motion.section
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-border bg-card shadow-float"
      >
        <div className="border-b border-border bg-muted/50 px-6 py-5">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-primary text-white shadow-glow-sm">
              <UserPlus className="h-4 w-4" />
            </span>
            <p className="text-xs font-semibold uppercase tracking-wider text-primary">账号申请</p>
          </div>
          <h2 className="mt-3 text-xl font-semibold text-foreground">
            <TextGenerateEffect words="提交注册申请" />
          </h2>
          <p className="mt-1.5 text-sm text-muted-foreground">注册后需管理员审核，通过后即可登录系统。</p>
        </div>

        <form className="space-y-4 px-6 py-6" onSubmit={submitRegister}>
          <div className="space-y-1.5">
            <Label htmlFor="register-username">账号</Label>
            <Input id="register-username" type="text" autoComplete="username" placeholder="3-120 位字符" value={username} onChange={(event) => setUsername(event.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="register-password">密码</Label>
            <Input id="register-password" type="password" autoComplete="new-password" placeholder="至少 6 位" value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="register-confirm">确认密码</Label>
            <Input id="register-confirm" type="password" autoComplete="new-password" placeholder="请再次输入密码" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
          </div>

          {success && (
            <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
              {success}
            </motion.p>
          )}
          {error && (
            <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              {error}
            </motion.p>
          )}

          <Button type="submit" size="lg" className="w-full" disabled={submitting}>
            {submitting ? '提交中...' : '提交注册'}
          </Button>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>已有账号？</span>
            <Link className="text-primary hover:underline" href="/login">返回登录</Link>
          </div>
        </form>
      </motion.section>
    </div>
  )
}
