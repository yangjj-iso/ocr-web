'use client'

import { useEffect, useMemo, useState } from 'react'

import { getArchiveRecords, getBatchEvaluationMetrics } from '@/api/ocr'

const STORAGE_KEYS = {
  latestBatchId: 'ocr:lastBatchId',
  runtimeState: 'ocr:aiRuntimeState',
}

const PASSIVE_RETRY_COOLDOWN_MS = 15000
let passiveRetryAfter = 0
const invalidBatchIds = new Set<string>()

export const AI_ANSWER_SOURCE = {
  RETRIEVAL: 'retrieval',
  MODEL: 'model',
} as const

function isActionableBatchId(batchId = '') {
  return /^batch_/i.test(String(batchId || '').trim())
}

function sanitizeBatchId(batchId = '') {
  const clean = String(batchId || '').trim()
  return isActionableBatchId(clean) ? clean : ''
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function readStorage(key: string, fallback = '') {
  if (!canUseStorage()) return fallback
  try {
    return window.localStorage.getItem(key) || fallback
  } catch (_) {
    return fallback
  }
}

function writeStorage(key: string, value: string) {
  if (!canUseStorage()) return
  try {
    window.localStorage.setItem(key, value)
  } catch (_) {}
}

function readJsonStorage<T extends object>(key: string, fallback: T): T {
  const raw = readStorage(key, '')
  if (!raw) return fallback
  try {
    return { ...fallback, ...JSON.parse(raw) }
  } catch (_) {
    return fallback
  }
}

function extractErrorPayload(error: any) {
  const responseData = error?.response?.data
  if (typeof responseData === 'string') return responseData
  if (typeof responseData?.detail === 'string') return responseData.detail
  return ''
}

function buildCompactErrorText(error: any) {
  return `${extractErrorPayload(error)} ${error?.message || ''}`.replace(/\s+/g, ' ').trim()
}

function isTransientNetworkError(error: any) {
  return /ERR_NETWORK_CHANGED|network\s+error|ERR_NETWORK|Failed to fetch|Network request failed/i.test(
    buildCompactErrorText(error)
  )
}

function isBackendUnavailableError(error: any) {
  const status = Number(error?.response?.status || 0)
  if (status === 502 || status === 503 || status === 504) return true
  return /ECONNREFUSED|ERR_CONNECTION_REFUSED|connection refused|connect ECONNREFUSED|proxy error/i.test(
    buildCompactErrorText(error)
  )
}

function isNoEligibleBatchError(error: any) {
  return (
    Number(error?.response?.status || 0) === 404 &&
    /No eligible completed tasks/i.test(buildCompactErrorText(error))
  )
}

export function getAiAnswerSource(provider?: string) {
  return provider === 'retrieval' ? AI_ANSWER_SOURCE.RETRIEVAL : AI_ANSWER_SOURCE.MODEL
}

export function getAiAnswerSourceLabel(provider?: string) {
  return getAiAnswerSource(provider) === AI_ANSWER_SOURCE.RETRIEVAL
    ? '证据检索结果'
    : '智能生成结果'
}

export function normalizeAiErrorMessage(
  error: any,
  fallback = '智能服务暂未连通，请检查本地模型配置。'
) {
  const compact = buildCompactErrorText(error)
  if (!compact) return fallback

  if (isBackendUnavailableError(error)) return '后端服务暂未启动或尚未就绪，请先启动本地服务。'
  if (isTransientNetworkError(error)) return '网络环境已变化，请稍后重试。'
  if (/<!doctype html|<html/i.test(compact)) return '智能服务正在切换到最新实例，请稍后重试。'
  if (/401|403|api[_ -]?key|authorization|auth|forbidden|unauthorized|minimax/i.test(compact)) {
    return '智能服务暂未连通，请检查本地模型配置。'
  }
  if (/404|No eligible completed tasks/i.test(compact)) {
    return '当前批次暂无可用于智能辅助的已完成材料。'
  }
  if (/timed out|timeout|504/i.test(compact)) return '智能服务响应超时，请稍后重试。'
  if (/outside allowed roots|path/i.test(compact)) {
    return '目录路径未通过校验，请检查高级设置中的路径范围。'
  }
  return compact || fallback
}

export function getStoredLatestBatchId() {
  return sanitizeBatchId(readStorage(STORAGE_KEYS.latestBatchId, ''))
}

export function rememberLatestBatchId(batchId: string) {
  if (!canUseStorage()) return
  const clean = sanitizeBatchId(batchId)
  try {
    if (!clean) {
      window.localStorage.removeItem(STORAGE_KEYS.latestBatchId)
      return
    }
    if (invalidBatchIds.has(clean)) {
      window.localStorage.removeItem(STORAGE_KEYS.latestBatchId)
      return
    }
    window.localStorage.setItem(STORAGE_KEYS.latestBatchId, clean)
  } catch (_) {}
}

type RuntimeState = {
  latestBatchId: string
  aiServiceAvailable: boolean
  answerSource: string
  lastError: string
  updatedAt: string
}

export function rememberAiRuntimeState(partialState: Partial<RuntimeState> = {}) {
  const sanitizedState = Object.fromEntries(
    Object.entries(partialState).filter(([, value]) => value !== undefined)
  ) as Partial<RuntimeState>

  const existing = readJsonStorage<RuntimeState>(STORAGE_KEYS.runtimeState, {
    latestBatchId: '',
    aiServiceAvailable: false,
    answerSource: '',
    lastError: '',
    updatedAt: '',
  })

  const nextState: RuntimeState = {
    ...existing,
    ...sanitizedState,
    updatedAt: new Date().toISOString(),
  }

  if (Object.prototype.hasOwnProperty.call(sanitizedState, 'latestBatchId')) {
    nextState.latestBatchId = sanitizeBatchId(sanitizedState.latestBatchId || '')
  } else {
    nextState.latestBatchId = sanitizeBatchId(existing.latestBatchId)
  }

  rememberLatestBatchId(nextState.latestBatchId)
  writeStorage(STORAGE_KEYS.runtimeState, JSON.stringify(nextState))
}

export type AiCapability = ReturnType<typeof useAiCapabilityState>

export function useAiCapabilityState() {
  const [latestBatchId, setLatestBatchId] = useState('')
  const [aiServiceAvailable, setAiServiceAvailable] = useState(false)
  const [answerSource, setAnswerSource] = useState('')
  const [lastError, setLastError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const stored = readJsonStorage<RuntimeState>(STORAGE_KEYS.runtimeState, {
      latestBatchId: getStoredLatestBatchId(),
      aiServiceAvailable: false,
      answerSource: '',
      lastError: '',
      updatedAt: '',
    })
    setLatestBatchId(sanitizeBatchId(stored.latestBatchId))
    setAiServiceAvailable(Boolean(stored.aiServiceAvailable))
    setAnswerSource(String(stored.answerSource || ''))
    setLastError(String(stored.lastError || ''))
  }, [])

  const hasBatchContext = Boolean(latestBatchId)
  const capabilityStatus: 'no-batch' | 'ready' | 'unavailable' = !hasBatchContext
    ? 'no-batch'
    : aiServiceAvailable
      ? 'ready'
      : 'unavailable'

  const capabilityMessage = useMemo(() => {
    if (capabilityStatus === 'no-batch') {
      return '需先完成一次批量处理，才能使用智能整合、质量概览和批次问答。'
    }
    if (capabilityStatus === 'ready') {
      return '当前批次已具备智能辅助条件，可继续查看整合建议、质量概览和批次问答。'
    }
    return lastError || '智能服务暂未连通，请先检查本地模型配置。'
  }, [capabilityStatus, lastError])

  async function resolveLatestBatchId() {
    const currentStoredBatchId = sanitizeBatchId(latestBatchId)
    try {
      const { data } = await getArchiveRecords({ page: 1, page_size: 200 })
      const records = data?.records || []
      const actionableBatchIds = records
        .map((item: any) => sanitizeBatchId(item.batch_id))
        .filter((id: string) => id && !invalidBatchIds.has(id))

      if (currentStoredBatchId && !invalidBatchIds.has(currentStoredBatchId)) {
        setLatestBatchId(currentStoredBatchId)
        rememberLatestBatchId(currentStoredBatchId)
        return currentStoredBatchId
      }

      const next = actionableBatchIds[0] || ''
      setLatestBatchId(next)
      rememberLatestBatchId(next)
      return next
    } catch (_) {}

    return currentStoredBatchId
  }

  function setBatchContext(batchId: string) {
    const clean = sanitizeBatchId(batchId)
    setLatestBatchId(clean)
    if (clean) invalidBatchIds.delete(clean)
    setAiServiceAvailable(false)
    setLastError('')
    passiveRetryAfter = 0
    rememberAiRuntimeState({
      latestBatchId: clean,
      aiServiceAvailable: false,
      answerSource,
      lastError: '',
    })
  }

  async function refreshAiCapability(
    options: { passive?: boolean; batchId?: string } = {}
  ) {
    const passive = options.passive !== false
    const requestedBatchId = sanitizeBatchId(options.batchId || '')
    if (passive && Date.now() < passiveRetryAfter) return

    if (requestedBatchId) setBatchContext(requestedBatchId)

    setLoading(true)
    const batchId = requestedBatchId || sanitizeBatchId(await resolveLatestBatchId())

    if (!batchId) {
      setAiServiceAvailable(false)
      setLastError('')
      setAnswerSource('')
      rememberAiRuntimeState({
        latestBatchId: '',
        aiServiceAvailable: false,
        answerSource: '',
        lastError: '',
      })
      setLoading(false)
      return
    }

    try {
      const { data } = await getBatchEvaluationMetrics(batchId, { forceRefresh: false })
      if (typeof data === 'string' && /<!doctype html|<html/i.test(data)) {
        throw { response: { data } }
      }
      const validPayload = Boolean(data && typeof data === 'object' && data.batch_id)
      if (!validPayload) throw new Error('Invalid AI capability payload.')

      passiveRetryAfter = 0
      setAiServiceAvailable(true)
      setLastError('')
      rememberAiRuntimeState({
        latestBatchId: batchId,
        aiServiceAvailable: true,
        lastError: '',
      })
    } catch (error: any) {
      if (isNoEligibleBatchError(error)) {
        invalidBatchIds.add(batchId)
        setLatestBatchId('')
        setAiServiceAvailable(false)
        setLastError('')
        setAnswerSource('')
        rememberAiRuntimeState({
          latestBatchId: '',
          aiServiceAvailable: false,
          answerSource: '',
          lastError: '',
        })
        setLoading(false)
        return
      }

      if (passive && (isTransientNetworkError(error) || isBackendUnavailableError(error))) {
        passiveRetryAfter = Date.now() + PASSIVE_RETRY_COOLDOWN_MS
        setAiServiceAvailable(false)
        setLastError('')
        setLoading(false)
        return
      }

      setAiServiceAvailable(false)
      const message = normalizeAiErrorMessage(error)
      setLastError(message)
      rememberAiRuntimeState({
        latestBatchId: batchId,
        aiServiceAvailable: false,
        lastError: message,
      })
    } finally {
      setLoading(false)
    }
  }

  function applyAnswerSource(provider?: string) {
    const source = getAiAnswerSource(provider)
    setAnswerSource(source)
    rememberAiRuntimeState({
      latestBatchId,
      aiServiceAvailable,
      answerSource: source,
      lastError,
    })
  }

  function markAiRuntimeAvailable(batchId?: string) {
    const next = sanitizeBatchId(batchId || latestBatchId || '')
    setLatestBatchId(next)
    if (next) invalidBatchIds.delete(next)
    setAiServiceAvailable(true)
    setLastError('')
    passiveRetryAfter = 0
    rememberAiRuntimeState({
      latestBatchId: next,
      aiServiceAvailable: true,
      answerSource,
      lastError: '',
    })
  }

  function markAiRuntimeUnavailable(batchId: string, error: any) {
    const next = sanitizeBatchId(batchId || latestBatchId || '')
    setLatestBatchId(next)
    setAiServiceAvailable(false)
    const message = normalizeAiErrorMessage(error)
    setLastError(message)
    rememberAiRuntimeState({
      latestBatchId: next,
      aiServiceAvailable: false,
      answerSource,
      lastError: message,
    })
  }

  return {
    loading,
    hasBatchContext,
    latestBatchId,
    aiServiceAvailable,
    answerSource,
    lastError,
    capabilityStatus,
    capabilityMessage,
    setBatchContext,
    refreshAiCapability,
    resolveLatestBatchId,
    applyAnswerSource,
    markAiRuntimeAvailable,
    markAiRuntimeUnavailable,
  }
}
