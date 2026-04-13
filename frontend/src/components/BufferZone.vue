<template>
  <div class="gov-panel flex min-h-full flex-col overflow-hidden">
    <div class="border-b px-5 py-4" :class="cc.headerBg">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg text-white" :class="cc.iconBg">
            <svg v-if="model.icon === 'brain'" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
            <svg v-else-if="model.icon === 'layout'" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
            <svg v-else-if="model.icon === 'cloud'" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z"/></svg>
            <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>
          </div>
          <div>
            <h3 class="text-sm font-semibold text-[var(--gov-text)]">{{ model.name }}</h3>
            <p class="text-xs gov-muted">{{ model.desc }}</p>
          </div>
        </div>
        <span
          v-if="model.badge"
          class="rounded-full px-2 py-0.5 text-xs font-medium"
          :class="model.color === 'cyan' ? 'bg-cyan-100 text-cyan-700' : model.color === 'indigo' ? 'bg-indigo-100 text-indigo-700' : model.color === 'green' ? 'bg-emerald-100 text-emerald-700' : 'bg-blue-100 text-blue-700'"
        >
          {{ model.badge }}
        </span>
      </div>
    </div>

    <div class="flex-1 p-6">
      <div
        class="cursor-pointer rounded-lg border-2 border-dashed px-8 py-16 text-center transition-all"
        :class="dragover ? 'border-[var(--gov-primary)] bg-[var(--gov-primary-soft)]' : 'border-[var(--gov-border)] hover:border-[var(--gov-border-strong)] hover:bg-slate-50'"
        @click="fileInput?.click()"
        @dragover.prevent="dragover = true"
        @dragleave="dragover = false"
        @drop.prevent="handleDrop"
      >
        <svg class="mx-auto mb-3 h-12 w-12 text-[var(--gov-text-muted)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M12 16V4m0 0L8 8m4-4l4 4M2 17l.621 2.485A2 2 0 004.561 21h14.878a2 2 0 001.94-1.515L22 17"/></svg>
        <p class="text-base text-[var(--gov-text-muted)]">拖拽材料到这里，或 <span class="font-medium text-[var(--gov-primary)]">点击选择</span></p>
        <p class="mt-2 text-sm gov-muted">支持 JPG / PNG / PDF</p>
      </div>

      <div class="mt-5 flex flex-wrap gap-3">
        <button class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--gov-text)] transition hover:bg-slate-50" @click="fileInput?.click()">
          选择文件
        </button>
        <button class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--gov-text)] transition hover:bg-slate-50" @click="folderInput?.click()">
          选择目录
        </button>
        <button class="rounded-lg border border-dashed border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-2.5 text-sm font-medium text-[var(--gov-text-muted)] transition hover:border-[var(--gov-border-strong)] hover:text-[var(--gov-text)]" @click="toggleViewMode">
          {{ isAdvancedView ? '收起高级设置' : '高级设置' }}
        </button>
      </div>

      <div v-if="isAdvancedView" class="mt-3 rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] p-3">
        <div class="mb-2 flex items-center justify-between">
          <div>
            <p class="text-xs font-semibold text-[var(--gov-text)]">高级设置</p>
            <p class="mt-1 text-[11px] gov-muted">目录导入与导出路径。</p>
          </div>
          <button class="text-xs gov-muted hover:text-[var(--gov-text)]" @click="toggleViewMode">收起</button>
        </div>

        <div class="space-y-2">
          <div class="flex space-x-2">
            <input
              v-model="folderPath"
              type="text"
              placeholder="输入已授权的目录路径"
              class="w-full rounded-lg border border-dashed border-[var(--gov-border)] px-3 py-2 text-xs focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
              @keydown.enter="importFromPath"
            />
            <button
              class="rounded-lg px-3 py-2 text-xs font-medium text-white transition"
              :class="scanning ? 'bg-slate-400' : 'bg-[var(--gov-primary)] hover:brightness-105'"
              :disabled="!folderPath.trim() || scanning"
              @click="importFromPath"
            >
              {{ scanning ? '导入中…' : '目录导入' }}
            </button>
          </div>

          <input
            v-model="excelPath"
            type="text"
            placeholder="归档目录导出位置（可选）"
            class="w-full rounded-lg border border-dashed border-[var(--gov-border)] px-3 py-2 text-xs focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
          />
          <input
            v-model="outputDir"
            type="text"
            placeholder="处理结果保存位置（可选）"
            class="w-full rounded-lg border border-dashed border-[var(--gov-border)] px-3 py-2 text-xs focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
          />

          <button
            class="w-full rounded-lg border border-dashed border-[var(--gov-border)] bg-white py-2 text-xs font-medium text-[var(--gov-text-muted)] transition hover:border-[var(--gov-border-strong)] hover:text-[var(--gov-text)]"
            @click="doExportInitExcel"
          >
            导出目录清单模板
          </button>
        </div>
      </div>

      <input ref="fileInput" type="file" multiple accept=".jpg,.jpeg,.png,.bmp,.tiff,.tif,.pdf" class="hidden" @change="onFileSelect" />
      <input ref="folderInput" type="file" webkitdirectory multiple class="hidden" @change="onFolderSelect" />
    </div>

    <div v-if="hasImportActivity" class="px-4 pb-3">
      <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p class="text-xs font-semibold tracking-[0.14em] text-[var(--gov-primary)]">{{ stageMeta.eyebrow }}</p>
            <p class="mt-1 text-sm font-semibold text-[var(--gov-text)]">{{ stageMeta.title }}</p>
            <p class="mt-1 text-xs leading-6 gov-muted">{{ importMessage || stageMeta.description }}</p>
          </div>
          <div class="rounded-full border border-[var(--gov-border)] bg-white px-3 py-1 text-xs font-medium text-[var(--gov-text-muted)]">
            {{ Math.round(importProgressPercent) }}%
          </div>
        </div>

        <div class="mt-3 h-2 w-full rounded-full bg-white/90">
          <div class="h-2 rounded-full transition-all duration-300" :class="cc.progressBar" :style="{ width: `${importProgressPercent}%` }"></div>
        </div>

        <div v-if="displayQueueSummary.totalFiles" class="mt-3 grid grid-cols-3 gap-2 text-xs">
          <div class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2">
            <p class="gov-muted">材料数量</p>
            <p class="mt-1 font-semibold text-[var(--gov-text)]">{{ displayQueueSummary.totalFiles }} 份</p>
          </div>
          <div class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2">
            <p class="gov-muted">涉及目录</p>
            <p class="mt-1 font-semibold text-[var(--gov-text)]">{{ displayQueueSummary.folderCount || 0 }} 个</p>
          </div>
          <div class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2">
            <p class="gov-muted">总大小</p>
            <p class="mt-1 font-semibold text-[var(--gov-text)]">{{ displayQueueSummary.totalSizeLabel }}</p>
          </div>
        </div>

        <div v-if="totalCount" class="mt-3 grid grid-cols-2 gap-2 text-xs md:grid-cols-5">
          <div class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2">
            <p class="gov-muted">提交总量</p>
            <p class="mt-1 font-semibold text-[var(--gov-text)]">{{ totalCount }} 份</p>
          </div>
          <div class="rounded-lg border border-emerald-100 bg-emerald-50/70 px-3 py-2">
            <p class="text-emerald-700/80">完成</p>
            <p class="mt-1 font-semibold text-emerald-700">{{ completedCount }} 份</p>
          </div>
          <div class="rounded-lg border border-blue-100 bg-blue-50/70 px-3 py-2">
            <p class="text-blue-700/80">处理中</p>
            <p class="mt-1 font-semibold text-blue-700">{{ processingCount }} 份</p>
          </div>
          <div class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <p class="text-slate-600">排队中</p>
            <p class="mt-1 font-semibold text-slate-700">{{ pendingCount }} 份</p>
          </div>
          <div class="rounded-lg border border-amber-100 bg-amber-50/70 px-3 py-2">
            <p class="text-amber-700/80">错误</p>
            <p class="mt-1 font-semibold text-amber-700">{{ failedCount }} 份</p>
          </div>
        </div>

        <p v-if="scanMsg" class="mt-3 text-xs" :class="scanError ? 'text-[var(--gov-danger)]' : 'text-[var(--gov-success)]'">{{ scanMsg }}</p>
      </div>
    </div>

    <div v-if="hasQueueItems && !processing" class="px-4 pb-2">
      <div class="mb-2 flex items-center justify-between">
        <div>
          <span class="text-xs font-medium gov-muted">
            待提交明细（{{ queue.length + pathQueue.length }} 份 / {{ dirGroupedFiles.length + dirGroupedPathFiles.length }} 个目录）
          </span>
          <p class="mt-1 text-[11px] gov-muted">点击目录名展开文件列表；可整个目录删除。</p>
        </div>
        <div class="flex items-center gap-2">
          <button class="text-xs text-[var(--gov-danger)] hover:brightness-95" @click="clearQueue">清空全部</button>
        </div>
      </div>

      <div class="max-h-64 space-y-1.5 overflow-y-auto pr-0.5">
        <!-- Browser-selected files grouped by directory -->
        <div
          v-for="group in dirGroupedFiles"
          :key="group.dir"
          class="overflow-hidden rounded-lg border border-[var(--gov-border)]"
        >
          <!-- Directory header row -->
          <div class="flex items-center bg-slate-50 px-3 py-2">
            <button class="flex min-w-0 flex-1 items-center gap-1.5 text-left" @click="toggleDirExpand(group.dir)">
              <svg
                class="h-3 w-3 flex-shrink-0 text-[var(--gov-primary)] transition-transform duration-150"
                :class="expandedDirs.has(group.dir) ? 'rotate-90' : ''"
                fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"
              ><path d="M9 18l6-6-6-6"/></svg>
              <svg class="h-3.5 w-3.5 flex-shrink-0 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>
              </svg>
              <span class="min-w-0 flex-1 truncate text-xs font-medium text-[var(--gov-text)]">{{ group.dir }}</span>
              <span class="ml-1.5 shrink-0 text-[11px] text-[var(--gov-text-muted)]">{{ group.files.length }} 份 · {{ formatSize(group.totalSize) }}</span>
            </button>
            <button
              class="ml-2 shrink-0 rounded px-2 py-0.5 text-[11px] text-red-500 hover:bg-red-50 hover:text-red-600"
              @click.stop="removeDirFiles(group.dir)"
            >删除目录</button>
          </div>
          <!-- Files within directory (only when expanded) -->
          <div v-if="expandedDirs.has(group.dir)" class="divide-y divide-[var(--gov-border)]">
            <div
              v-for="item in group.files"
              :key="item.idx"
              class="flex items-center bg-white px-3 py-1.5 text-xs"
            >
              <div class="min-w-0 flex-1 truncate pl-5 text-[var(--gov-text)]">
                {{ item.file.name }}
                <span class="ml-1.5 text-[var(--gov-text-muted)]">{{ formatSize(item.file.size) }}</span>
              </div>
              <button class="ml-2 shrink-0 text-[var(--gov-text-muted)] hover:text-red-500" @click="removeFile(item.idx)">移除</button>
            </div>
          </div>
        </div>

        <!-- Server-side path files grouped by directory -->
        <div
          v-for="group in dirGroupedPathFiles"
          :key="'p_' + group.dir"
          class="overflow-hidden rounded-lg border border-[var(--gov-border)]"
        >
          <div class="flex items-center bg-[var(--gov-primary-soft)] px-3 py-2">
            <button class="flex min-w-0 flex-1 items-center gap-1.5 text-left" @click="toggleDirExpand('p_'+group.dir)">
              <svg
                class="h-3 w-3 flex-shrink-0 text-[var(--gov-primary)] transition-transform duration-150"
                :class="expandedDirs.has('p_'+group.dir) ? 'rotate-90' : ''"
                fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"
              ><path d="M9 18l6-6-6-6"/></svg>
              <svg class="h-3.5 w-3.5 flex-shrink-0 text-[var(--gov-primary)]" fill="currentColor" viewBox="0 0 20 20">
                <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>
              </svg>
              <span class="min-w-0 flex-1 truncate text-xs font-medium text-[var(--gov-text)]">{{ group.dir }}</span>
              <span class="ml-1.5 shrink-0 text-[11px] text-[var(--gov-text-muted)]">{{ group.files.length }} 份 · {{ formatSize(group.totalSize) }}（路径导入）</span>
            </button>
          </div>
          <div v-if="expandedDirs.has('p_'+group.dir)" class="divide-y divide-[var(--gov-border)]">
            <div
              v-for="item in group.files"
              :key="item.idx"
              class="flex items-center bg-white px-3 py-1.5 text-xs"
            >
              <div class="min-w-0 flex-1 truncate pl-5 text-[var(--gov-text)]">
                {{ item.file.rel_path }}
                <span class="ml-1.5 text-[var(--gov-text-muted)]">{{ formatSize(item.file.size) }}</span>
              </div>
              <button class="ml-2 shrink-0 text-[var(--gov-text-muted)] hover:text-red-500" @click="removePathFile(item.idx)">移除</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="hasQueueItems || processing || batchDone" class="space-y-3 px-4 pb-4">
      <div v-if="hasQueueItems && !processing && !batchDone" class="flex items-center space-x-2">
        <label class="text-xs gov-muted">定时开始</label>
        <input
          v-model="scheduledTime"
          type="datetime-local"
          class="flex-1 rounded-md border border-[var(--gov-border)] px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
        />
        <button v-if="scheduledTime" class="text-xs gov-muted hover:text-[var(--gov-text)]" @click="scheduledTime = ''">清除</button>
      </div>

      <button
        v-if="!batchDone"
        class="w-full rounded-lg py-2 text-sm font-medium text-white transition-all"
        :class="processing ? 'cursor-not-allowed bg-slate-400' : cc.btn"
        :disabled="processing || !hasQueueItems"
        @click="startBatch"
      >
        {{ actionButtonLabel }}
      </button>

      <div v-if="batchDone && lastBatchId && !processing" class="space-y-2">
        <div
          v-if="!enableAiMerge"
          class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700"
        >
          任务已提交并处理完成，可在右侧任务界面查看每个文件的状态和结果。
        </div>

        <div v-if="enableAiMerge" class="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs" :class="aiMerging ? 'border-violet-200 bg-violet-50' : aiMergeError ? 'border-amber-200 bg-amber-50' : aiMergeResult ? 'border-emerald-200 bg-emerald-50' : 'border-[var(--gov-border)] bg-[var(--gov-surface-muted)]'">
          <span v-if="aiMerging" class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-violet-400 border-t-transparent"></span>
          <span v-else-if="aiMergeResult" class="text-emerald-600">&#10003;</span>
          <span v-else-if="aiMergeError" class="text-amber-600">&#9888;</span>
          <span class="flex-1" :class="aiMerging ? 'text-violet-700' : aiMergeError ? 'text-amber-700' : aiMergeResult ? 'text-emerald-700' : 'text-[var(--gov-text-muted)]'">
            <template v-if="aiMerging">智能整合分析中…</template>
            <template v-else-if="aiMergeError">{{ aiMergeError }}</template>
            <template v-else-if="aiMergeResult">智能整合完成，已形成 {{ mergedDocuments.length || aiMergeResult.summary.documents_count }} 份归并文件建议。</template>
            <template v-else>等待智能整合…</template>
          </span>
          <button
            v-if="aiMergeResult && !aiMerging"
            class="shrink-0 rounded bg-emerald-600 px-2 py-1 text-[11px] font-medium text-white hover:brightness-105"
            @click="mergeModalVisible = true"
          >
            查看结果
          </button>
          <button
            v-if="aiMergeError && !aiMerging"
            class="shrink-0 rounded bg-amber-600 px-2 py-1 text-[11px] font-medium text-white hover:brightness-105"
            @click="runAiMergeExtract"
          >
            重试
          </button>
        </div>

        <div v-if="enableAiMerge" class="grid grid-cols-2 gap-2">
          <button class="rounded-lg bg-emerald-700 py-1.5 text-xs font-medium text-white transition hover:brightness-105" @click="doExportExcel">
            导出本次归档
          </button>
          <button
            class="rounded-lg bg-slate-700 py-1.5 text-xs font-medium text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:bg-slate-300"
            :disabled="!lastBatchId"
            @click="openBatchInsights"
          >
            质量概览
          </button>
        </div>
      </div>
    </div>

    <div v-if="aiMergeResult && mergeModalVisible" class="gov-modal-backdrop" @click.self="mergeModalVisible = false">
      <div class="gov-modal-panel max-h-[85vh] w-full max-w-5xl overflow-hidden">
        <div class="flex items-center justify-between border-b border-[var(--gov-border)] px-5 py-3">
          <div>
            <h3 class="text-sm font-semibold text-[var(--gov-text)]">智能整合结果</h3>
            <p class="text-xs gov-muted">已生成可核对的归并文件和字段建议。</p>
          </div>
          <button class="rounded px-2 py-1 text-xs gov-muted hover:bg-slate-100" @click="mergeModalVisible = false">关闭</button>
        </div>

        <div class="max-h-[calc(85vh-64px)] space-y-4 overflow-y-auto px-5 py-4">
          <div class="grid grid-cols-2 gap-2 text-xs text-[var(--gov-text-muted)] md:grid-cols-4">
            <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">原始材料：{{ aiMergeResult.summary.total_tasks }}</div>
            <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">可分析材料：{{ aiMergeResult.summary.eligible_tasks }}</div>
            <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">判定分组：{{ aiMergeResult.summary.groups_count }}</div>
            <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">归并文件：{{ aiMergeResult.summary.documents_count }}</div>
          </div>

          <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-3">
            <div class="mb-2 flex items-center justify-between">
              <p class="text-xs font-semibold text-[var(--gov-text)]">统计概览</p>
              <div class="flex items-center space-x-2">
                <button
                  class="rounded border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-text)] hover:bg-slate-50"
                  :disabled="aiMerging"
                  @click="recomputeAiMerge"
                >
                  {{ aiMerging ? '分析中…' : '重新分析' }}
                </button>
                <button
                  class="rounded bg-[var(--gov-primary)] px-2 py-1 text-[11px] text-white hover:brightness-105"
                  @click="openBatchInsights"
                >
                  查看质量概览
                </button>
                <button
                  class="rounded bg-white px-2 py-1 text-[11px] text-[var(--gov-primary)] ring-1 ring-[var(--gov-border)] hover:bg-[var(--gov-primary-soft)]"
                  @click="openBoundaryReview"
                >
                  人工校核归并
                </button>
              </div>
            </div>
            <p v-if="aiMetricsLoading" class="text-xs gov-muted">质量分析中…</p>
            <p v-else-if="aiMetricsError" class="text-xs text-[var(--gov-danger)]">{{ aiMetricsError }}</p>
            <div v-else-if="operationalMetrics" class="grid grid-cols-2 gap-2 text-xs text-[var(--gov-text)] md:grid-cols-4">
              <div class="rounded bg-white px-2 py-1">字段完整率：{{ pct(operationalMetrics.field_fill_rate?.recommended) }}</div>
              <div class="rounded bg-white px-2 py-1">待核对率：{{ pct(operationalMetrics.conflict_rate) }}</div>
              <div class="rounded bg-white px-2 py-1">整合可信度：{{ pct(operationalMetrics.avg_same_document_confidence) }}</div>
              <div class="rounded bg-white px-2 py-1">双路一致度：{{ pct(operationalMetrics.avg_rule_llm_agreement) }}</div>
            </div>
          </div>

          <div
            v-for="documentItem in mergedDocuments"
            :key="documentItem.key"
            class="rounded-lg border border-[var(--gov-border)] bg-white p-4"
          >
            <div class="mb-2 flex items-center justify-between">
              <div>
                <div class="text-sm font-semibold text-[var(--gov-text)]">归并文件 {{ documentItem.index }}</div>
                <p class="mt-1 text-xs gov-muted">{{ documentItem.sourceSummary }}</p>
              </div>
              <div class="text-xs gov-muted">整合可信度：{{ documentItem.sameDocumentConfidence.toFixed(2) }}</div>
            </div>

            <div class="mb-3 rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p class="mb-1 text-xs font-medium text-[var(--gov-text)]">归并文件名</p>
                  <p class="text-sm font-semibold text-[var(--gov-text)]">{{ documentItem.displayName }}</p>
                  <p v-if="documentItem.title" class="mt-1 text-xs gov-muted">题名建议：{{ documentItem.title }}</p>
                </div>
                <div class="text-right text-xs gov-muted">
                  <p>归并页数：{{ documentItem.mergedPageCount || documentItem.sourceCount }}</p>
                  <p>来源图片：{{ documentItem.sourceCount }} 张</p>
                </div>
              </div>

              <div v-if="documentItem.sourceBadges.length" class="mt-3 flex flex-wrap gap-2">
                <span
                  v-for="(badge, idx) in documentItem.sourceBadges"
                  :key="`${documentItem.key}-badge-${idx}`"
                  class="rounded-full border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-text-muted)]"
                >
                  {{ badge }}
                </span>
              </div>

              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  v-if="documentItem.primaryTaskId"
                  class="rounded border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-primary)] hover:bg-[var(--gov-primary-soft)]"
                  @click="openTask(documentItem.primaryTaskId)"
                >
                  {{ documentItem.sourceCount > 1 ? '查看首页' : '查看文件' }}
                </button>
                <button
                  v-for="(taskId, idx) in documentItem.taskIds"
                  :key="`${documentItem.key}-task-${taskId}`"
                  class="rounded border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-text-muted)] hover:bg-slate-50"
                  @click="openTask(taskId)"
                >
                  查看来源页 {{ idx + 1 }}
                </button>
              </div>
            </div>

            <div class="mb-3 rounded-lg border border-[var(--gov-border)] bg-[var(--gov-primary-soft)] px-3 py-2">
              <p class="mb-1 text-xs font-medium text-[var(--gov-primary)]">判定依据</p>
              <p class="text-xs leading-5 text-[var(--gov-text)]">{{ documentItem.decisionReasons.join('；') || '-' }}</p>
            </div>

            <div v-if="documentItem.document" class="rounded-lg border border-emerald-100 bg-emerald-50/50 px-3 py-3">
              <div class="mb-2 flex items-center justify-between text-xs text-emerald-800">
                <span>合并页数：{{ documentItem.mergedPageCount }}</span>
                <span>协同一致度：{{ documentItem.agreementRatio.toFixed(2) }}</span>
              </div>
              <div class="grid gap-1 text-xs text-[var(--gov-text)] md:grid-cols-2">
                <div
                  v-for="[field, value] in fieldEntries(documentItem.recommendedFields)"
                  :key="`${documentItem.key}-${field}`"
                  class="rounded bg-white px-2 py-1"
                >
                  <span class="gov-muted">{{ field }}：</span>
                  <span>{{ value || '-' }}</span>
                </div>
              </div>
              <p
                v-if="documentItem.conflictFields.length"
                class="mt-2 text-xs text-amber-700"
              >
                待核对字段：{{ documentItem.conflictFields.join('、') }}
              </p>
            </div>
          </div>

          <div
            v-if="aiMergeResult.summary.skipped_tasks?.length"
            class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700"
          >
            <p class="mb-1 font-medium">已跳过材料</p>
            <div v-for="task in aiMergeResult.summary.skipped_tasks" :key="`skip-${task.task_id}`">
              #{{ task.task_id }} {{ task.filename }}（{{ task.reason }}）
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useBatchUpload } from '../composables/useBatchUpload.js'
import { buildMergedDocumentViews } from '../utils/mergeDocumentDisplay.js'

