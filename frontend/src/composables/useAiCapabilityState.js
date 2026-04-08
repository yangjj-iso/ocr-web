import { computed, ref } from 'vue'

import { getArchiveRecords, getBatchEvaluationMetrics } from '../api/ocr.js'

const STORAGE_KEYS = {
  latestBatchId: 'ocr:lastBatchId',
  runtimeState: 'ocr:aiRuntimeState',
}

const PASSIVE_RETRY_COOLDOWN_MS = 15000
let passiveRetryAfter = 0
const invalidBatchIds = new Set()

export const AI_ANSWER_SOURCE = {
  RETRIEVAL: 'retrieval',
  MODEL: 'model',
}

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

function readStorage(key, fallback = '') {
  if (!canUseStorage()) return fallback
  try {
    return window.localStorage.getItem(key) || fallback
  } catch (_) {
    return fallback
  }
}

function writeStorage(key, value) {
  if (!canUseStorage()) return
  try {
    window.localStorage.setItem(key, value)
  } catch (_) {}
}

function readJsonStorage(key, fallback) {
  const raw = readStorage(key, '')
  if (!raw) return fallback
  try {
    return { ...fallback, ...JSON.parse(raw) }
  } catch (_) {
    return fallback
  }
}

function extractErrorPayload(error) {
  const responseData = error?.response?.data
  if (typeof responseData === 'string') {
    return responseData
  }
  if (typeof responseData?.detail === 'string') {
    return responseData.detail
  }
  return ''
}

function buildCompactErrorText(error) {
  return `${extractErrorPayload(error)} ${error?.message || ''}`.replace(/\s+/g, ' ').trim()
}

function isTransientNetworkError(error) {
  return /ERR_NETWORK_CHANGED|network\s+error|ERR_NETWORK|Failed to fetch|Network request failed/i.test(
    buildCompactErrorText(error)
  )
}

function isBackendUnavailableError(error) {
  const status = Number(error?.response?.status || 0)
  if (status === 502 || status === 503 || status === 504) {
    return true
  }
  return /ECONNREFUSED|ERR_CONNECTION_REFUSED|connection refused|connect ECONNREFUSED|proxy error/i.test(
    buildCompactErrorText(error)
  )
}

function isNoEligibleBatchError(error) {
  return Number(error?.response?.status || 0) === 404 &&
    /No eligible completed tasks/i.test(buildCompactErrorText(error))
}

export function getAiAnswerSource(provider) {
  return provider === 'retrieval' ? AI_ANSWER_SOURCE.RETRIEVAL : AI_ANSWER_SOURCE.MODEL
}

export function getAiAnswerSourceLabel(provider) {
  return getAiAnswerSource(provider) === AI_ANSWER_SOURCE.RETRIEVAL ? '证据检索结果' : '智能生成结果'
}

export function normalizeAiErrorMessage(
  error,
  fallback = '智能服务暂未连通，请检查本地模型配置。'
) {
  const compact = buildCompactErrorText(error)
  if (!compact) {
    return fallback
  }

  if (isBackendUnavailableError(error)) {
    return '后端服务暂未启动或尚未就绪，请先启动本地服务。'
  }

  if (isTransientNetworkError(error)) {
    return '网络环境已变化，请稍后重试。'
  }

  if (/<!doctype html|<html/i.test(compact)) {
    return '智能服务正在切换到最新实例，请稍后重试。'
  }

  if (/401|403|api[_ -]?key|authorization|auth|forbidden|unauthorized|minimax/i.test(compact)) {
    return '智能服务暂未连通，请检查本地模型配置。'
  }

  if (/404|No eligible completed tasks/i.test(compact)) {
    return '当前批次暂无可用于智能辅助的已完成材料。'
  }

  if (/timed out|timeout|504/i.test(compact)) {
    return '智能服务响应超时，请稍后重试。'
  }

  if (/outside allowed roots|path/i.test(compact)) {
    return '目录路径未通过校验，请检查高级设置中的路径范围。'
  }

  return compact || fallback
}

export function getStoredLatestBatchId() {
  return sanitizeBatchId(readStorage(STORAGE_KEYS.latestBatchId, ''))
}

