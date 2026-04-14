<template>
  <div class="flex h-full flex-col bg-white">
    <!-- Toolbar -->
    <div class="flex items-center gap-2 border-b border-[var(--gov-border)] px-3 py-2">
      <button
        :disabled="currentPage <= 1"
        class="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-40"
        @click="prevPage"
        title="上一页"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
        </svg>
      </button>
      <span class="text-xs text-slate-600">{{ currentPage }} / {{ numPages }}</span>
      <button
        :disabled="currentPage >= numPages"
        class="rounded p-1 text-slate-500 hover:bg-slate-100 disabled:opacity-40"
        @click="nextPage"
        title="下一页"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
      </button>
      <div class="flex-1" />
      <button class="rounded p-1 text-slate-500 hover:bg-slate-100" @click="zoom(-0.2)" title="缩小">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM13.5 10.5h-6"/></svg>
      </button>
      <span class="text-xs text-slate-600">{{ Math.round(scale * 100) }}%</span>
      <button class="rounded p-1 text-slate-500 hover:bg-slate-100" @click="zoom(0.2)" title="放大">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6"/></svg>
      </button>
    </div>

    <!-- Canvas area -->
    <div ref="container" class="flex-1 overflow-auto bg-slate-100">
      <div class="flex min-h-full items-start justify-center p-4">
        <canvas ref="canvas" class="shadow-lg" />
      </div>
    </div>

    <!-- Loading overlay -->
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center bg-white/80">
      <svg class="h-8 w-8 animate-spin text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
      </svg>
    </div>

    <div v-if="!src && !loading" class="absolute inset-0 flex items-center justify-center">
      <p class="text-sm text-slate-400">暂无预览</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'

const props = defineProps({
  src: { type: String, default: null }, // PDF URL
  page: { type: Number, default: 1 },   // initial page to show
})

const emit = defineEmits(['page-change', 'loaded', 'load-error'])

const canvas = ref(null)
const container = ref(null)
const currentPage = ref(props.page || 1)
const numPages = ref(0)
const scale = ref(1.2)
const loading = ref(false)

let pdfDoc = null
let renderTask = null

async function loadPdf(url) {
  if (!url) return
  loading.value = true
  try {
    const pdfjsLib = await import('pdfjs-dist')
    pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs',
      import.meta.url
    ).toString()
    pdfDoc = await pdfjsLib.getDocument({ url, withCredentials: true }).promise
    numPages.value = pdfDoc.numPages
    emit('loaded', pdfDoc.numPages)
    await renderPage(currentPage.value)
  } catch (e) {
    console.error('PdfViewer load error', e)
    emit('load-error', e)
  } finally {
    loading.value = false
  }
}

async function renderPage(pageNum) {
  if (!pdfDoc || !canvas.value) return
  if (renderTask) { renderTask.cancel(); renderTask = null }
  loading.value = true
  try {
    const page = await pdfDoc.getPage(pageNum)
    const viewport = page.getViewport({ scale: scale.value })
    canvas.value.width = viewport.width
    canvas.value.height = viewport.height
    const ctx = canvas.value.getContext('2d')
    renderTask = page.render({ canvasContext: ctx, viewport })
    await renderTask.promise
    emit('page-change', pageNum)
  } catch (e) {
    if (e?.name !== 'RenderingCancelledException') console.error(e)
  } finally {
    loading.value = false
    renderTask = null
  }
}

function prevPage() {
  if (currentPage.value > 1) { currentPage.value--; renderPage(currentPage.value) }
}
function nextPage() {
  if (currentPage.value < numPages.value) { currentPage.value++; renderPage(currentPage.value) }
}
function zoom(delta) {
  scale.value = Math.max(0.4, Math.min(3, scale.value + delta))
  renderPage(currentPage.value)
}

watch(() => props.src, (url) => { loadPdf(url) })
watch(() => props.page, (p) => { if (p !== currentPage.value) { currentPage.value = p; renderPage(p) } })

onMounted(() => { if (props.src) loadPdf(props.src) })
</script>