const props = defineProps({
  model: Object,
  enableAiMerge: {
    type: Boolean,
    default: true,
  },
})
const emit = defineEmits(['start-batch', 'batch-completed', 'view-result'])
const router = useRouter()
const enableAiMerge = computed(() => props.enableAiMerge !== false)

const COLOR_MAP = {
  cyan: {
    headerBg: 'bg-cyan-50 border-cyan-100',
    iconBg: 'bg-cyan-600',
    btn: 'bg-cyan-700 hover:brightness-105',
    progressBar: 'bg-cyan-600',
  },
  indigo: {
    headerBg: 'bg-indigo-50 border-indigo-100',
    iconBg: 'bg-indigo-600',
    btn: 'bg-indigo-700 hover:brightness-105',
    progressBar: 'bg-indigo-600',
  },
  blue: {
    headerBg: 'bg-blue-50 border-blue-100',
    iconBg: 'bg-[var(--gov-primary)]',
    btn: 'bg-[var(--gov-primary)] hover:brightness-105',
    progressBar: 'bg-[var(--gov-primary)]',
  },
  green: {
    headerBg: 'bg-emerald-50 border-emerald-100',
    iconBg: 'bg-emerald-700',
    btn: 'bg-emerald-700 hover:brightness-105',
    progressBar: 'bg-emerald-700',
  },
}

