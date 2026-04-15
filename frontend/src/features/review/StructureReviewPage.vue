<template>
  <AppShell>
    <template #review-toolbar>
      <div class="flex items-center gap-3">
        <span class="font-mono text-xs text-[var(--gov-text-muted)]">#{{ taskId }}</span>
        <StatusBadge :status="task?.status" />
        <span class="text-[11px] font-semibold text-[var(--gov-primary)]">结构审核</span>
        <!-- Progress -->
        <div class="hidden sm:flex items-center gap-2 ml-2">
          <div class="w-24 h-1.5 rounded-full bg-slate-200 overflow-hidden">
            <div class="h-full rounded-full bg-[var(--gov-primary)] transition-all duration-300" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <span class="text-[11px] tabular-nums text-[var(--gov-text-muted)]">{{ confirmedCount }}/{{ docs.length }}</span>
        </div>
        <div class="ml-auto flex items-center gap-2">
          <span v-if="refreshStatusText" class="hidden lg:inline">{{ refreshStatusText }}</span>
          <button @click="handleManualRefresh" :disabled="refreshing" class="h-8 rounded-md border border-[var(--gov-border)] px-3 text-[11px] text-[var(--gov-text-muted)] hover:bg-slate-50 disabled:opacity-50">
            {{ refreshing ? '刷新中...' : '刷新' }}
          </button>
        </div>
        <div class="hidden md:inline-flex items-center gap-1.5 text-[11px] text-[var(--gov-text-muted)]">
          <span class="gov-kbd">&uarr;</span><span class="gov-kbd">&darr;</span> 切换件
          <span class="gov-kbd ml-1">Space</span> 确认
          <span class="gov-kbd ml-1">Enter</span> 提交
        </div>
      </div>
    </template>

    <div class="box-border h-[calc(100vh-3rem)] min-w-0 overflow-hidden bg-[#f4f7fb] p-3">
      <!-- Loading / error -->
      <div v-if="loadError" class="w-full flex items-center justify-center p-8">
        <div class="max-w-sm rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-center">
          <p class="text-sm text-red-700">{{ loadError }}</p>
          <button class="mt-3 text-xs font-medium text-red-600 hover:underline" @click="$router.back()">返回</button>
        </div>
      </div>

      <!-- Left: doc list -->
      <div v-if="!loadError" class="h-full min-h-0 overflow-x-auto overflow-y-hidden">
      <div class="flex h-full min-h-0 w-max items-stretch gap-3">
      <aside class="w-[184px] xl:w-[208px] border border-slate-200 bg-white flex flex-col flex-shrink-0 overflow-hidden min-h-0">
        <div class="px-3 py-3 border-b border-[var(--gov-border)]">
          <p class="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">Material Queue</p>
          <div class="mt-1 flex items-center justify-between">
            <span class="text-sm font-semibold text-[var(--gov-text)]">材料分件</span>
            <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">共 {{ docs.length }} 件</span>
          </div>
          <div class="flex items-center gap-2">
            <span v-if="needAttentionCount > 0" class="text-[10px] font-semibold text-amber-600 bg-amber-50 rounded px-1.5 py-0.5">
              {{ needAttentionCount }} 需关注
            </span>
            <span v-else-if="docs.length > 0" class="text-[10px] font-semibold text-green-600 bg-green-50 rounded px-1.5 py-0.5">
              全部正常
            </span>
          </div>
        </div>

        <!-- Batch confirm -->
        <div v-if="hasUnconfirmedSafe" class="px-3 py-2 border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)]">
          <button @click="confirmAllSafe"
            class="w-full h-7 text-[11px] font-medium rounded-md border border-green-300 text-green-700 bg-green-50 hover:bg-green-100 transition-colors flex items-center justify-center gap-1.5">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            确认所有低风险件
          </button>
        </div>

        <!-- Draggable doc list -->
        <div class="flex-1 overflow-y-auto py-1" ref="docListRef">
          <div
            v-for="(doc, idx) in docs"
            :key="doc.id || doc.doc_id || idx"
            class="group w-full flex items-center gap-2 px-3 py-2.5 text-left transition-all cursor-pointer select-none border-l-2"
            :class="[
              selectedIdx === idx
                ? 'bg-[var(--gov-primary-soft)] border-l-[var(--gov-primary)]'
                : doc._confirmed
                  ? 'border-l-green-400 bg-green-50/30 hover:bg-green-50/60'
                  : 'border-l-transparent hover:bg-slate-50',
              dragOverIdx === idx ? 'ring-2 ring-[var(--gov-primary)]/30 ring-inset' : ''
            ]"
            :draggable="true"
            @dragstart="onDragStart(idx, $event)"
            @dragover.prevent="dragOverIdx = idx"
            @dragleave="dragOverIdx = -1"
            @drop="onDrop(idx)"
            @click="selectDoc(idx)"
          >
            <!-- Confirmed check or sequence -->
            <span v-if="doc._confirmed" class="flex-shrink-0 w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
              <svg class="h-3 w-3 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>
            </span>
            <span v-else class="flex-shrink-0 w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold" :class="docSeqClass(doc)">
              {{ idx + 1 }}
            </span>

            <div class="min-w-0 flex-1">
              <p class="text-xs font-medium text-[var(--gov-text)] truncate leading-tight">{{ doc.title || doc.name || `件 ${idx + 1}` }}</p>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-[10px] text-[var(--gov-text-muted)] tabular-nums">第{{ doc.start_page ?? '?' }}–{{ doc.end_page ?? '?' }}页</span>
                <span v-if="docConfidence(doc) != null" class="text-[10px] font-semibold tabular-nums" :class="confColor(docConfidence(doc))">
                  {{ (docConfidence(doc) * 100).toFixed(0) }}%
                </span>
              </div>
            </div>

            <span class="flex-shrink-0 text-slate-300 group-hover:text-slate-400 cursor-grab opacity-0 group-hover:opacity-100 transition-opacity">
              <svg class="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 16 16"><circle cx="5" cy="3" r="1.2"/><circle cx="11" cy="3" r="1.2"/><circle cx="5" cy="8" r="1.2"/><circle cx="11" cy="8" r="1.2"/><circle cx="5" cy="13" r="1.2"/><circle cx="11" cy="13" r="1.2"/></svg>
            </span>

            <span v-if="doc.risk_level && doc.risk_level !== 'none'" class="flex-shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold"
              :class="riskTagClass(doc.risk_level)">
              {{ doc.risk_level === 'high' ? '高' : '中' }}
            </span>
          </div>
        </div>

        <!-- Structure operations -->
        <div class="border-t border-[var(--gov-border)] flex-shrink-0">
          <div class="px-2 py-2 grid grid-cols-2 gap-1.5">
            <button @click="mergeWithPrev" :disabled="selectedIdx <= 0"
              class="flex items-center justify-center gap-1 h-8 text-[11px] font-medium rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] bg-white hover:bg-slate-50 disabled:opacity-30 transition-colors">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/></svg>
              合并前件
            </button>
            <button @click="splitAsNew" :disabled="selectedIdx < 0"
              class="flex items-center justify-center gap-1 h-8 text-[11px] font-medium rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] bg-white hover:bg-slate-50 disabled:opacity-30 transition-colors">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/></svg>
              拆分新件
            </button>
            <button @click="setAsNextFirst" :disabled="selectedIdx < 0 || selectedIdx >= docs.length - 1"
              class="flex items-center justify-center gap-1 h-8 text-[11px] font-medium rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] bg-white hover:bg-slate-50 disabled:opacity-30 transition-colors">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
              设为后件首页
            </button>
            <button @click="markEscalate" :disabled="selectedIdx < 0"
              class="flex items-center justify-center gap-1 h-8 text-[11px] font-medium rounded-md border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 disabled:opacity-30 transition-colors">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/></svg>
              标记升级
            </button>
          </div>
        </div>
      </aside>

      <!-- Center: page viewer -->
      <section class="w-[640px] min-w-[640px] max-w-[640px] xl:w-[700px] xl:min-w-[700px] xl:max-w-[700px] border border-slate-200 bg-white flex flex-col overflow-hidden min-h-0 flex-shrink-0">
        <div class="h-[62px] border-b border-slate-100 bg-white px-5 flex items-center justify-between gap-3 flex-shrink-0">
          <div class="min-w-0">
            <span class="inline-flex h-7 items-center rounded-t bg-blue-50 px-4 text-xs font-semibold text-blue-600">{{ currentImageViewLabel }}</span>
            <div class="mt-2 flex items-center gap-2 text-xs text-slate-500">
              <svg class="h-4 w-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20"><path d="M4 3.5A1.5 1.5 0 0 1 5.5 2h5.38a1.5 1.5 0 0 1 1.06.44l3.62 3.62A1.5 1.5 0 0 1 16 7.12v9.38a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 4 16.5v-13Z"/></svg>
              <span class="truncate text-slate-700">{{ selectedDocTitle }}</span>
              <span class="text-slate-300">·</span>
              <span class="tabular-nums">{{ currentPage }}/{{ totalPages }}</span>
            </div>
          </div>
          <div class="inline-flex rounded border border-slate-200 bg-white">
            <button type="button" class="h-8 px-3 text-xs font-medium transition-colors"
              :class="imageViewMode === 'preview' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50'"
              @click="switchImageViewMode('preview')">校正预览</button>
            <button type="button" class="h-8 border-l border-slate-200 px-3 text-xs font-medium transition-colors"
              :disabled="!sourceImageUrl"
              :class="imageViewMode === 'source' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50 disabled:opacity-40'"
              @click="switchImageViewMode('source')">原始扫描</button>
          </div>
        </div>

        <div class="relative flex-1 min-h-0 overflow-y-auto overflow-x-auto overscroll-contain bg-white">
          <div class="flex min-h-max min-w-max items-start justify-center px-6 pb-24 pt-6">
            <div v-if="pageImageUrl" class="relative inline-flex overflow-hidden border border-slate-200 bg-white">
              <img ref="pageImageRef" :src="pageImageUrl" alt="页面预览" class="max-w-none select-none object-contain"
                :style="pageImageStyle"
                @load="handlePageImageLoad" />
              <div class="pointer-events-none absolute inset-0">
                <div v-for="block in pageOverlayItems" :key="block.id"
                  class="absolute border transition-all duration-200"
                  :class="overlayBoxClass(block)"
                  :style="boxStyleFromBbox(block.bbox)">
                  <span class="absolute -top-5 left-0 bg-blue-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                    {{ officialBlockLabel(block) }}
                  </span>
                </div>
              </div>
            </div>
            <PdfViewer v-else-if="previewUrl && !pdfLoadFailed" :src="previewUrl" :page="currentPage" class="h-full w-full"
              @page-change="(p) => (currentPage = p)" @load-error="pdfLoadFailed = true" />
            <div v-else class="border border-dashed border-slate-300 bg-white px-8 py-10 text-sm text-[var(--gov-text-muted)]">暂无预览</div>
          </div>
          <div class="pointer-events-none absolute inset-x-0 bottom-5 flex justify-center">
            <div class="pointer-events-auto inline-flex h-11 items-center gap-1 rounded-full border border-slate-200 bg-white/95 px-3 shadow-[0_10px_28px_rgba(15,23,42,0.14)] backdrop-blur">
              <button type="button" class="h-8 w-8 rounded-full text-slate-400 transition hover:bg-slate-50 hover:text-slate-700 disabled:opacity-30" :disabled="currentPage <= pageRange[0]" @click="goToPage(currentPage - 1)" aria-label="上一页">‹</button>
              <span class="mx-2 min-w-[64px] rounded border border-slate-200 bg-white px-3 py-1 text-center text-sm tabular-nums text-slate-700">{{ currentPage }}</span>
              <span class="px-1 text-sm text-slate-400">/</span>
              <span class="px-2 text-sm tabular-nums text-slate-600">{{ totalPages }}</span>
              <button type="button" class="h-8 w-8 rounded-full text-slate-400 transition hover:bg-slate-50 hover:text-slate-700 disabled:opacity-30" :disabled="currentPage >= pageRange[pageRange.length - 1]" @click="goToPage(currentPage + 1)" aria-label="下一页">›</button>
              <span class="mx-2 h-5 w-px bg-slate-200"></span>
              <button type="button" class="h-8 w-8 rounded-full text-slate-500 transition hover:bg-slate-50 hover:text-slate-800" @click="changePreviewScale(-0.1)" aria-label="缩小">⌕</button>
              <button type="button" class="h-8 w-8 rounded-full text-slate-500 transition hover:bg-slate-50 hover:text-slate-800" @click="changePreviewScale(0.1)" aria-label="放大">⊕</button>
              <button type="button" class="h-8 w-8 rounded-full text-slate-500 transition hover:bg-slate-50 hover:text-slate-800" @click="resetPreviewScale" aria-label="重置缩放">↻</button>
            </div>
          </div>
        </div>
      </section>

      <!-- Right: evidence & actions -->
      <aside class="w-[620px] min-w-[620px] max-w-[620px] 2xl:w-[660px] 2xl:min-w-[660px] 2xl:max-w-[660px] border border-slate-200 bg-white flex flex-col flex-shrink-0 overflow-hidden min-h-0">
        <!-- Tab bar -->
        <div class="h-[42px] border-b border-slate-100 bg-[#f3f6ff] px-4 flex items-center justify-between gap-3 flex-shrink-0">
          <div class="flex items-center gap-3 text-xs">
            <span class="text-slate-500">解析模型</span>
            <span class="font-medium text-blue-600">PaddleOCR-VL-1.5</span>
            <span class="rounded bg-indigo-500 px-1.5 py-0.5 text-[10px] font-bold text-white">NEW</span>
          </div>
          <span class="text-slate-500">⌄</span>
        </div>

        <div class="h-[46px] border-b border-slate-100 bg-white px-4 flex items-center justify-between gap-2 flex-shrink-0">
          <div class="inline-flex items-center gap-1">
            <button v-for="tab in evidenceTabs" :key="tab.key" @click="activeTab = tab.key"
              class="h-8 px-3 text-[13px] font-medium transition-colors"
              :class="activeTab === tab.key
                ? 'bg-blue-50 text-blue-600'
                : 'text-slate-700 hover:bg-slate-50'">{{ tab.label }}</button>
          </div>
          <div class="flex items-center gap-4 text-slate-500">
            <span class="text-[11px]">{{ currentPageStructureSummary.region_count }} 区域</span>
            <button type="button" class="text-lg leading-none hover:text-slate-800" aria-label="解析设置">⌘</button>
            <button type="button" class="text-lg leading-none hover:text-slate-800" aria-label="刷新">↻</button>
            <button type="button" class="text-lg leading-none hover:text-slate-800" aria-label="下载">⇩</button>
          </div>
        </div>

        <div ref="analysisPanelRef" class="flex-1 min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain bg-white">
          <!-- Tab: boundary evidence -->
          <div v-show="activeTab === 'boundary'">
            <div class="px-3 py-3 border-b border-[var(--gov-border)]">
              <div class="flex items-center justify-between mb-2">
                <span class="text-[10px] font-semibold text-slate-500 tracking-wider">置信度</span>
                <span class="text-sm font-bold tabular-nums" :class="confColor(currentEvidence.confidence)">{{ confPercent }}%</span>
              </div>
              <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div class="h-full rounded-full transition-all duration-300" :style="{ width: confPercent + '%' }"
                  :class="confPercent >= 80 ? 'bg-green-500' : confPercent >= 50 ? 'bg-amber-500' : 'bg-red-500'"></div>
              </div>
            </div>

            <div class="px-3 py-3 border-b border-[var(--gov-border)]">
              <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-2">边界判定原因</p>
              <div v-if="currentEvidence.boundary_reason" class="rounded-md border border-slate-200 bg-[var(--gov-surface-muted)] p-2.5">
                <p class="text-xs text-[var(--gov-text)] leading-relaxed">{{ currentEvidence.boundary_reason }}</p>
              </div>
              <p v-else class="text-xs text-[var(--gov-text-muted)] italic">暂无判定信息</p>
            </div>

            <div class="px-3 py-3 border-b border-[var(--gov-border)]">
              <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-2">标题候选</p>
              <div v-if="currentEvidence.title_candidates?.length" class="space-y-1.5">
                <div v-for="(tc, i) in currentEvidence.title_candidates" :key="i"
                  class="rounded-md border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-2.5 py-1.5 text-xs text-[var(--gov-text)]">{{ tc }}</div>
              </div>
              <p v-else class="text-xs text-[var(--gov-text-muted)] italic">暂无</p>
            </div>

            <div class="px-3 py-3">
              <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-2">日期候选</p>
              <div v-if="currentEvidence.date_candidates?.length" class="flex flex-wrap gap-1.5">
                <span v-for="(dc, i) in currentEvidence.date_candidates" :key="i"
                  class="inline-block rounded-md bg-purple-50 border border-purple-200 px-2.5 py-1 text-xs text-purple-700 font-medium">{{ dc }}</span>
              </div>
              <p v-else class="text-xs text-[var(--gov-text-muted)] italic">暂无</p>
            </div>
          </div>

          <!-- Tab: structured OCR -->
          <div v-show="activeTab === 'ocr'" class="mx-auto w-full max-w-[560px] space-y-8 px-5 py-8 2xl:max-w-[600px]">
            <div v-if="currentStructureStatusText" class="border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-700">
              {{ currentStructureStatusText }}
            </div>

            <section v-if="!isOcrOnlyMode && documentStructuredBlocks.length" class="bg-white">
              <div class="mb-5 border-b border-slate-100 pb-3">
                <p class="text-sm font-semibold text-slate-800">文档结构还原</p>
                <p class="mt-0.5 text-[11px] text-slate-400">按原页位置重排标题、正文、表格与印章证据。</p>
              </div>
              <div class="space-y-5">
                <article v-for="block in documentStructuredBlocks" :key="block.id" :ref="block.type === 'seal' ? (el) => setSealCardRef(block, el) : undefined"
                  class="relative bg-white transition-all"
                  :class="selectedOcrBoxId === block.id ? 'ring-1 ring-blue-500' : ''"
                  @click="focusOcrBox(block, { scroll: false })">
                  <div class="mb-1 flex items-center justify-between gap-2">
                    <span class="px-2 py-0.5 text-[11px] font-semibold text-white" :class="block.type === 'table' ? 'bg-emerald-600' : block.type === 'seal' ? 'bg-rose-600' : 'bg-blue-600'">{{ officialBlockLabel(block) }}</span>
                    <button type="button" class="text-[11px] font-semibold text-blue-600 hover:underline" @click.stop="focusOcrBox(block)">定位区域</button>
                  </div>

                  <div v-if="block.type === 'table'" class="overflow-x-auto">
                    <table v-if="normalizeTableRows(block.tableData).length" class="w-full min-w-[560px] table-fixed border-collapse text-[12px]">
                      <tbody>
                        <tr v-for="(row, rowIndex) in normalizeTableRows(block.tableData)" :key="rowIndex" class="bg-white">
                          <td v-for="colIndex in tableColumnCount(block)" :key="colIndex"
                            class="border border-slate-300 px-3 py-3 align-top leading-relaxed text-slate-700">
                            {{ row[colIndex - 1] || '' }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    <p v-else class="border border-emerald-500 px-3 py-3 text-sm leading-relaxed text-slate-700 whitespace-pre-wrap">{{ block.content || '表格结构未返回单元格，仅可定位区域。' }}</p>
                  </div>

                  <div v-else-if="block.type === 'seal'">
                    <div v-if="pageImageUrl && sealCropRect(block)" class="relative h-[220px] overflow-hidden border border-slate-200 bg-white" :style="sealCropFrameStyle(block)">
                      <img :src="pageImageUrl" alt="印章裁剪预览" class="absolute max-w-none object-fill" :style="sealCropStyle(block)" />
                    </div>
                    <div v-else class="border border-dashed border-slate-200 bg-slate-50 px-3 py-8 text-center text-xs text-slate-500">
                      已识别到印章文字，等待模型返回更精确的印章坐标。
                    </div>
                    <div class="mt-2 bg-blue-600 px-2.5 py-1.5 text-xs font-semibold text-white">{{ sealPrimaryText(block) }}</div>
                    <p v-for="(text, textIndex) in sealTextList(block)" :key="textIndex" class="border border-transparent px-2.5 py-1.5 text-sm leading-relaxed text-slate-700">{{ text }}</p>
                    <div class="mt-3 flex items-center justify-end gap-2">
                      <button type="button" class="h-8 rounded-full border border-slate-200 bg-white px-3 text-[11px] font-semibold text-slate-600 shadow-sm hover:bg-slate-50" @click.stop="copySealText(block)">复制</button>
                      <button type="button" class="h-8 rounded-full border border-slate-200 bg-white px-3 text-[11px] font-semibold text-slate-600 shadow-sm hover:bg-slate-50" @click.stop="requestSealCorrection(block)">纠正</button>
                    </div>
                  </div>

                  <p v-else class="border px-4 py-3 whitespace-pre-wrap"
                    :class="[selectedOcrBoxId === block.id ? 'border-blue-500' : 'border-transparent', block.type === 'title' ? 'text-xl font-semibold leading-9 text-slate-900' : 'text-sm leading-7 text-slate-800']">{{ block.content || '（无文本）' }}</p>
                </article>
              </div>
            </section>

            <section v-if="isOcrOnlyMode" class="bg-white">
              <div class="mb-4 border-b border-slate-100 pb-3">
                <p class="text-sm font-semibold text-slate-800">OCR 行文本</p>
                <p class="mt-0.5 text-[11px] text-slate-400">当前页没有结构化区域，以下为纯文本识别结果。</p>
              </div>
              <pre class="whitespace-pre-wrap break-words text-sm leading-7 text-slate-800">{{ currentPageOcr || '（当前页无OCR文本）' }}</pre>
            </section>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="border-t border-[var(--gov-border)] p-3 space-y-2 flex-shrink-0">
          <div v-if="opMsg" class="rounded-md border p-2 text-[11px]" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
            {{ opMsg.text }}
          </div>

          <button v-if="selectedDoc && !selectedDoc._confirmed" @click="confirmDoc(selectedIdx)"
            class="w-full h-9 text-[13px] font-medium rounded-md border border-green-300 text-green-700 bg-green-50 hover:bg-green-100 transition-colors flex items-center justify-center gap-1.5">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>
            确认本件边界
          </button>
          <div v-else-if="selectedDoc?._confirmed" class="w-full h-9 rounded-md bg-green-50 border border-green-200 flex items-center justify-center gap-1.5 text-[13px] text-green-600 font-medium">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            已确认
            <button @click="unconfirmDoc(selectedIdx)" class="text-[10px] text-green-500 hover:text-green-700 ml-1 underline">撤销</button>
          </div>

          <div class="flex gap-2">
            <button @click="submitStructure('approve')" :disabled="submitting || confirmedCount < docs.length"
              class="flex-1 h-9 text-[13px] font-semibold rounded-md bg-[var(--gov-primary)] text-white hover:bg-[var(--gov-primary-hover)] disabled:opacity-40 transition-colors">
              {{ submitting ? '提交中…' : '审核通过' }}
            </button>
            <button @click="openReject" class="h-9 px-3 text-[13px] rounded-md border border-red-200 text-red-600 hover:bg-red-50 transition-colors">
              驳回
            </button>
          </div>
          <p v-if="confirmedCount < docs.length" class="text-[10px] text-[var(--gov-text-muted)] text-center">
            请先确认所有件的边界后提交
          </p>
        </div>
      </aside>
      </div>
      </div>
    </div>

    <ReworkModal v-model="showReworkModal" :record-id="String(taskId)" @submitted="submitStructure('reject', $event)" />
  </AppShell>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import ReworkModal from '@/shared/components/ReworkModal.vue'
import { getReviewTask, listDocUnits, submitReview } from '@/api/archive'
import { formatRefreshTime } from '@/features/batches/progress'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const task = ref(null)
const docs = ref([])
const selectedIdx = ref(0)
const currentPage = ref(1)
const loadError = ref('')
const submitting = ref(false)
const opMsg = ref(null)
const showReworkModal = ref(false)
const activeTab = ref('ocr')
const dragFrom = ref(-1)
const dragOverIdx = ref(-1)
const refreshing = ref(false)
const lastRefreshedAt = ref(null)
const hasLocalStructureChanges = ref(false)
const imageViewMode = ref('preview')
const pageImageRef = ref(null)
const pageImageNaturalSize = ref({ width: 0, height: 0 })
const selectedOcrBoxId = ref('')
const analysisPanelRef = ref(null)
const sealCardRefs = new Map()
const previewScale = ref(1)

const AUTO_REFRESH_MS = 10000
const ACTIVE_REVIEW_TASK_STATUSES = new Set(['pending', 'processing', 'human_review', 'claimed', 'running'])
let structureRefreshTimer = null

const evidenceTabs = [
  { key: 'ocr', label: '文档解析' },
  { key: 'boundary', label: 'JSON' },
]

const selectedDoc = computed(() => docs.value[selectedIdx.value] || null)
const selectedDocTitle = computed(() => selectedDoc.value?.title || selectedDoc.value?.name || '未选择文档')
const previewUrl = computed(() => selectedDoc.value?.pdf_url || selectedDoc.value?.preview_url || null)
const totalPages = computed(() => Number(selectedDoc.value?.page_count || selectedDoc.value?.pages?.length || 1))
const pdfLoadFailed = ref(false)
const _currentPageEntry = computed(() => {
  const doc = selectedDoc.value
  if (!doc?.ocr_pages?.length) return null
  const start = Number(doc.start_page || 1)
  const localIdx = Math.max(0, Number(currentPage.value) - start)
  return doc.ocr_pages[localIdx] || doc.ocr_pages[0] || null
})
const previewImageUrl = computed(() => _currentPageEntry.value?.preview_image_url || _currentPageEntry.value?.previewImageUrl || _currentPageEntry.value?.image_url || null)
const sourceImageUrl = computed(() => _currentPageEntry.value?.source_image_url || _currentPageEntry.value?.sourceImageUrl || null)
const hasDistinctPreview = computed(() => Boolean(previewImageUrl.value && sourceImageUrl.value && previewImageUrl.value !== sourceImageUrl.value))
const pageImageUrl = computed(() => {
  if (imageViewMode.value === 'source' && sourceImageUrl.value) return sourceImageUrl.value
  return previewImageUrl.value || sourceImageUrl.value || null
})
const pageImageStyle = computed(() => ({
  width: `${Math.round(760 * previewScale.value)}px`,
  maxWidth: 'none',
  ...(pageImageRotation.value ? { transform: `rotate(${pageImageRotation.value}deg)`, transformOrigin: 'center center' } : {}),
}))
const currentImageViewLabel = computed(() => imageViewMode.value === 'source' ? '原始扫描' : '校正预览')
const currentImageViewHint = computed(() => imageViewMode.value === 'source' ? '展示未校正原图，点击右侧定位后才叠加区域框' : '用于审核的预处理/方向校正图')
const pageImageRotation = computed(() => Number(_currentPageEntry.value?.rotation || 0))
const confirmedCount = computed(() => docs.value.filter(d => d._confirmed).length)
const progressPercent = computed(() => docs.value.length ? Math.round((confirmedCount.value / docs.value.length) * 100) : 0)
const needAttentionCount = computed(() => docs.value.filter(d => (d.risk_level && d.risk_level !== 'none') || (docConfidence(d) != null && docConfidence(d) < 0.6)).length)
const hasUnconfirmedSafe = computed(() => docs.value.some(d => !d._confirmed && (!d.risk_level || d.risk_level === 'none') && (docConfidence(d) == null || docConfidence(d) >= 0.6)))
const autoRefreshEnabled = computed(() => {
  const status = String(task.value?.status || '').trim().toLowerCase()
  return ACTIVE_REVIEW_TASK_STATUSES.has(status) && !hasLocalStructureChanges.value
})
const refreshStatusText = computed(() => {
  const stamp = formatRefreshTime(lastRefreshedAt.value)
  if (hasLocalStructureChanges.value) {
    return stamp ? `${stamp} 更新 · 存在未提交的边界调整，已暂停自动刷新` : '存在未提交的边界调整，已暂停自动刷新'
  }
  if (autoRefreshEnabled.value) {
    return stamp ? `${stamp} 更新 · 结构审核页每10s自动刷新` : '结构审核页每10s自动刷新'
  }
  return stamp ? `${stamp} 更新` : ''
})

const currentPageLines = computed(() => normalizeOcrLines(_currentPageEntry.value?.lines || _currentPageEntry.value?.ocr_lines || []))
const pageStructuredBlocks = computed(() => {
  const regions = Array.isArray(_currentPageEntry.value?.regions) ? _currentPageEntry.value.regions : []
  return regions.map((region, index) => normalizeStructuredBlock(region, index)).filter(Boolean)
})
const tableStructuredBlocks = computed(() => pageStructuredBlocks.value.filter((block) => block.type === 'table'))
const sealStructuredBlocks = computed(() => pageStructuredBlocks.value.filter((block) => block.type === 'seal'))
const textStructuredBlocks = computed(() => pageStructuredBlocks.value.filter((block) => block.type !== 'table' && block.type !== 'seal'))
const visibleStructuredBlocks = computed(() => [...tableStructuredBlocks.value, ...textStructuredBlocks.value, ...sealStructuredBlocks.value])
const documentStructuredBlocks = computed(() => [...pageStructuredBlocks.value].sort(compareBlocksByDocumentOrder))
const currentPageStructureSummary = computed(() => {
  const raw = _currentPageEntry.value?.structure_summary || _currentPageEntry.value?.structureSummary || {}
  const selectedMode = raw.selected_mode || raw.selectedMode || _currentPageEntry.value?.selected_mode || _currentPageEntry.value?.layout_type || (pageStructuredBlocks.value.length ? 'layout' : 'ocr_only')
  return {
    region_count: Number(raw.region_count ?? raw.regionCount ?? pageStructuredBlocks.value.length) || 0,
    table_count: Number(raw.table_count ?? raw.tableCount ?? tableStructuredBlocks.value.length) || 0,
    seal_count: Number(raw.seal_count ?? raw.sealCount ?? sealStructuredBlocks.value.length) || 0,
    line_count: Number(raw.line_count ?? raw.lineCount ?? currentPageLines.value.length) || 0,
    selected_mode: selectedMode,
  }
})
const isOcrOnlyMode = computed(() => String(currentPageStructureSummary.value.selected_mode || '').toLowerCase() === 'ocr_only' || (!pageStructuredBlocks.value.length && currentPageLines.value.length > 0))
const currentStructureStatusText = computed(() => {
  if (isOcrOnlyMode.value) return '当前页未产出结构化结果，仅展示 OCR 行文本'
  if (!pageStructuredBlocks.value.length) return '当前页暂无可定位的结构化区域'
  return ''
})
const selectedStructuredBlock = computed(() => visibleStructuredBlocks.value.find((block) => block.id === selectedOcrBoxId.value) || null)
const primaryStructuredBlock = computed(() => tableStructuredBlocks.value[0] || textStructuredBlocks.value[0] || sealStructuredBlocks.value[0] || null)
const pageOverlayItems = computed(() => {
  if (!pageImageUrl.value) return []
  if (selectedStructuredBlock.value) return [withEffectiveBbox(selectedStructuredBlock.value)]
  if (imageViewMode.value === 'source') return []
  return primaryStructuredBlock.value ? [withEffectiveBbox(primaryStructuredBlock.value)] : []
})

const pageRange = computed(() => {
  const start = Number(selectedDoc.value?.start_page || 1)
  return Array.from({ length: totalPages.value }, (_, i) => start + i)
})

const currentEvidence = computed(() => {
  const ev = task.value?.evidence || selectedDoc.value?.evidence || {}
  const cands = selectedDoc.value?.candidates || selectedDoc.value?.field_candidates || {}
  return {
    boundary_reason: ev.boundary_reason || ev.reason || selectedDoc.value?.boundary_reason || null,
    confidence: ev.confidence ?? selectedDoc.value?.confidence ?? task.value?.confidence ?? null,
    title_candidates: cands.title?.values || (Array.isArray(cands.title) ? cands.title : []),
    date_candidates: cands.date?.values || (Array.isArray(cands.date) ? cands.date : []),
  }
})

const confPercent = computed(() => {
  const c = currentEvidence.value.confidence
  return c != null ? Math.round(c * 100) : 0
})

const currentPageOcr = computed(() => {
  const entry = _currentPageEntry.value
  if (entry?.text || entry?.ocr_text || entry?.content) return entry.text || entry.ocr_text || entry.content
  if (currentPageLines.value.length) return currentPageLines.value.map((line) => line.text).filter(Boolean).join('\n')
  const pages = selectedDoc.value?.ocr_pages || selectedDoc.value?.pages || []
  if (!Array.isArray(pages)) return ''
  const p = pages.find(pg => Number(pg.page_no || pg.page || pg.index) === Number(currentPage.value))
  return p?.text || ''
})

function normalizeOcrLines(lines) {
  if (!Array.isArray(lines)) return []
  return lines.map((line, index) => {
    if (typeof line === 'string') return { id: `line_${index}`, text: line, confidence: null }
    return {
      id: String(line.id || line.line_id || `line_${index}`),
      text: String(line.text || line.content || line.words || '').trim(),
      confidence: line.confidence ?? line.score ?? null,
      bbox: normalizeBbox(extractRawBbox(line)),
    }
  }).filter((line) => line.text)
}

function normalizeRegionType(region = {}) {
  const raw = String(region.type || region.region_type || region.layout_type || region.category || '').toLowerCase()
  if (raw.includes('table') || raw.includes('表')) return 'table'
  if (raw.includes('seal') || raw.includes('stamp') || raw.includes('印章') || raw.includes('归档章')) return 'seal'
  if (raw.includes('title') || raw.includes('标题')) return 'title'
  return 'text'
}

function normalizeStructuredBlock(region = {}, index = 0) {
  const type = normalizeRegionType(region)
  const tableData = region.table_data || region.tableData || region.table || null
  const lines = normalizeOcrLines(region.lines || region.region_lines || region.ocr_lines || [])
  const content = extractRegionText(region, lines)
  const bbox = normalizeBbox(extractRawBbox(region))
  if (!content && !tableData && !bbox) return null
  return {
    raw: region,
    id: String(region.id || region.region_id || `${type}_${index}`),
    index,
    type,
    label: region.label || region.name || (type === 'table' ? '表格' : type === 'seal' ? '印章' : type === 'title' ? '标题' : '正文'),
    confidence: region.confidence ?? region.score ?? region.probability ?? null,
    content,
    tableData,
    lines,
    bbox,
  }
}

function extractRegionText(region = {}, lines = []) {
  const direct = region.content || region.text || region.value || region.words
  if (direct) return String(direct).trim()
  if (Array.isArray(region.texts)) return region.texts.map((item) => typeof item === 'string' ? item : item?.text || item?.content || '').filter(Boolean).join('\n')
  if (lines.length) return lines.map((line) => line.text).filter(Boolean).join('\n')
  return ''
}

function extractRawBbox(item = {}) {
  if (!item || typeof item !== 'object') return null
  return item.bbox
    || item.box
    || item.position
    || item.bounds
    || item.bound
    || item.bounding_box
    || item.boundingBox
    || item.rect
    || item.rectangle
    || item.location
    || item.coordinates
    || item.points
    || item.polygon
    || item.poly
    || item.quad
    || item.seal_bbox
    || item.sealBox
    || item.text_bbox
    || item.textBox
    || item?.seal?.bbox
    || item?.seal?.box
    || null
}

function normalizeBbox(raw) {
  if (!raw) return null
  if (Array.isArray(raw) && raw.length >= 2 && Array.isArray(raw[0])) {
    const points = raw
      .map((point) => Array.isArray(point) ? { x: Number(point[0]), y: Number(point[1]) } : { x: Number(point?.x), y: Number(point?.y) })
      .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
    if (points.length >= 2) {
      const xs = points.map((point) => point.x)
      const ys = points.map((point) => point.y)
      const left = Math.min(...xs)
      const top = Math.min(...ys)
      const right = Math.max(...xs)
      const bottom = Math.max(...ys)
      return { x: left, y: top, width: Math.max(0, right - left), height: Math.max(0, bottom - top) }
    }
  }
  if (Array.isArray(raw) && raw.length >= 4) {
    const nums = raw.slice(0, 4).map(Number)
    if (nums.some((num) => !Number.isFinite(num))) return null
    const [x1, y1, x2, y2] = nums
    if (x2 > x1 && y2 > y1) return { x: x1, y: y1, width: x2 - x1, height: y2 - y1 }
    return { x: x1, y: y1, width: Math.max(0, x2), height: Math.max(0, y2) }
  }
  if (typeof raw === 'object') {
    const nested = raw.bbox || raw.box || raw.points || raw.polygon || raw.poly || raw.coordinates || raw.rect || raw.rectangle
    if (nested && nested !== raw) {
      const normalized = normalizeBbox(nested)
      if (normalized) return normalized
    }
    const x = Number(raw.x ?? raw.left ?? raw.x1 ?? raw.min_x)
    const y = Number(raw.y ?? raw.top ?? raw.y1 ?? raw.min_y)
    const width = raw.width ?? raw.w
    const height = raw.height ?? raw.h
    if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(Number(width)) && Number.isFinite(Number(height))) {
      return { x, y, width: Number(width), height: Number(height) }
    }
    const right = Number(raw.right ?? raw.x2 ?? raw.max_x)
    const bottom = Number(raw.bottom ?? raw.y2 ?? raw.max_y)
    if (Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(right) && Number.isFinite(bottom)) {
      return { x, y, width: Math.max(0, right - x), height: Math.max(0, bottom - y) }
    }
  }
  return null
}

