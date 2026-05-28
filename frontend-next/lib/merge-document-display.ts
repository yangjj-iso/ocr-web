function toArray<T = any>(value: any): T[] {
  return Array.isArray(value) ? value : []
}

function basename(path = '') {
  const normalized = String(path || '').replace(/\\/g, '/')
  const segments = normalized.split('/').filter(Boolean)
  return segments.length ? segments[segments.length - 1] : normalized
}

function stripExtension(filename = '') {
  return String(filename || '').replace(/\.[^.]+$/, '')
}

function extractPageToken(filename = '') {
  const match = String(filename || '').match(/-(\d{3})(?:\.[^.]+)?$/)
  return match ? match[1] : ''
}

function extractSeriesStem(filename = '') {
  return stripExtension(filename).replace(/-\d{3}$/, '')
}

export function buildMergedFileName(filenames: string[] = []) {
  const normalized = toArray<string>(filenames).map(basename).filter(Boolean)
  if (!normalized.length) return '未命名文件'
  if (normalized.length === 1) return normalized[0]

  const first = normalized[0]
  const last = normalized[normalized.length - 1]
  const firstPage = extractPageToken(first)
  const lastPage = extractPageToken(last)
  const stem = extractSeriesStem(first)
  const sameStem = normalized.every((name) => extractSeriesStem(name) === stem)

  if (sameStem && firstPage && lastPage) {
    return `${stem}-${firstPage}-${lastPage}.pdf`
  }

  return `${stripExtension(first)} 等 ${normalized.length} 页`
}

export function buildSourcePageSummary(filenames: string[] = []) {
  const normalized = toArray<string>(filenames).map(basename).filter(Boolean)
  if (!normalized.length) return '暂无来源页'
  if (normalized.length === 1) return normalized[0]

  const pageTokens = normalized.map(extractPageToken)
  if (pageTokens.every(Boolean)) {
    return `来源页 ${pageTokens[0]}-${pageTokens[pageTokens.length - 1]}`
  }

  return `来源材料 ${normalized.length} 份`
}

export function buildSourcePageBadges(filenames: string[] = []) {
  return toArray<string>(filenames)
    .map(basename)
    .filter(Boolean)
    .map((name) => {
      const pageToken = extractPageToken(name)
      return pageToken ? `第 ${pageToken} 页` : name
    })
}

export type MergedDocumentView = ReturnType<typeof buildMergedDocumentViews>[number]

export function buildMergedDocumentViews(result: any) {
  const groups = toArray(result?.groups)
  const documentMap = new Map(
    toArray<any>(result?.documents).map((item) => [item?.group_id, item])
  )

  return groups.map((group: any, index: number) => {
    const filenames = toArray<string>(group?.filenames)
    const taskIds = toArray<any>(group?.task_ids)
    const document = documentMap.get(group?.group_id) || null
    const recommendedFields = document?.recommended_fields || {}
    const title =
      recommendedFields['题名'] ||
      document?.llm_fields?.['题名'] ||
      document?.rule_fields?.['题名'] ||
      ''

    return {
      key: group?.group_id || `group-${index + 1}`,
      index: index + 1,
      groupId: group?.group_id || `group-${index + 1}`,
      displayName: buildMergedFileName(filenames),
      title,
      sourceSummary: buildSourcePageSummary(filenames),
      sourceBadges: buildSourcePageBadges(filenames),
      sourceCount: filenames.length,
      filenames,
      taskIds,
      primaryTaskId: Number(taskIds[0] || 0) || null,
      sameDocumentConfidence: Number(group?.same_document_confidence || 0),
      decisionReasons: toArray<string>(group?.decision_reasons).filter(Boolean),
      mergedPageCount: Number(document?.merged_page_count || filenames.length || 0),
      agreementRatio: Number(document?.agreement?.ratio || 0),
      recommendedFields,
      conflicts: document?.conflicts || {},
      conflictFields: Object.keys(document?.conflicts || {}),
      document,
    }
  })
}