const cc = computed(() => COLOR_MAP[props.model.color] || COLOR_MAP.blue)
const dragover = ref(false)
const fileInput = ref(null)
const folderInput = ref(null)
const mergeModalVisible = ref(false)

const {
  batchDone,
  aiMergeError,
  aiMergeResult,
  aiMerging,
  aiMetrics,
  aiMetricsError,
  aiMetricsLoading,
  clearQueue,
  displayQueueSummary,
  doExportExcel,
  doExportInitExcel,
  completedCount,
  excelPath,
  failedCount,
  folderPath,
  formatSize,
  importFromPath,
  importMessage,
  importProgressPercent,
  importStage,
  isAdvancedView,
  lastBatchId,
  onDrop,
  onFileSelect,
  onFolderSelect,
  outputDir,
  pathQueue,
  pendingCount,
  processing,
  processingCount,
  queue,
  queueExpanded,
  removeFile,
  removePathFile,
  runAiMergeExtract,
  scanError,
  scanMsg,
  scanning,
  scheduledTime,
  startBatch,
  totalCount,
  toggleQueueExpanded,
  toggleViewMode,
} = useBatchUpload(props.model.mode, {
  enableAiMerge: props.enableAiMerge,
  onSubmitted: () => emit('start-batch'),
  onCompleted: (payload) => emit('batch-completed', payload),
})

