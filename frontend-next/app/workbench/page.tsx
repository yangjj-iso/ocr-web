'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  FileText,
  History,
  Layers,
  Loader2,
  Sparkles,
  Upload,
} from 'lucide-react'

import { BufferZone } from '@/components/buffer-zone'
import { HistoryList, HistoryListHandle } from '@/components/history-list'
import { useAiCapabilityState } from '@/hooks/use-ai-capability-state'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

const STEPS = [
  { id: 'upload', label: '导入材料', icon: Upload },
  { id: 'process', label: '识别处理', icon: Loader2 },
  { id: 'result', label: '查看结果', icon: CheckCircle2 },
]

const MODEL_CONFIG = { mode: 'ocr', name: 'OCR 识别', desc: '文档数字化识别' }

export default function WorkbenchPage() {
  const router = useRouter()
  const historyRef = React.useRef<HistoryListHandle>(null)
  const aiCapability = useAiCapabilityState()
  const [showHistory, setShowHistory] = React.useState(false)
  const [currentStep, setCurrentStep] = React.useState(0)

  function handleStartBatch() {
    setCurrentStep(1)
  }

  function handleBatchCompleted(payload: any) {
    setCurrentStep(2)
    if (payload?.batchId) {
      aiCapability.setBatchContext(payload.batchId)
      aiCapability.refreshAiCapability({ batchId: payload.batchId })
    }
    historyRef.current?.refresh()
  }

  function handleViewResult(payload: any) {
    if (!payload?.taskId) return
    const params = new URLSearchParams()
    if (payload.folder) params.set('folder', payload.folder)
    if (payload.submissionId) params.set('submission_id', payload.submissionId)
    if (payload.batchId) params.set('batch_id', payload.batchId)
    const qs = params.toString()
    router.push(`/result/${payload.taskId}${qs ? `?${qs}` : ''}`)
  }

  function handleHistoryBatchContext(payload: any) {
    if (payload?.batchId) aiCapability.setBatchContext(payload.batchId)
  }

  return (
    <div className="flex h-[calc(100vh-57px)] flex-col">
      {/* Step indicator */}
      <div className="border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-center gap-0 px-6 py-4">
          {STEPS.map((step, i) => {
            const Icon = step.icon
            const isActive = i === currentStep
            const isDone = i < currentStep
            return (
              <React.Fragment key={step.id}>
                {i > 0 && (
                  <div className="mx-3 flex items-center">
                    <div className={`h-px w-10 transition-colors duration-300 ${isDone ? 'bg-primary' : 'bg-border'}`} />
                  </div>
                )}
                <button
                  onClick={() => { if (isDone) setCurrentStep(i) }}
                  className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-all duration-300 ${
                    isActive
                      ? 'bg-primary text-white shadow-md shadow-primary/25'
                      : isDone
                        ? 'cursor-pointer bg-primary/10 text-primary hover:bg-primary/15'
                        : 'cursor-default text-muted-foreground'
                  }`}
                >
                  {isDone ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <Icon className={`h-4 w-4 ${isActive && step.id === 'process' ? 'animate-spin' : ''}`} />
                  )}
                  {step.label}
                </button>
              </React.Fragment>
            )
          })}
        </div>
      </div>

      {/* Main content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-6 py-8">
          {/* BufferZone handles all upload/process/result states internally */}
          <BufferZone
            model={MODEL_CONFIG}
            onStartBatch={handleStartBatch}
            onBatchCompleted={handleBatchCompleted}
            onViewResult={(payload) => handleViewResult(payload)}
          />

          {/* History toggle */}
          <div className="mt-8">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="group flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground"
            >
              <History className="h-4 w-4" />
              <span>历史处理记录</span>
              <motion.div animate={{ rotate: showHistory ? 90 : 0 }} transition={{ duration: 0.2 }}>
                <ArrowRight className="h-3.5 w-3.5" />
              </motion.div>
            </button>

            <AnimatePresence>
              {showHistory && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.25 }}
                  className="overflow-hidden"
                >
                  <div className="pt-4">
                    <HistoryList
                      ref={historyRef}
                      onViewResult={handleViewResult}
                      onBatchContext={handleHistoryBatchContext}
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}