function clamp(num, min = 0, max = 100) {
  return Math.min(max, Math.max(min, Number(num) || 0))
}

function bboxToPercentRect(bbox, expand = 0) {
  if (!bbox) return null
  const values = [bbox.x, bbox.y, bbox.width, bbox.height].map(Number)
  if (values.some((value) => !Number.isFinite(value))) return null
  let [x, y, width, height] = values
  const maxValue = Math.max(Math.abs(x), Math.abs(y), Math.abs(width), Math.abs(height), Math.abs(x + width), Math.abs(y + height))
  if (maxValue <= 1.2) {
    x *= 100; y *= 100; width *= 100; height *= 100
  } else if (pageImageNaturalSize.value.width > 0 && pageImageNaturalSize.value.height > 0) {
    x = (x / pageImageNaturalSize.value.width) * 100
    y = (y / pageImageNaturalSize.value.height) * 100
    width = (width / pageImageNaturalSize.value.width) * 100
    height = (height / pageImageNaturalSize.value.height) * 100
  } else if (maxValue > 100) {
    return null
  }
  const padX = expand ? Math.max(width * expand, pageImageNaturalSize.value.width ? (18 / pageImageNaturalSize.value.width) * 100 : 2) : 0
  const padY = expand ? Math.max(height * expand, pageImageNaturalSize.value.height ? (18 / pageImageNaturalSize.value.height) * 100 : 2) : 0
  const left = clamp(x - padX)
  const top = clamp(y - padY)
  const right = clamp(x + width + padX)
  const bottom = clamp(y + height + padY)
  return { x: left, y: top, width: Math.max(0.5, right - left), height: Math.max(0.5, bottom - top) }
}