watch(aiMergeResult, (val) => {
  mergeModalVisible.value = !!val
})

const mergedDocuments = computed(() => buildMergedDocumentViews(aiMergeResult.value))

const operationalMetrics = computed(() => aiMetrics.value?.operational_metrics || null)
const hasQueueItems = computed(() => Boolean(queue.value.length || pathQueue.value.length))
const hasImportActivity = computed(() => hasQueueItems.value || processing.value || batchDone.value || importStage.value !== 'idle')
const previewQueueFiles = computed(() => (queueExpanded.value ? queue.value : queue.value.slice(0, 2)))
const previewPathBaseIndex = computed(() => (queueExpanded.value ? 0 : 0))
const previewPathFiles = computed(() => (queueExpanded.value ? pathQueue.value : pathQueue.value.slice(0, 3)))
const hiddenQueueCount = computed(() => {
  const shownCount = previewQueueFiles.value.length + previewPathFiles.value.length
  return Math.max(0, queue.value.length + pathQueue.value.length - shownCount)
})
const showQueueToggle = computed(() => queue.value.length + pathQueue.value.length > 5)

// ── Directory-grouped preview ──────────────────────────────────────────────
const expandedDirs = ref(new Set())

function toggleDirExpand(dir) {
  const s = new Set(expandedDirs.value)
  s.has(dir) ? s.delete(dir) : s.add(dir)
  expandedDirs.value = s
}

