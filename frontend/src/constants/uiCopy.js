export const VIEW_MODE = {
  DEFAULT: 'default',
  ADVANCED: 'advanced',
}

export const UI_COPY_POLICY = {
  assistantLabel: '智能辅助',
  advancedLabel: '高级设置',
}

const MODE_META = {
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

const STATUS_META = {
  done: {
    label: '已完成',
    className: 'bg-green-100 text-green-700',
  },
  failed: {
    label: '处理异常',
    className: 'bg-red-100 text-red-700',
  },
  processing: {
    label: '处理中',
    className: 'bg-amber-100 text-amber-700',
  },
  pending: {
    label: '排队中',
    className: 'bg-slate-100 text-slate-600',
  },
}

export const RESULT_TAB_LABELS = {
  parsed: '识别结果',
  json: '结构数据',
}

export function getModeMeta(mode) {
  return MODE_META[mode] || {
    title: '档案识别',
    shortLabel: '档案识别',
    description: '适合常规档案材料处理。',
    badge: '',
  }
}

export function getModeLabel(mode) {
  return getModeMeta(mode).shortLabel
}

export function getStatusMeta(status) {
  return STATUS_META[status] || {
    label: status || '未知状态',
    className: 'bg-slate-100 text-slate-600',
  }
}

export function getStatusLabel(status) {
  return getStatusMeta(status).label
}

export function getStatusClass(status) {
  return getStatusMeta(status).className
}
