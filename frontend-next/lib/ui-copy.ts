export const VIEW_MODE = {
  DEFAULT: 'default',
  ADVANCED: 'advanced',
} as const

export const UI_COPY_POLICY = {
  assistantLabel: '智能辅助',
  advancedLabel: '高级设置',
}

type ModeMeta = {
  title: string
  shortLabel: string
  description: string
  badge: string
}

const MODE_META: Record<string, ModeMeta> = {
  baidu_vl: {
    title: '综合识别',
    shortLabel: '综合识别',
    description: '适合复杂版式档案材料，支持印章、表格、公式等多要素识别。',
    badge: '推荐',
  },
  vl: {
    title: '综合识别',
    shortLabel: '综合识别',
    description: '适合复杂版式档案材料，支持印章、表格、公式等多要素识别。',
    badge: '推荐',
  },
  layout: {
    title: '版式识别',
    shortLabel: '版式识别',
    description: '适合表格、图文混排和结构信息较强的档案材料。',
    badge: '',
  },
  ocr: {
    title: '文本识别',
    shortLabel: '文本识别',
    description: '适合常规文字材料的快速处理与基础核验。',
    badge: '快速',
  },
}

type StatusMeta = {
  label: string
  className: string
}

const STATUS_META: Record<string, StatusMeta> = {
  done: { label: '已完成', className: 'bg-emerald-100 text-emerald-700' },
  failed: { label: '处理异常', className: 'bg-red-100 text-red-700' },
  human_review: { label: '待人工复核', className: 'bg-violet-100 text-violet-700' },
  processing: { label: '处理中', className: 'bg-amber-100 text-amber-700' },
  pending: { label: '排队中', className: 'bg-slate-100 text-slate-600' },
}

export const RESULT_TAB_LABELS = {
  parsed: '识别结果',
  json: '结构数据',
}

export function getModeMeta(mode: string): ModeMeta {
  return (
    MODE_META[mode] || {
      title: '档案识别',
      shortLabel: '档案识别',
      description: '适合常规档案材料处理。',
      badge: '',
    }
  )
}

export function getModeLabel(mode: string) {
  return getModeMeta(mode).shortLabel
}

export function getStatusMeta(status: string): StatusMeta {
  return (
    STATUS_META[status] || {
      label: status || '未知状态',
      className: 'bg-slate-100 text-slate-600',
    }
  )
}

export function getStatusLabel(status: string) {
  return getStatusMeta(status).label
}

export function getStatusClass(status: string) {
  return getStatusMeta(status).className
}
