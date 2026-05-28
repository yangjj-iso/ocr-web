'use client'

import * as React from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { ShieldCheck } from 'lucide-react'

import { useAuthState } from '@/hooks/use-auth-state'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { BackgroundBeams } from '@/components/aceternity/background-beams'
import { TextGenerateEffect } from '@/components/aceternity/text-generate-effect'

function LoginForm() {
  const router = useRouter()
  const params = useSearchParams()
  const authState = useAuthState()

  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState('')

  async function submitLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!username.trim() || !password) {
      setError('请输入账号和密码。')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      await authState.login(username.trim(), password)
      await authState.refreshAuthStatus(true)
      const redirect = params?.get('redirect') || '/'
      router.replace(redirect)
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || '登录未完成，请稍后重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-border bg-card shadow-float"
    >
      <div className="border-b border-border bg-muted/50 px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-violet-500 text-white shadow-glow-sm">
            <ShieldCheck className="h-4 w-4" />
          </span>
          <p className="text-xs font-semibold uppercase tracking-wider text-primary">身份认证</p>
        </div>
        <h2 className="mt-3 text-xl font-semibold text-foreground">
          <TextGenerateEffect words="系统登录" />
        </h2>
        <p className="mt-1.5 text-sm text-muted-foreground">请使用已开通账号登录，未开通账号可先提交注册申请。</p>
      </div>

      <form className="space-y-4 px-6 py-6" onSubmit={submitLogin}>
        <div className="space-y-1.5">
          <Label htmlFor="login-username">账号</Label>
          <Input id="login-username" type="text" autoComplete="username" placeholder="请输入账号" value={username} onChange={(event) => setUsername(event.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="login-password">密码</Label>
          <Input id="login-password" type="password" autoComplete="current-password" placeholder="请输入密码" value={password} onChange={(event) => setPassword(event.target.value)} />
        </div>

        {error && (
          <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {error}
          </motion.p>
        )}

        <Button type="submit" size="lg" className="w-full" disabled={submitting}>
          {submitting ? '登录中...' : '登录'}
        </Button>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>没有账号？</span>
          <Link className="text-primary hover:underline" href="/register">去注册</Link>
        </div>
      </form>
    </motion.section>
  )
}

export default function LoginPage() {
  return (
    <div className="relative isolate flex min-h-[calc(100vh-57px)] items-center justify-center overflow-hidden px-6 py-10">
      <BackgroundBeams />
      <React.Suspense fallback={null}>
        <LoginForm />
      </React.Suspense>
    </div>
  )
}
