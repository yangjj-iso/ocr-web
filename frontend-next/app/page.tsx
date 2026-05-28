'use client'

import * as React from 'react'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { FileSearch, MessageSquare, Sun, Upload, Users } from 'lucide-react'

import { useAuthState } from '@/hooks/use-auth-state'
import { TextGenerateEffect } from '@/components/aceternity/text-generate-effect'
import { CardHoverEffect } from '@/components/aceternity/card-hover-effect'

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

function getWeatherIcon(code?: string) {
  return <Sun className="h-5 w-5" />
}

export default function HomePage() {
  const authState = useAuthState()
  const [weather, setWeather] = React.useState<{ temp: string; text: string } | null>(null)
  const greeting = getGreeting()

  React.useEffect(() => {
    // Placeholder: fetch weather from API in the future
    setWeather({ temp: '--', text: '晴' })
  }, [])

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-10"
      >
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          <TextGenerateEffect words={`${greeting}，欢迎回来`} />
        </h1>
        {weather && (
          <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
            {getWeatherIcon()}
            <span>{weather.text} {weather.temp}°</span>
            <span className="text-border">|</span>
            <span>{new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })}</span>
          </div>
        )}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
      >
        <p className="mb-4 text-sm font-medium text-muted-foreground">快捷入口</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link href="/workbench" className="no-underline">
            <CardHoverEffect>
              <div className="flex items-center gap-4 p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Upload className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">工作台</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">上传文档，AI 识别与抽取</p>
                </div>
              </div>
            </CardHoverEffect>
          </Link>

          <Link href="/chat" className="no-underline">
            <CardHoverEffect>
              <div className="flex items-center gap-4 p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-500/10 text-violet-600">
                  <MessageSquare className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">问答台</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">基于文档的智能问答</p>
                </div>
              </div>
            </CardHoverEffect>
          </Link>

          <Link href="/search" className="no-underline">
            <CardHoverEffect>
              <div className="flex items-center gap-4 p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600">
                  <FileSearch className="h-6 w-6" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">信息检索</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">跨文档全文搜索</p>
                </div>
              </div>
            </CardHoverEffect>
          </Link>

          {(!authState.auth?.enabled || authState.auth?.is_admin) && (
            <Link href="/org" className="no-underline">
              <CardHoverEffect>
                <div className="flex items-center gap-4 p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600">
                    <Users className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">组织架构</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">租户与权限管理</p>
                  </div>
                </div>
              </CardHoverEffect>
            </Link>
          )}
        </div>
      </motion.div>
    </div>
  )
}
