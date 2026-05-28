'use client'

import * as React from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { LogOut, Settings, Sparkles, User } from 'lucide-react'

import { useAuthState } from '@/hooks/use-auth-state'
import { cn } from '@/lib/utils'
import { AnimatedGradientText } from '@/components/aceternity/animated-gradient-text'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const NAV_ITEMS = [
  { to: '/', label: '首页' },
  { to: '/workbench', label: '工作台' },
  { to: '/chat', label: '问答台' },
  { to: '/search', label: '信息检索' },
  { to: '/org', label: '组织架构', adminOnly: true },
]

const AUTH_PAGES = ['/login', '/register']

function isActiveRoute(pathname: string, target: string) {
  if (target === '/') return pathname === '/'
  return pathname === target || pathname.startsWith(target + '/')
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || '/'
  const router = useRouter()
  const authState = useAuthState()
  const [bootstrapped, setBootstrapped] = React.useState(false)

  const isAuthPage = AUTH_PAGES.includes(pathname)
  const visibleNavItems = NAV_ITEMS.filter(
    (item) => !item.adminOnly || !authState.auth?.enabled || authState.auth?.is_admin
  )

  React.useEffect(() => {
    let mounted = true
    authState.refreshAuthStatus(true).finally(() => {
      if (mounted) setBootstrapped(true)
    })
    return () => { mounted = false }
  }, [])

  async function handleLogout() {
    await authState.logout()
    router.replace('/login')
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-border/60 bg-white/70 backdrop-blur-xl">
        <div className="flex h-14 items-center justify-between px-6">
          <Link href="/" className="group flex items-center gap-2.5 no-underline">
            <motion.span
              whileHover={{ scale: 1.05, rotate: 3 }}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-violet-500 text-white shadow-glow-sm"
            >
              <Sparkles className="h-4 w-4" />
            </motion.span>
            <span className="text-base font-semibold tracking-tight text-foreground">
              <AnimatedGradientText>OmniScan</AnimatedGradientText>
            </span>
          </Link>

          {!isAuthPage && (
            <nav className="flex items-center gap-1">
              {visibleNavItems.map((item) => (
                <Link
                  key={item.to}
                  href={item.to}
                  className={cn(
                    'relative rounded-lg px-3.5 py-2 text-sm font-medium transition-colors',
                    isActiveRoute(pathname, item.to)
                      ? 'text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {isActiveRoute(pathname, item.to) && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-lg bg-muted"
                      transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }}
                    />
                  )}
                  <span className="relative z-10">{item.label}</span>
                </Link>
              ))}
            </nav>
          )}

          {!isAuthPage && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 rounded-full border border-border bg-muted px-2 py-1 transition hover:bg-muted/80">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-white text-xs font-medium">
                    {authState.auth?.username?.charAt(0)?.toUpperCase() || <User className="h-3.5 w-3.5" />}
                  </span>
                  <span className="text-sm font-medium text-foreground">{authState.auth?.username || '用户'}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuLabel>
                  <p className="text-sm font-medium">{authState.auth?.username || '用户'}</p>
                  <p className="text-xs font-normal text-muted-foreground">已登录</p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <Settings className="mr-2 h-4 w-4" />
                  设置
                </DropdownMenuItem>
                <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={handleLogout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </header>

      <AnimatePresence mode="wait">
        <motion.main
          key={pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="flex-1"
        >
          {children}
        </motion.main>
      </AnimatePresence>
    </div>
  )
}