function blockSortRect(block) {
  const bbox = effectiveBlockBbox(block)
  if (!bbox) return null
  const values = [bbox.x, bbox.y, bbox.width, bbox.height].map(Number)
  if (values.some((value) => !Number.isFinite(value))) return null
  let [x, y, width, height] = values
  const maxValue = Math.max(Math.abs(x), Math.abs(y), Math.abs(width), Math.abs(height), Math.abs(x + width), Math.abs(y + height))
  if (maxValue <= 1.2) {
    x *= 100; y *= 100; width *= 100; height *= 100
  } else if (pageImageNaturalSize.value.width > 0 && pageImageNaturalSize.value.height > 0 && maxValue > 100) {
    x = (x / pageImageNaturalSize.value.width) * 100
    y = (y / pageImageNaturalSize.value.height) * 100
    width = (width / pageImageNaturalSize.value.width) * 100
    height = (height / pageImageNaturalSize.value.height) * 100
  }
  return { x, y, width, height }
}

function compareBlocksByDocumentOrder(a, b) {
  const ra = blockSortRect(a)
  const rb = blockSortRect(b)
  if (ra && rb) {
    const yDelta = ra.y - rb.y
    if (Math.abs(yDelta) > 3) return yDelta
    const xDelta = ra.x - rb.x
    if (Math.abs(xDelta) > 3) return xDelta
  }
  if (ra && !rb) return -1
  if (!ra && rb) return 1
  return Number(a?.index || 0) - Number(b?.index || 0)
}

