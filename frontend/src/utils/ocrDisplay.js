const CJK_RE = /[\u3400-\u9fff]/
const LATIN1_RE = /[À-ÿ]/
const MOJIBAKE_HINT_TEST_RE = /(?:Ã.|Â.|â.|ä.|å.|æ.|ç.|è.|é.|ê.|ë.|ì.|í.|î.|ï.|ñ.|ò.|ó.|ô.|õ.|ö.|ù.|ú.|û.|ü.|ý.|ÿ.)/
const MOJIBAKE_HINT_RE = /(?:Ã.|Â.|â.|ä.|å.|æ.|ç.|è.|é.|ê.|ë.|ì.|í.|î.|ï.|ñ.|ò.|ó.|ô.|õ.|ö.|ù.|ú.|û.|ü.|ý.|ÿ.)/g

let utf8Decoder = null

function getUtf8Decoder() {
  if (utf8Decoder !== null) return utf8Decoder
  utf8Decoder = typeof TextDecoder === 'undefined' ? false : new TextDecoder('utf-8', { fatal: false })
  return utf8Decoder
}

function countMatches(value, pattern) {
  return (String(value || '').match(pattern) || []).length
}

function shouldTryRepair(text) {
  if (typeof text !== 'string' || !text.trim()) return false
  if (!LATIN1_RE.test(text)) return false
  return MOJIBAKE_HINT_TEST_RE.test(text) || (!CJK_RE.test(text) && countMatches(text, /[À-ÿ]/g) >= 2)
}

function decodeUtf8Mojibake(text) {
  const decoder = getUtf8Decoder()
  if (!decoder) return text

  try {
    const bytes = Uint8Array.from(Array.from(text), (char) => char.charCodeAt(0) & 0xff)
    return decoder.decode(bytes)
  } catch (_) {
    return text
  }
}

function shouldUseDecodedText(original, decoded) {
  if (!decoded || decoded === original) return false
  if (decoded.includes('\u0000') || decoded.includes('�')) return false

  const originalHasCjk = CJK_RE.test(original)
  const decodedHasCjk = CJK_RE.test(decoded)
  const originalLatin1Count = countMatches(original, /[À-ÿ]/g)
  const decodedLatin1Count = countMatches(decoded, /[À-ÿ]/g)
  const originalHintCount = countMatches(original, MOJIBAKE_HINT_RE)
  const decodedHintCount = countMatches(decoded, MOJIBAKE_HINT_RE)

  if (!originalHasCjk && decodedHasCjk) return true
  if (original.includes('Â·') && decoded.includes('·')) return true
  if (decodedLatin1Count + 1 < originalLatin1Count) return true
  return decodedHintCount + 1 < originalHintCount
}

export function repairRecognitionText(value) {
  if (typeof value !== 'string') return value
  if (!shouldTryRepair(value)) return value

  const decoded = decodeUtf8Mojibake(value)
  return shouldUseDecodedText(value, decoded) ? decoded : value
}

function normalizeLineForDisplay(line) {
  if (!line || typeof line !== 'object') return line
  return {
    ...line,
    text: repairRecognitionText(line.text),
  }
}

function normalizeTableDataForDisplay(tableData) {
  if (!Array.isArray(tableData)) return tableData
  return tableData.map((row) =>
    Array.isArray(row)
      ? row.map((cell) => repairRecognitionText(String(cell ?? '')))
      : [repairRecognitionText(String(row ?? ''))]
  )
}

function normalizeLooseTextTree(value) {
  if (typeof value === 'string') return repairRecognitionText(value)
  if (Array.isArray(value)) return value.map((item) => normalizeLooseTextTree(item))
  if (!value || typeof value !== 'object') return value

  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, normalizeLooseTextTree(item)])
  )
}

function normalizeRegionForDisplay(region) {
  if (!region || typeof region !== 'object') return region
  return {
    ...region,
    content: repairRecognitionText(region.content),
    html: repairRecognitionText(region.html),
    markdown: repairRecognitionText(region.markdown),
    table_data: normalizeTableDataForDisplay(region.table_data),
    region_lines: Array.isArray(region.region_lines)
      ? region.region_lines.map((line) => normalizeLineForDisplay(line))
      : region.region_lines,
    agent_meta: normalizeLooseTextTree(region.agent_meta),
  }
}

export function normalizePagesForDisplay(rawPages) {
  if (!Array.isArray(rawPages)) return []
  return rawPages.map((page) => ({
    ...page,
    regions: Array.isArray(page?.regions) ? page.regions.map((region) => normalizeRegionForDisplay(region)) : [],
    lines: Array.isArray(page?.lines) ? page.lines.map((line) => normalizeLineForDisplay(line)) : [],
    agent_meta: normalizeLooseTextTree(page?.agent_meta),
  }))
}

export function normalizeTaskForDisplay(rawTask) {
  const task = rawTask && typeof rawTask === 'object' ? rawTask : {}
  const rawResultData = task.result_data && typeof task.result_data === 'object' ? task.result_data : {}
  const rawPages = Array.isArray(rawResultData.pages)
    ? rawResultData.pages
    : Array.isArray(task.result_json)
      ? task.result_json
      : []
  const pages = normalizePagesForDisplay(rawPages)

  return {
    ...task,
    filename: repairRecognitionText(task.filename),
    full_text: repairRecognitionText(task.full_text),
    error_message: repairRecognitionText(task.error_message),
    result_json: pages,
    result_data: {
      ...rawResultData,
      pages,
      agent_meta: normalizeLooseTextTree(rawResultData.agent_meta),
    },
    agent_meta: normalizeLooseTextTree(task.agent_meta),
  }
}