const dirGroupedFiles = computed(() => {
  const groups = {}
  queue.value.forEach((file, idx) => {
    const relPath = file.webkitRelativePath || file._relativePath || file.name
    const parts = relPath.split('/')
    const key = parts.length > 1 ? parts.slice(0, -1).join('/') : '（独立文件）'
    if (!groups[key]) groups[key] = []
    groups[key].push({ file, idx })
  })
  return Object.entries(groups).map(([dir, files]) => ({
    dir,
    files,
    totalSize: files.reduce((s, f) => s + (f.file.size || 0), 0),
  }))
})

const dirGroupedPathFiles = computed(() => {
  const groups = {}
  pathQueue.value.forEach((file, idx) => {
    const parts = (file.rel_path || '').split('/')
    const key = parts.length > 1 ? parts.slice(0, -1).join('/') : '（根目录）'
    if (!groups[key]) groups[key] = []
    groups[key].push({ file, idx })
  })
  return Object.entries(groups).map(([dir, files]) => ({
    dir,
    files,
    totalSize: files.reduce((s, f) => s + (f.file.size || 0), 0),
  }))
})

function removeDirFiles(dir) {
  const group = dirGroupedFiles.value.find(g => g.dir === dir)
  if (!group) return
  // Remove highest index first so lower indices stay valid
  const indices = group.files.map(f => f.idx).sort((a, b) => b - a)
  indices.forEach(idx => removeFile(idx))
  const s = new Set(expandedDirs.value)
  s.delete(dir)
  expandedDirs.value = s
}
const activeProcessingCount = computed(() => processingCount.value + pendingCount.value)