function inferSealBbox(block) {
  if (!block || block.type !== 'seal') return null
  const seals = sealStructuredBlocks.value
  const index = Math.max(0, seals.findIndex((seal) => seal.id === block.id))
  const count = Math.max(1, seals.length)
  if (count === 1) return { x: 24, y: 64, width: 48, height: 24 }
  const slot = 68 / count
  return {
    x: 16 + index * slot,
    y: 64,
    width: Math.min(30, slot - 4),
    height: 24,
  }
}

function effectiveBlockBbox(block) {
  return block?.bbox || inferSealBbox(block)
}

function withEffectiveBbox(block) {
  if (!block) return block
  return { ...block, bbox: effectiveBlockBbox(block) }
}

function boxStyleFromBbox(bbox) {
  const rect = bboxToPercentRect(bbox)
  if (!rect) return { display: 'none' }
  return { left: `${rect.x}%`, top: `${rect.y}%`, width: `${rect.width}%`, height: `${rect.height}%` }
}

function overlayBoxClass(block) {
  if (block?.type === 'seal') return 'border-rose-500 bg-rose-500/5'
  return 'border-blue-600 bg-blue-500/5'
}

function officialBlockLabel(block) {
  if (block?.type === 'table') return '表格'
  if (block?.type === 'seal') return '印章'
  if (block?.type === 'title') return '标题'
  return '文本'
}

