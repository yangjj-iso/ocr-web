'use client'

import * as React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowUp,
  AtSign,
  Globe,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Paperclip,
  Plus,
  Sparkles,
  Trash2,
  User,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

interface Conversation {
  id: string
  title: string
  messages: Message[]
  updatedAt: Date
}

const SUGGESTIONS = [
  '帮我总结这份文档的核心内容',
  '提取文档中的关键日期和人物',
  '这份档案的归档编号是什么？',
  '对比两份文件的差异',
]

export default function ChatPage() {
  const [conversations, setConversations] = React.useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = React.useState<string | null>(null)
  const [messages, setMessages] = React.useState<Message[]>([])
  const [input, setInput] = React.useState('')
  const [isTyping, setIsTyping] = React.useState(false)
  const [sidebarOpen, setSidebarOpen] = React.useState(true)
  const messagesEndRef = React.useRef<HTMLDivElement>(null)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const isEmpty = messages.length === 0

  function createNewConversation() {
    if (activeConvId && messages.length > 0) {
      setConversations((prev) =>
        prev.map((c) => (c.id === activeConvId ? { ...c, messages, updatedAt: new Date() } : c))
      )
    }
    setMessages([])
    setActiveConvId(null)
  }

  function switchConversation(conv: Conversation) {
    if (activeConvId && messages.length > 0) {
      setConversations((prev) =>
        prev.map((c) => (c.id === activeConvId ? { ...c, messages, updatedAt: new Date() } : c))
      )
    }
    setActiveConvId(conv.id)
    setMessages(conv.messages)
  }

  function deleteConversation(id: string) {
    setConversations((prev) => prev.filter((c) => c.id !== id))
    if (activeConvId === id) {
      setActiveConvId(null)
      setMessages([])
    }
  }

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function autoResize() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  async function sendMessage(text?: string) {
    const content = (text || input).trim()
    if (!content) return

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    // Save to conversation list
    if (!activeConvId) {
      const newConv: Conversation = {
        id: Date.now().toString(),
        title: content.slice(0, 30) + (content.length > 30 ? '...' : ''),
        messages: newMessages,
        updatedAt: new Date(),
      }
      setConversations((prev) => [newConv, ...prev])
      setActiveConvId(newConv.id)
    } else {
      setConversations((prev) =>
        prev.map((c) => (c.id === activeConvId ? { ...c, messages: newMessages, updatedAt: new Date() } : c))
      )
    }

    setIsTyping(true)
    await new Promise((r) => setTimeout(r, 1200))
    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: `这是一个模拟回复。在接入 RAG 后，我会基于您上传的文档内容来回答："${content}"`,
      timestamp: new Date(),
    }
    const finalMessages = [...newMessages, assistantMsg]
    setMessages(finalMessages)
    setIsTyping(false)

    setConversations((prev) =>
      prev.map((c) => (c.id === (activeConvId || newMessages[0]?.id) ? { ...c, messages: finalMessages, updatedAt: new Date() } : c))
    )
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex h-[calc(100vh-57px)]">
      <motion.aside
        initial={false}
        animate={{ width: sidebarOpen ? 260 : 0 }}
        transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative shrink-0 overflow-hidden border-r border-border bg-muted/30"
      >
        <div className="flex h-full w-[260px] flex-col">
          <div className="flex items-center justify-between px-3 py-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={createNewConversation}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              新建对话
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground"
              onClick={() => setSidebarOpen(false)}
            >
              <PanelLeftClose className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 pb-3">
            {conversations.length === 0 ? (
              <div className="px-3 py-8 text-center text-xs text-muted-foreground">
                暂无对话记录
              </div>
            ) : (
              <div className="space-y-0.5">
                {conversations.map((conv) => (
                  <div key={conv.id} className="group relative">
                    <button
                      onClick={() => switchConversation(conv)}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition',
                        activeConvId === conv.id
                          ? 'bg-muted font-medium text-foreground'
                          : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                      )}
                    >
                      <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{conv.title}</span>
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          className={cn(
                            'absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition hover:bg-background hover:text-foreground',
                            'opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100'
                          )}
                        >
                          <MoreHorizontal className="h-3.5 w-3.5" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-32">
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onClick={() => deleteConversation(conv.id)}
                        >
                          <Trash2 className="mr-2 h-3.5 w-3.5" />
                          删除对话
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </motion.aside>

      {!sidebarOpen && (
        <Button
          variant="outline"
          size="icon"
          className="absolute left-2 top-[72px] z-10 h-8 w-8"
          onClick={() => setSidebarOpen(true)}
        >
          <PanelLeftOpen className="h-4 w-4" />
        </Button>
      )}

      <div className="flex flex-1 flex-col">
        <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          /* Empty state - Gemini style centered greeting */
          <div className="flex h-full flex-col items-center justify-center px-6">
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5 }}
              className="text-center"
            >
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-violet-500/20">
                <Sparkles className="h-8 w-8 text-primary" />
              </div>
              <h1 className="mt-6 text-2xl font-semibold text-foreground">有什么可以帮您？</h1>
              <p className="mt-2 text-sm text-muted-foreground">基于文档内容的智能问答，支持上下文检索与结构化抽取</p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="mt-8 grid max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2"
            >
              {SUGGESTIONS.map((s, i) => (
                <Button
                  key={i}
                  variant="outline"
                  className="h-auto justify-start rounded-xl px-4 py-3 text-left text-sm font-normal"
                  onClick={() => sendMessage(s)}
                >
                  {s}
                </Button>
              ))}
            </motion.div>
          </div>
        ) : (
          /* Message list */
          <div className="mx-auto max-w-3xl px-6 py-6">
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={cn('mb-6 flex gap-3', msg.role === 'user' && 'justify-end')}
                >
                  {msg.role === 'assistant' && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-white">
                      <Sparkles className="h-4 w-4" />
                    </div>
                  )}
                  <div
                    className={cn(
                      'max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
                      msg.role === 'user'
                        ? 'bg-primary text-white'
                        : 'bg-muted text-foreground'
                    )}
                  >
                    {msg.content}
                  </div>
                  {msg.role === 'user' && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                      <User className="h-4 w-4" />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {isTyping && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mb-6 flex gap-3"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-violet-500 text-white">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div className="rounded-2xl bg-muted px-4 py-3">
                  <div className="flex items-center gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:0ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:150ms]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:300ms]" />
                  </div>
                </div>
              </motion.div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="shrink-0 px-6 py-4">
        <div className="mx-auto max-w-3xl">
          <div className="overflow-hidden rounded-2xl border border-border bg-white shadow-soft transition focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10">
            <div className="flex items-center gap-2 px-4 pt-3">
              <Button variant="outline" size="sm" className="h-7 gap-1.5 rounded-full text-xs">
                <AtSign className="h-3.5 w-3.5" />
                添加上下文
              </Button>
            </div>

            <div className="px-4 py-2">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => { setInput(e.target.value); autoResize() }}
                onKeyDown={handleKeyDown}
                placeholder="提问、搜索或生成任何内容..."
                rows={1}
                className="max-h-[200px] min-h-[36px] w-full resize-none bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
              />
            </div>

            <div className="flex items-center justify-between px-4 pb-3">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground">
                  <Paperclip className="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground">
                  Auto
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs text-muted-foreground">
                  <Globe className="h-3.5 w-3.5" />
                  All Sources
                </Button>
              </div>
              <Button
                size="icon"
                className="h-8 w-8 rounded-full bg-foreground text-white hover:bg-foreground/80"
                disabled={!input.trim()}
                onClick={() => sendMessage()}
              >
                <ArrowUp className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <p className="mt-2 text-center text-xs text-muted-foreground">
            OmniScan 可能会出错，请核实重要信息。
          </p>
        </div>
      </div>
      </div>
    </div>
  )
}