const stageMeta = computed(() => {
  switch (importStage.value) {
    case 'scanning':
      return {
        eyebrow: '目录整理',
        title: '正在整理导入材料',
        description: '整理材料中。',
      }
    case 'ready':
      return {
        eyebrow: '待开始处理',
        title: '材料已整理完成',
        description: '可直接提交。',
      }
    case 'uploading':
      return {
        eyebrow: '提交中',
        title: '正在提交任务',
        description: '上传并入队。',
      }
    case 'processing':
      return {
        eyebrow: '处理中',
        title: '后台正在处理任务',
        description: '后台处理中。',
      }
    case 'completed':
      return {
        eyebrow: '完成',
        title: '本次任务已完成',
        description: '可查看结果。',
      }
    default:
      return {
        eyebrow: '任务提交',
        title: '等待选择材料',
        description: '选择材料后提交。',
      }
  }
})

const actionButtonLabel = computed(() => {
  if (processing.value) {
    if (importStage.value === 'uploading') return '任务提交中…'
    if (importStage.value === 'processing') return '任务处理中…'
    return '处理中…'
  }
  return scheduledTime.value ? '定时提交任务' : '提交任务'
})

function fieldEntries(fields) {
  return Object.entries(fields || {})
}

function openTask(taskId) {
  if (!taskId) return
  emit('view-result', {
    taskId,
    batchId: String(lastBatchId.value || '').trim(),
  })
}

function pct(value) {
  const numeric = Number(value || 0)
  return `${(numeric * 100).toFixed(1)}%`
}

function openBatchInsights() {
  if (!lastBatchId.value) return
  router.push(`/batch-insights/${encodeURIComponent(lastBatchId.value)}`)
}

function openBoundaryReview() {
  if (!lastBatchId.value) return
  router.push({
    path: `/batch-insights/${encodeURIComponent(lastBatchId.value)}`,
    query: { tab: 'truth' },
  })
}

async function recomputeAiMerge() {
  await runAiMergeExtract({ forceRefresh: true })
}

async function handleDrop(event) {
  dragover.value = false
  await onDrop(event)
}
</script>