function blockConfidenceText(block) {
  const value = Number(block?.confidence)
  return Number.isFinite(value) ? `${Math.round(value * 100)}%` : ''
}

function normalizeTableRows(tableData) {
  if (!tableData) return []
  const rawRows = Array.isArray(tableData)
    ? tableData
    : Array.isArray(tableData.rows)
      ? tableData.rows
      : Array.isArray(tableData.data)
        ? tableData.data
        : []
  return rawRows.map((row) => {
    if (Array.isArray(row)) return row.map((cell) => String(cell?.text ?? cell?.content ?? cell ?? '').trim())
    if (row && typeof row === 'object') return Object.values(row).map((cell) => String(cell?.text ?? cell?.content ?? cell ?? '').trim())
    return [String(row ?? '').trim()]
  }).filter((row) => row.some(Boolean))
}

function tableColumnCount(block) {
  const rows = normalizeTableRows(block?.tableData)
  return Math.max(1, ...rows.map((row) => row.length))
}

function focusOcrBox(block, options = {}) {
  if (!block) return
  selectedOcrBoxId.value = block.id
  if (block.type === 'seal' && options.scroll !== false) {
    nextTick(() => sealCardRefs.get(block.id)?.scrollIntoView?.({ behavior: 'smooth', block: 'center' }))
  }
}

