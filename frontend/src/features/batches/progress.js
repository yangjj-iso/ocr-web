const ACTIVE_BATCH_STATUSES = new Set(['processing', 'review_required'])
const IN_FLIGHT_RUN_STATUSES = new Set(['processing', 'running', 'blocked'])
const TERMINAL_BATCH_STATUSES = new Set(['done', 'failed'])
const MIN_ACTIVE_STAGE_PROGRESS = 0.1

function normalizeStatus(value) {
  return String(value || '').trim().toLowerCase()
}

function clampRatio(value) {
  if (!Number.isFinite(value)) return 0
  if (value <= 0) return 0
  if (value >= 1) return 1
  return value
}

function parseStageRatio(count) {
  if (typeof count !== 'string') return null
  const match = count.match(/^\s*(\d+)\s*\/\s*(\d+)\s*$/)
  if (!match) return null
  const completed = Number(match[1])
  const total = Number(match[2])
  if (!Number.isFinite(total) || total <= 0) return null
  return clampRatio(completed / total)
}

function stageFraction(stage, batch) {
  const status = normalizeStatus(stage?.status)
  const ratio = parseStageRatio(stage?.count)
  if (ratio != null) {
    return status === 'processing' ? Math.max(ratio, MIN_ACTIVE_STAGE_PROGRESS) : ratio
  }

  if (stage?.name === 'final') {
    const totalDocs = Number(batch?.total_docs || 0)
    const doneDocs = Number(batch?.done_docs || 0)
    if (totalDocs > 0) {
      const finalRatio = clampRatio(doneDocs / totalDocs)
      return status === 'processing' ? Math.max(finalRatio, MIN_ACTIVE_STAGE_PROGRESS) : finalRatio
    }
  }

  if (status === 'done') return 1
  if (status === 'failed') return 0.5
  if (status === 'processing') return 0.5
  return 0
}

function isStageTouched(stage, batch) {
  const status = normalizeStatus(stage?.status)
  if (['done', 'processing', 'failed'].includes(status)) return true
  const ratio = parseStageRatio(stage?.count)
  if (ratio != null) return ratio > 0
  if (stage?.name === 'final') {
    return Number(batch?.done_docs || 0) > 0
  }
  return false
}

export function isBatchAutoRefreshable(batch) {
  const status = normalizeStatus(batch?.status)
  const runStatus = normalizeStatus(batch?.run_status)
  return ACTIVE_BATCH_STATUSES.has(status)
    || IN_FLIGHT_RUN_STATUSES.has(runStatus)
    || Boolean(batch?.current_stage && !TERMINAL_BATCH_STATUSES.has(status))
}

export function getBatchProgressPercent(batch) {
  const status = normalizeStatus(batch?.status)
  if (!batch) return 0
  if (status === 'done') return 100

  const stages = Array.isArray(batch.workflow_stages) ? batch.workflow_stages.filter(Boolean) : []
  const neverStarted = ['draft', 'pending', 'created'].includes(status)
    && !batch?.current_stage
    && !normalizeStatus(batch?.run_status)
  if (neverStarted) return 0

  if (!stages.length) {
    const totalDocs = Number(batch?.total_docs || 0)
    if (totalDocs > 0) {
      return Math.round(clampRatio(Number(batch?.done_docs || 0) / totalDocs) * 100)
    }
    return isBatchAutoRefreshable(batch) ? 10 : 0
  }

  const lastTouchedIndex = stages.reduce((index, stage, currentIndex) => {
    return isStageTouched(stage, batch) ? currentIndex : index
  }, -1)

  const normalizedFractions = stages.map((stage, index) => {
    const fraction = stageFraction(stage, batch)
    if (fraction <= 0 && index < lastTouchedIndex) {
      return 1
    }
    return fraction
  })

  const total = normalizedFractions.reduce((sum, fraction) => sum + fraction, 0)
  return Math.round(clampRatio(total / normalizedFractions.length) * 100)
}

export function getBatchProgressSummary(batch) {
  const stages = Array.isArray(batch?.workflow_stages) ? batch.workflow_stages.filter(Boolean) : []
  if (!stages.length) return ''
  const activeStage = stages.find((stage) => normalizeStatus(stage?.status) === 'processing')
  if (activeStage) {
    return activeStage.count ? `${activeStage.label} ${activeStage.count}` : activeStage.label
  }
  const failedStage = stages.find((stage) => normalizeStatus(stage?.status) === 'failed')
  if (failedStage) {
    return failedStage.count ? `${failedStage.label} 失败于 ${failedStage.count}` : `${failedStage.label} 失败`
  }
  const latestDoneStage = [...stages].reverse().find((stage) => normalizeStatus(stage?.status) === 'done')
  if (latestDoneStage) {
    return latestDoneStage.count ? `${latestDoneStage.label} ${latestDoneStage.count}` : latestDoneStage.label
  }
  return ''
}

export function formatRefreshTime(value) {
  if (!value) return ''
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}