export function rememberLatestBatchId(batchId) {
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

export function rememberAiRuntimeState(partialState = {}) {
  const sanitizedState = Object.fromEntries(
    Object.entries(partialState).filter(([, value]) => value !== undefined)
  )
  const existing = readJsonStorage(STORAGE_KEYS.runtimeState, {
    latestBatchId: '',
    aiServiceAvailable: false,
    answerSource: '',
    lastError: '',
    updatedAt: '',
  })

  const nextState = {
    ...existing,
    ...sanitizedState,
    updatedAt: new Date().toISOString(),
  }

  if (Object.prototype.hasOwnProperty.call(sanitizedState, 'latestBatchId')) {
    nextState.latestBatchId = sanitizeBatchId(sanitizedState.latestBatchId)
  } else {
    nextState.latestBatchId = sanitizeBatchId(existing.latestBatchId)
  }

  rememberLatestBatchId(nextState.latestBatchId)
  writeStorage(STORAGE_KEYS.runtimeState, JSON.stringify(nextState))
}

export function useAiCapabilityState() {
  const storedState = readJsonStorage(STORAGE_KEYS.runtimeState, {
    latestBatchId: getStoredLatestBatchId(),
    aiServiceAvailable: false,
    answerSource: '',
    lastError: '',
    updatedAt: '',
  })

  const loading = ref(false)
  const latestBatchId = ref(sanitizeBatchId(storedState.latestBatchId || ''))
  const aiServiceAvailable = ref(Boolean(storedState.aiServiceAvailable))
  const answerSource = ref(String(storedState.answerSource || ''))
  const lastError = ref(String(storedState.lastError || ''))

  const hasBatchContext = computed(() => Boolean(latestBatchId.value))
  const capabilityStatus = computed(() => {
    if (!hasBatchContext.value) return 'no-batch'
    return aiServiceAvailable.value ? 'ready' : 'unavailable'
  })

  const capabilityMessage = computed(() => {
    if (capabilityStatus.value === 'no-batch') {
      return '需先完成一次批量处理，才能使用智能整合、质量概览和批次问答。'
    }
    if (capabilityStatus.value === 'ready') {
      return '当前批次已具备智能辅助条件，可继续查看整合建议、质量概览和批次问答。'
    }
    return lastError.value || '智能服务暂未连通，请先检查本地模型配置。'
  })

  async function resolveLatestBatchId() {
    const currentStoredBatchId = sanitizeBatchId(latestBatchId.value)
    try {
      const { data } = await getArchiveRecords({ page: 1, page_size: 200 })
      const records = data?.records || []
      const actionableBatchIds = records
        .map((item) => sanitizeBatchId(item.batch_id))
        .filter((id) => id && !invalidBatchIds.has(id))

      if (currentStoredBatchId && !invalidBatchIds.has(currentStoredBatchId)) {
        latestBatchId.value = currentStoredBatchId
        rememberLatestBatchId(latestBatchId.value)
        return latestBatchId.value
      }

      latestBatchId.value = actionableBatchIds[0] || ''
      rememberLatestBatchId(latestBatchId.value)
      return latestBatchId.value
    } catch (_) {}

    return currentStoredBatchId
  }

  function setBatchContext(batchId) {
    latestBatchId.value = sanitizeBatchId(batchId)
    if (latestBatchId.value) {
      invalidBatchIds.delete(latestBatchId.value)
    }
    aiServiceAvailable.value = false
    lastError.value = ''
    passiveRetryAfter = 0
    rememberAiRuntimeState({
      latestBatchId: latestBatchId.value,
      aiServiceAvailable: false,
      answerSource: answerSource.value,
      lastError: '',
    })
  }

  async function refreshAiCapability(options = {}) {
    const passive = options.passive !== false
    const requestedBatchId = sanitizeBatchId(options.batchId || '')
    if (passive && Date.now() < passiveRetryAfter) {
      return
    }

    if (requestedBatchId) {
      setBatchContext(requestedBatchId)
    }

    loading.value = true
    const batchId = requestedBatchId || sanitizeBatchId(await resolveLatestBatchId())

    if (!batchId) {
      aiServiceAvailable.value = false
      lastError.value = ''
      answerSource.value = ''
      rememberAiRuntimeState({
        latestBatchId: '',
        aiServiceAvailable: false,
        answerSource: '',
        lastError: '',
      })
      loading.value = false
      return
    }

    try {
      const { data } = await getBatchEvaluationMetrics(batchId, { forceRefresh: false })
      if (typeof data === 'string' && /<!doctype html|<html/i.test(data)) {
        throw { response: { data } }
      }
      const validPayload = Boolean(data && typeof data === 'object' && data.batch_id)
      if (!validPayload) {
        throw new Error('Invalid AI capability payload.')
      }

      passiveRetryAfter = 0
      aiServiceAvailable.value = true
      lastError.value = ''
      rememberAiRuntimeState({
        latestBatchId: batchId,
        aiServiceAvailable: true,
        lastError: '',
      })
    } catch (error) {
      if (isNoEligibleBatchError(error)) {
        invalidBatchIds.add(batchId)
        latestBatchId.value = ''
        aiServiceAvailable.value = false
        lastError.value = ''
        answerSource.value = ''
        rememberAiRuntimeState({
          latestBatchId: '',
          aiServiceAvailable: false,
          answerSource: '',
          lastError: '',
        })
        loading.value = false
        return
      }

      if (passive && (isTransientNetworkError(error) || isBackendUnavailableError(error))) {
        passiveRetryAfter = Date.now() + PASSIVE_RETRY_COOLDOWN_MS
        aiServiceAvailable.value = false
        lastError.value = ''
        loading.value = false
        return
      }

      aiServiceAvailable.value = false
      lastError.value = normalizeAiErrorMessage(error)
      rememberAiRuntimeState({
        latestBatchId: batchId,
        aiServiceAvailable: false,
        lastError: lastError.value,
      })
    } finally {
      loading.value = false
    }
  }

  function applyAnswerSource(provider) {
    answerSource.value = getAiAnswerSource(provider)
    rememberAiRuntimeState({
      latestBatchId: latestBatchId.value,
      aiServiceAvailable: aiServiceAvailable.value,
      answerSource: answerSource.value,
      lastError: lastError.value,
    })
  }

  function markAiRuntimeAvailable(batchId) {
    latestBatchId.value = sanitizeBatchId(batchId || latestBatchId.value || '')
    if (latestBatchId.value) {
      invalidBatchIds.delete(latestBatchId.value)
    }
    aiServiceAvailable.value = true
    lastError.value = ''
    passiveRetryAfter = 0
    rememberAiRuntimeState({
      latestBatchId: latestBatchId.value,
      aiServiceAvailable: true,
      answerSource: answerSource.value,
      lastError: '',
    })
  }

  function markAiRuntimeUnavailable(batchId, error) {
    latestBatchId.value = sanitizeBatchId(batchId || latestBatchId.value || '')
    aiServiceAvailable.value = false
    lastError.value = normalizeAiErrorMessage(error)
    rememberAiRuntimeState({
      latestBatchId: latestBatchId.value,
      aiServiceAvailable: false,
      answerSource: answerSource.value,
      lastError: lastError.value,
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
    applyAnswerSource,
    markAiRuntimeAvailable,
    markAiRuntimeUnavailable,
    resolveLatestBatchId,
  }
}