function setSealCardRef(block, el) {
  if (!block?.id) return
  if (el) sealCardRefs.set(block.id, el)
  else sealCardRefs.delete(block.id)
}

function sealTextList(block) {
  const rawItems = block?.raw?.texts || block?.raw?.lines || block?.lines || []
  const items = normalizeOcrLines(rawItems).map((line) => line.text).filter(Boolean)
  if (items.length) return items
  return String(block?.content || '').split(/\r?\n|\s{2,}/).map((item) => item.trim()).filter(Boolean)
}

function sealPrimaryText(block) {
  const items = sealTextList(block)
  if (!items.length) return '未识别到印章文本'
  return items.find((item) => /公司|委员会|管理|编号|[0-9]{6,}/.test(item)) || items[0]
}

function sealCropRect(block) {
  return bboxToPercentRect(effectiveBlockBbox(block), 0.16)
}

function sealCropFrameStyle(block) {
  const rect = sealCropRect(block)
  return rect ? { aspectRatio: `${Math.max(rect.width, 1)} / ${Math.max(rect.height, 1)}` } : {}
}

function sealCropStyle(block) {
  const rect = sealCropRect(block)
  if (!rect) return {}
  return {
    width: `${10000 / rect.width}%`,
    height: `${10000 / rect.height}%`,
    left: `-${(rect.x * 100) / rect.width}%`,
    top: `-${(rect.y * 100) / rect.height}%`,
  }
}

function handlePageImageLoad(event) {
  pageImageNaturalSize.value = {
    width: Number(event?.target?.naturalWidth || 0),
    height: Number(event?.target?.naturalHeight || 0),
  }
}

function switchImageViewMode(mode) {
  imageViewMode.value = mode
  if (mode === 'source') selectedOcrBoxId.value = ''
}

function goToPage(page) {
  const first = pageRange.value[0] || 1
  const last = pageRange.value[pageRange.value.length - 1] || first
  currentPage.value = Math.min(Math.max(Number(page) || first, first), last)
}

function changePreviewScale(delta) {
  previewScale.value = Math.min(1.6, Math.max(0.7, Number((previewScale.value + delta).toFixed(2))))
}

function resetPreviewScale() {
  previewScale.value = 1
}

async function copySealText(block) {
  const text = sealTextList(block).join('\n') || block?.content || ''
  if (!text) return
  try {
    if (navigator?.clipboard?.writeText) await navigator.clipboard.writeText(text)
    else {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.setAttribute('readonly', '')
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    opMsg.value = { ok: true, text: '印章识别文本已复制' }
  } catch (error) {
    opMsg.value = { ok: false, text: '复制失败，请手动选择文本' }
  }
}

function requestSealCorrection(block) {
  focusOcrBox(block, { scroll: false })
  opMsg.value = { ok: true, text: '已定位印章区域，可在后续纠正流程中核对文本' }
}

function docConfidence(doc) { return doc?.confidence ?? doc?.evidence?.confidence ?? null }
function confColor(c) { return c == null ? 'text-slate-400' : c >= 0.8 ? 'text-green-600' : c >= 0.5 ? 'text-amber-600' : 'text-red-600' }
function docSeqClass(doc) { return doc.risk_level === 'high' ? 'bg-red-100 text-red-700' : doc.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600' }
function riskTagClass(level) { return level === 'high' ? 'bg-red-100 text-red-700' : level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500' }
function isBoundaryPage(p) { return docs.value.some(d => Number(d.start_page) === p) }
function getDocKey(doc) { const key = doc?.id ?? doc?.doc_id; return key == null ? '' : String(key) }
function getDocSpan(doc) {
  const start = Number(doc?.start_page || 1)
  const end = Number(doc?.end_page || start)
  if (Number.isFinite(start) && Number.isFinite(end) && end >= start) return { start, end }
  const pageCount = Number(doc?.page_count || (Array.isArray(doc?.pages) ? doc.pages.length : doc?.pages) || 1)
  const count = Number.isFinite(pageCount) && pageCount > 0 ? pageCount : 1
  return { start, end: start + count - 1 }
}
function markStructureDirty() { hasLocalStructureChanges.value = true }

function confirmDoc(idx) {
  if (idx < 0 || idx >= docs.value.length) return
  markStructureDirty()
  docs.value[idx]._confirmed = true
  opMsg.value = { ok: true, text: `件 ${idx + 1} 已确认` }
  const next = docs.value.findIndex((d, i) => i > idx && !d._confirmed)
  if (next >= 0) setTimeout(() => selectDoc(next), 200)
}
function unconfirmDoc(idx) {
  if (idx >= 0 && idx < docs.value.length) {
    markStructureDirty()
    docs.value[idx]._confirmed = false
  }
}
function confirmAllSafe() {
  let count = 0
  docs.value.forEach(d => {
    if (!d._confirmed && (!d.risk_level || d.risk_level === 'none')) {
      const c = docConfidence(d); if (c == null || c >= 0.6) { d._confirmed = true; count++ }
    }
  })
  if (count > 0) markStructureDirty()
  opMsg.value = { ok: true, text: `已批量确认 ${count} 件` }
}

function extractArray(data, keys = ['items']) {
  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key]
  }
  if (Array.isArray(data)) return data
  return []
}

async function loadTask(options = {}) {
  loadError.value = ''
  const previousDocKey = options.preserveSelection === false ? '' : getDocKey(selectedDoc.value)
  const previousPage = currentPage.value
  try {
    const res = await getReviewTask(taskId)
    task.value = res.data || null
    const taskDocs = task.value?.docs || task.value?.doc_units || []
    if (Array.isArray(taskDocs) && taskDocs.length) {
      docs.value = taskDocs.map(d => ({ ...d, _confirmed: false }))
    } else if (task.value?.batch_id) {
      const r = await listDocUnits(task.value.batch_id)
      docs.value = extractArray(r.data).map(d => ({ ...d, _confirmed: false }))
    } else { docs.value = [] }
    if (docs.value.length) {
      const nextIndex = previousDocKey
        ? docs.value.findIndex((doc) => getDocKey(doc) === previousDocKey)
        : 0
      const targetIndex = nextIndex >= 0 ? nextIndex : 0
      const preservePage = Boolean(previousDocKey) && targetIndex >= 0 && getDocKey(docs.value[targetIndex]) === previousDocKey
      selectDoc(targetIndex, { preservePage, page: previousPage })
    } else {
      selectedIdx.value = 0
      currentPage.value = 1
    }
    hasLocalStructureChanges.value = false
    lastRefreshedAt.value = new Date()
  } catch (error) { loadError.value = error?.response?.data?.detail || '加载审核任务失败，请返回重试。' }
}
function selectDoc(idx, options = {}) {
  selectedIdx.value = idx
  const doc = docs.value[idx]
  if (!doc) {
    currentPage.value = 1
    return
  }
  const span = getDocSpan(doc)
  const requestedPage = options.preservePage ? Number(options.page || span.start) : span.start
  currentPage.value = Math.min(Math.max(requestedPage, span.start), span.end)
  selectedOcrBoxId.value = ''
  imageViewMode.value = 'preview'
  previewScale.value = 1
  sealCardRefs.clear()
  pageImageNaturalSize.value = { width: 0, height: 0 }
}

function onDragStart(idx, e) { dragFrom.value = idx; e.dataTransfer.effectAllowed = 'move' }
function onDrop(idx) {
  dragOverIdx.value = -1
  if (dragFrom.value < 0 || dragFrom.value === idx) return
  const list = [...docs.value]; const [moved] = list.splice(dragFrom.value, 1); list.splice(idx, 0, moved)
  markStructureDirty()
  docs.value = list; selectedIdx.value = idx; dragFrom.value = -1
  opMsg.value = { ok: true, text: '已调整顺序（本地）' }
}

function mergeWithPrev() {
  if (selectedIdx.value <= 0) return
  markStructureDirty()
  const prev = docs.value[selectedIdx.value - 1], cur = docs.value[selectedIdx.value]
  prev.end_page = cur.end_page || prev.end_page
  prev.page_count = (Number(prev.page_count) || 0) + (Number(cur.page_count) || 0)
  prev._confirmed = false; docs.value.splice(selectedIdx.value, 1)
  selectedIdx.value = Math.max(0, selectedIdx.value - 1)
  opMsg.value = { ok: true, text: '已合并到前件（本地）' }
}
function splitAsNew() {
  if (selectedIdx.value < 0) return
  markStructureDirty()
  const cur = docs.value[selectedIdx.value]
  const newDoc = { id: `new_${Date.now()}`, title: `拆分件（从第${currentPage.value}页）`, start_page: currentPage.value, end_page: cur.end_page, page_count: (Number(cur.end_page) || currentPage.value) - currentPage.value + 1, status: 'pending', risk_level: 'medium', _confirmed: false }
  cur.end_page = currentPage.value - 1; cur.page_count = (Number(cur.end_page) || 0) - (Number(cur.start_page) || 0) + 1; cur._confirmed = false
  docs.value.splice(selectedIdx.value + 1, 0, newDoc); selectedIdx.value += 1
  opMsg.value = { ok: true, text: '已拆分为新件（本地）' }
}
function setAsNextFirst() {
  if (selectedIdx.value < 0 || selectedIdx.value >= docs.value.length - 1) return
  markStructureDirty()
  const cur = docs.value[selectedIdx.value], next = docs.value[selectedIdx.value + 1]
  next.start_page = currentPage.value; cur.end_page = currentPage.value - 1
  cur.page_count = Math.max(0, (Number(cur.end_page) || 0) - (Number(cur.start_page) || 0) + 1)
  cur._confirmed = false; next._confirmed = false
  opMsg.value = { ok: true, text: '已设为后一件首页（本地）' }
}
function markEscalate() {
  if (selectedIdx.value < 0) return
  markStructureDirty()
  docs.value[selectedIdx.value].risk_level = 'high'; docs.value[selectedIdx.value].escalated = true; docs.value[selectedIdx.value]._confirmed = false
  opMsg.value = { ok: true, text: '已标记升级处理' }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (!autoRefreshEnabled.value) return
  structureRefreshTimer = window.setInterval(() => {
    if (!document.hidden && !showReworkModal.value && !submitting.value && !hasLocalStructureChanges.value) {
      loadTask()
    }
  }, AUTO_REFRESH_MS)
}

function stopAutoRefresh() {
  if (structureRefreshTimer) {
    window.clearInterval(structureRefreshTimer)
    structureRefreshTimer = null
  }
}

async function handleManualRefresh() {
  if (refreshing.value) return
  if (hasLocalStructureChanges.value) {
    opMsg.value = { ok: false, text: '存在未提交的边界调整，请先提交或撤销后再刷新' }
    return
  }
  refreshing.value = true
  try {
    await loadTask()
  } finally {
    refreshing.value = false
  }
}

async function submitStructure(decision, rejectPayload) {
  submitting.value = true; opMsg.value = null
  try {
    const payload = { decision, structure: docs.value.map((d, i) => ({ doc_id: d.id || d.doc_id, sequence: i, start_page: d.start_page, end_page: d.end_page, escalated: d.escalated || false })) }
    if (decision === 'reject' && rejectPayload) { payload.reason = rejectPayload.description; payload.rework = rejectPayload }
    await submitReview(taskId, payload); showReworkModal.value = false; router.push('/tasks')
  } catch (error) { opMsg.value = { ok: false, text: '提交失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { submitting.value = false }
}
function openReject() { showReworkModal.value = true }

function handleKeyboard(e) {
  const tag = e.target?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return
  if (e.key === 'ArrowUp' && !e.ctrlKey) { e.preventDefault(); if (selectedIdx.value > 0) selectDoc(selectedIdx.value - 1) }
  else if (e.key === 'ArrowDown' && !e.ctrlKey) { e.preventDefault(); if (selectedIdx.value < docs.value.length - 1) selectDoc(selectedIdx.value + 1) }
  else if (e.key === ' ' && !e.shiftKey) { e.preventDefault(); if (selectedDoc.value && !selectedDoc.value._confirmed) confirmDoc(selectedIdx.value) }
  else if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (confirmedCount.value >= docs.value.length) submitStructure('approve') }
}

watch(autoRefreshEnabled, (active) => {
  if (active) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

watch(selectedIdx, () => { pdfLoadFailed.value = false })
watch(currentPage, () => {
  selectedOcrBoxId.value = ''
  sealCardRefs.clear()
  pageImageNaturalSize.value = { width: 0, height: 0 }
})
watch(sourceImageUrl, (url) => {
  if (!url && imageViewMode.value === 'source') imageViewMode.value = 'preview'
})

onMounted(() => { loadTask(); document.addEventListener('keydown', handleKeyboard) })
onUnmounted(() => { stopAutoRefresh(); document.removeEventListener('keydown', handleKeyboard) })
</script>
