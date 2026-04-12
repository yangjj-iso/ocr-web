<template>
  <main id="batch-workbench" class="min-h-[calc(100vh-64px)] overflow-y-auto bg-[var(--gov-surface-muted)] p-6">
    <div class="mx-auto max-w-[1600px] space-y-5">
      <section class="gov-panel overflow-hidden">
        <div class="border-b border-[var(--gov-border)] bg-white px-5 py-5">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p class="text-xs font-semibold tracking-[0.14em] text-[var(--gov-primary)]">签录工作台</p>
              <h2 class="mt-2 text-xl font-semibold text-[var(--gov-text)]">提交任务</h2>
              <p class="mt-2 max-w-3xl text-sm leading-6 gov-muted">
                只需要选择材料并提交任务，系统会统一进入后台队列处理，无需再选择综合识别、版式识别或文本识别。
              </p>
            </div>

            <div v-if="myQuota && !authState.isAdmin.value" class="w-full max-w-sm rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-3">
              <div class="mb-2 flex items-center justify-between">
                <span class="text-xs font-semibold text-[var(--gov-text)]">本月配额</span>
                <span class="text-xs gov-muted">{{ myQuota.quota_used }} / {{ myQuota.quota_total }}</span>
              </div>
              <div class="h-2 overflow-hidden rounded-full bg-white">
                <div
                  class="h-full rounded-full transition-all"
                  :class="quotaPercent >= 90 ? 'bg-red-400' : quotaPercent >= 70 ? 'bg-amber-400' : 'bg-emerald-500'"
                  :style="{ width: quotaPercent + '%' }"
                />
              </div>
              <p class="mt-2 text-[11px] gov-muted">单次提交上限 {{ myQuota.quota_per_import }} 份材料</p>
            </div>
          </div>

          <div class="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div
              v-for="item in taskStatusGuide"
              :key="item.key"
              class="rounded-lg border px-4 py-3"
              :class="item.cardClass"
            >
              <div class="flex items-center gap-2">
                <span class="h-2 w-2 rounded-full" :class="item.dotClass"></span>
                <span class="text-sm font-semibold text-[var(--gov-text)]">{{ item.label }}</span>
              </div>
              <p class="mt-2 text-xs leading-5 gov-muted">{{ item.description }}</p>
            </div>
          </div>
        </div>
      </section>

      <div class="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(440px,0.9fr)]">
        <BufferZone
          :model="taskSubmitModel"
          :enable-ai-merge="false"
          @start-batch="handleStartBatch"
          @batch-completed="handleBatchCompleted"
          @view-result="handleViewResult"
        />

        <TaskBoard
          ref="taskBoardRef"
          @view-result="handleViewResult"
          @batch-context="handleHistoryBatchContext"
          @view-batch="handleTaskBoardViewBatch"
        />
      </div>
    </div>
  </main>

  <div v-if="false" class="flex h-[calc(100vh-64px)] gap-0">
    <aside class="flex w-[280px] flex-shrink-0 flex-col border-r border-[var(--gov-border)] bg-white">
      <nav class="flex flex-1 flex-col overflow-y-auto">
        <div class="border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-5 py-4">
          <p class="text-xs font-semibold tracking-[0.14em] text-[var(--gov-primary)]">功能模块</p>
        </div>

        <div class="flex-1 space-y-1 p-3">
          <button
            v-for="model in models"
            :key="model.mode"
            class="group flex w-full items-center gap-3 rounded-lg px-3 py-4 text-left transition-all"
            :class="selectedTab === model.mode
              ? sidebarActiveClass(model.color)
              : 'hover:bg-slate-50'"
            @click="selectedTab = model.mode"
          >
            <div
              class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors"
              :class="selectedTab === model.mode
                ? sidebarIconClass(model.color)
                : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'"
            >
              <svg v-if="model.icon === 'brain'" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
              <svg v-else-if="model.icon === 'layout'" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-[var(--gov-text)]">{{ model.name }}</span>
                <span
                  v-if="model.badge"
                  class="rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none"
                  :class="selectedTab === model.mode
                    ? 'bg-white/80 text-[var(--gov-text)]'
                    : badgeClass(model.color)"
                >{{ model.badge }}</span>
              </div>
              <p class="mt-0.5 truncate text-xs gov-muted">{{ model.desc }}</p>
            </div>
          </button>
        </div>

        <div class="mx-3 border-t border-[var(--gov-border)]"></div>

        <div class="space-y-1 p-3">
          <button
            class="group flex w-full items-center gap-3 rounded-lg px-3 py-4 text-left transition-all"
            :class="selectedTab === 'assistant'
              ? 'bg-violet-50 ring-1 ring-violet-200'
              : 'hover:bg-slate-50'"
            @click="onAssistantTabClick"
          >
            <div
              class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors"
              :class="selectedTab === 'assistant'
                ? 'bg-violet-600 text-white'
                : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-[var(--gov-text)]">智能辅助</span>
                <span
                  class="rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none"
                  :class="capabilityBadgeClass"
                >{{ capabilityBadgeText }}</span>
              </div>
              <p class="mt-0.5 truncate text-xs gov-muted">批次整合与质量概览</p>
            </div>
          </button>

          <button
            class="group flex w-full items-center gap-3 rounded-lg px-3 py-4 text-left transition-all"
            :class="selectedTab === 'history'
              ? 'bg-slate-100 ring-1 ring-slate-200'
              : 'hover:bg-slate-50'"
            @click="selectedTab = 'history'"
          >
            <div
              class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors"
              :class="selectedTab === 'history'
                ? 'bg-[var(--gov-primary)] text-white'
                : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div class="min-w-0 flex-1">
              <span class="text-sm font-semibold text-[var(--gov-text)]">处理记录</span>
              <p class="mt-0.5 truncate text-xs gov-muted">按提交快速回看处理记录</p>
            </div>
          </button>

          <button
            class="group flex w-full items-center gap-3 rounded-lg px-3 py-4 text-left transition-all"
            :class="selectedTab === 'assigned'
              ? 'bg-green-50 ring-1 ring-green-200'
              : 'hover:bg-slate-50'"
            @click="selectedTab = 'assigned'; loadAssignedTasks()"
          >
            <div
              class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors"
              :class="selectedTab === 'assigned'
                ? 'bg-emerald-600 text-white'
                : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-[var(--gov-text)]">我的任务</span>
                <span v-if="assignedPending > 0" class="rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-600 leading-none">{{ assignedPending }}</span>
              </div>
              <p class="mt-0.5 truncate text-xs gov-muted">管理员分配的待处理批次</p>
            </div>
          </button>
        </div>
      </nav>

      <!-- Operator quota bar at sidebar bottom -->
      <div v-if="myQuota && !authState.isAdmin.value" class="border-t border-[var(--gov-border)] p-3">
        <p class="mb-1 text-[10px] font-semibold text-[var(--gov-text-muted)] uppercase tracking-wide">本月配额</p>
        <div class="h-1.5 rounded-full bg-slate-100 overflow-hidden">
          <div
            class="h-full rounded-full transition-all"
            :class="quotaPercent >= 90 ? 'bg-red-400' : quotaPercent >= 70 ? 'bg-amber-400' : 'bg-emerald-500'"
            :style="{ width: quotaPercent + '%' }"
          />
        </div>
        <p class="mt-1 text-[10px] text-[var(--gov-text-muted)]">
          已用 {{ myQuota.quota_used }} / {{ myQuota.quota_total }}，单次上限 {{ myQuota.quota_per_import }}
        </p>
      </div>
    </aside>

    <main id="batch-workbench" class="min-w-0 flex-1 overflow-y-auto bg-[var(--gov-surface-muted)] p-6">
      <!-- Assigned tasks panel -->
      <div v-show="selectedTab === 'assigned'" class="gov-panel overflow-hidden">
        <div class="border-b border-[var(--gov-border)] bg-emerald-50 px-5 py-4 flex items-center justify-between">
          <div>
            <h3 class="text-lg font-semibold text-[var(--gov-text)]">我的任务</h3>
            <p class="mt-1 text-xs gov-muted">管理员分配给我的批次，点击批次 ID 可进入分析</p>
          </div>
          <button class="text-xs text-[var(--gov-primary)] hover:underline" @click="loadAssignedTasks">刷新</button>
        </div>
        <div class="bg-white">
          <div v-if="assignedLoading" class="py-10 text-center text-sm text-[var(--gov-text-muted)]">加载中…</div>
          <div v-else-if="!assignedTasks.length" class="py-10 text-center text-sm text-[var(--gov-text-muted)]">暂无分配任务</div>
          <table v-else class="w-full text-sm">
            <thead class="bg-slate-50 border-b border-[var(--gov-border)]">
              <tr>
                <th class="px-5 py-2.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">批次 ID</th>
                <th class="px-5 py-2.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">文件数</th>
                <th class="px-5 py-2.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">状态</th>
                <th class="px-5 py-2.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">备注</th>
                <th class="px-5 py-2.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">分配时间</th>
                <th class="px-5 py-2.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--gov-border)]">
              <tr v-for="t in assignedTasks" :key="t.id" class="hover:bg-slate-50">
                <td class="px-5 py-3 font-mono text-xs text-[var(--gov-primary)]">{{ t.batch_id }}</td>
                <td class="px-5 py-3">{{ t.file_count }}</td>
                <td class="px-5 py-3">
                  <span :class="assignedStatusClass(t.status)" class="rounded-full px-2 py-0.5 text-xs font-medium">{{ assignedStatusLabel(t.status) }}</span>
                </td>
                <td class="px-5 py-3 text-xs text-[var(--gov-text-muted)]">{{ t.note || '—' }}</td>
                <td class="px-5 py-3 text-xs text-[var(--gov-text-muted)] whitespace-nowrap">{{ fmtAssignDate(t.created_at) }}</td>
                <td class="px-5 py-3">
                  <button
                    class="text-xs text-[var(--gov-primary)] hover:underline"
                    @click="openAssignedBatch(t.batch_id)"
                  >查看批次</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <BufferZone
        v-for="model in models"
        v-show="selectedTab === model.mode"
        :key="model.mode"
        :model="model"
        @start-batch="handleStartBatch"
        @batch-completed="handleBatchCompleted"
        @view-result="handleViewResult"
      />

      <div v-show="selectedTab === 'assistant'" class="space-y-5">
        <div class="gov-panel overflow-hidden">
          <div class="border-b border-[var(--gov-border)] bg-violet-50 px-5 py-4">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="text-lg font-semibold text-[var(--gov-text)]">智能辅助</h3>
                <p class="mt-1 text-sm gov-muted">{{ assistantHeaderMessage }}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class="rounded-full px-3 py-1 text-xs font-medium" :class="capabilityBadgeClass">
                  {{ capabilityBadgeText }}
                </span>
                <span v-if="latestBatchId" class="rounded-full border border-[var(--gov-border)] bg-white px-3 py-1 text-xs text-[var(--gov-text-muted)]">
                  当前批次：{{ latestBatchId }}
                </span>
              </div>
            </div>
          </div>

          <div class="bg-white p-5">
            <div class="grid gap-4 md:grid-cols-3">
              <article
                v-for="item in assistantItems"
                :key="item.title"
                class="cursor-pointer rounded-xl border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-5 py-5 transition hover:border-violet-200 hover:bg-violet-50/50"
                @click="item.action?.()"
              >
                <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
                  <svg v-if="item.icon === 'merge'" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                  <svg v-else-if="item.icon === 'chart'" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                  <svg v-else class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>
                </div>
                <p class="text-sm font-semibold text-[var(--gov-text)]">{{ item.title }}</p>
                <p class="mt-1 text-xs leading-5 gov-muted">{{ item.description }}</p>
                <p class="mt-3 text-[11px] leading-5 text-[var(--gov-text-muted)]">{{ item.hint }}</p>
                <button
                  class="mt-4 rounded-lg px-3 py-2 text-xs font-medium transition"
                  :class="item.buttonClass"
                  @click.stop="item.action?.()"
                >
                  {{ item.ctaLabel }}
                </button>
              </article>
            </div>

            <div
              v-if="assistantPreviewWarning"
              class="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700"
            >
              {{ assistantPreviewWarning }}
            </div>

            <div
              v-if="assistantPreviewError"
              class="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-600"
            >
              {{ assistantPreviewError }}
            </div>

            <div v-if="hasBatchContext" class="mt-5 grid gap-4 xl:grid-cols-[1.15fr,0.85fr]">
              <div class="space-y-4">
                <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <div
                    v-for="card in assistantSummaryCards"
                    :key="card.label"
                    class="rounded-xl border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-3"
                  >
                    <p class="text-[11px] gov-muted">{{ card.label }}</p>
                    <p class="mt-1 text-sm font-semibold text-[var(--gov-text)]">{{ card.value }}</p>
                    <p class="mt-1 text-[11px] text-[var(--gov-text-muted)]">{{ card.caption }}</p>
                  </div>
                </div>

                <section class="rounded-xl border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-4">
                  <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h4 class="text-sm font-semibold text-[var(--gov-text)]">智能整合预览</h4>
                      <p class="mt-1 text-xs gov-muted">当前页直接预览归并建议，深入校核可进入完整分析中心。</p>
                    </div>
                    <div class="flex items-center gap-2">
                      <button
                        class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-xs font-medium text-[var(--gov-text)] transition hover:bg-slate-50"
                        :disabled="assistantPreviewLoading"
                        @click="loadAssistantPreview({ forceRefresh: true })"
                      >
                        {{ assistantPreviewLoading ? '刷新中…' : '刷新预览' }}
                      </button>
                      <button
                        class="rounded-lg bg-violet-600 px-3 py-2 text-xs font-medium text-white transition hover:brightness-105"
                        @click="openBatchInsights('overview')"
                      >
                        查看完整整合
                      </button>
                    </div>
                  </div>

                  <div
                    v-if="assistantPreviewLoading && !assistantHasPreview"
                    class="mt-4 rounded-lg border border-dashed border-[var(--gov-border)] bg-white px-4 py-6 text-sm text-[var(--gov-text-muted)]"
                  >
                    正在加载当前批次的整合建议...
                  </div>
                  <div v-else-if="assistantMergedDocuments.length" class="mt-4 space-y-3">
                    <div
                      v-for="documentItem in assistantMergedDocuments"
                      :key="documentItem.key"
                      class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-3"
                    >
                      <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0 flex-1">
                          <p class="text-sm font-semibold text-[var(--gov-text)]">
                            {{ documentItem.displayName }}
                          </p>
                          <p v-if="documentItem.title" class="mt-1 text-xs text-[var(--gov-text-muted)]">
                            题名建议：{{ documentItem.title }}
                          </p>
                          <p class="mt-2 text-[11px] text-[var(--gov-text-muted)]">
                            {{ documentItem.sourceSummary }} · 归并页数 {{ documentItem.mergedPageCount || documentItem.sourceCount }}
                          </p>
                        </div>
                        <button
                          v-if="documentItem.primaryTaskId"
                          class="rounded-lg border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-primary)] transition hover:bg-[var(--gov-primary-soft)]"
                          @click="handleViewResult(documentItem.primaryTaskId)"
                        >
                          查看材料
                        </button>
                      </div>
                      <div class="mt-3 flex flex-wrap gap-2 text-[11px] text-[var(--gov-text-muted)]">
                        <span class="rounded-full border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-2 py-1">
                          归并置信度 {{ decimalText(documentItem.sameDocumentConfidence) }}
                        </span>
                        <span
                          v-if="documentItem.conflictFields.length"
                          class="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-amber-700"
                        >
                          待核对：{{ documentItem.conflictFields.join('、') }}
                        </span>
                        <span
                          v-else
                          class="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-emerald-700"
                        >
                          当前无字段冲突
                        </span>
                      </div>
                    </div>
                  </div>
                  <p
                    v-else
                    class="mt-4 rounded-lg border border-dashed border-[var(--gov-border)] bg-white px-4 py-6 text-sm text-[var(--gov-text-muted)]"
                  >
                    当前批次还没有可展示的整合预览，刷新后会自动尝试生成。
                  </p>
                </section>

                <section class="rounded-xl border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-4">
                  <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h4 class="text-sm font-semibold text-[var(--gov-text)]">质量摘要</h4>
                      <p class="mt-1 text-xs gov-muted">把归并质量和字段质量先浓缩在工作台里，便于快速判断是否需要深入复核。</p>
                    </div>
                    <button
                      class="rounded-lg bg-white px-3 py-2 text-xs font-medium text-[var(--gov-text)] ring-1 ring-[var(--gov-border)] transition hover:bg-slate-50"
                      @click="openBatchInsights('metrics')"
                    >
                      进入质量概览
                    </button>
                  </div>

                  <div v-if="assistantMetrics" class="mt-4 grid gap-3 sm:grid-cols-2">
                    <div class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-3">
                      <p class="text-[11px] gov-muted">推荐字段完整率</p>
                      <p class="mt-1 text-sm font-semibold text-[var(--gov-text)]">{{ pct(assistantMetrics.field_fill_rate?.recommended) }}</p>
                      <p class="mt-1 text-[11px] text-[var(--gov-text-muted)]">越高说明推荐字段越完整。</p>
                    </div>
                    <div class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-3">
                      <p class="text-[11px] gov-muted">字段冲突率</p>
                      <p class="mt-1 text-sm font-semibold text-[var(--gov-text)]">{{ pct(assistantMetrics.conflict_rate) }}</p>
                      <p class="mt-1 text-[11px] text-[var(--gov-text-muted)]">越低说明同一文档内字段分歧越少。</p>
                    </div>
                    <div class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-3">
                      <p class="text-[11px] gov-muted">同文档平均置信度</p>
                      <p class="mt-1 text-sm font-semibold text-[var(--gov-text)]">{{ pct(assistantMetrics.avg_same_document_confidence) }}</p>
                      <p class="mt-1 text-[11px] text-[var(--gov-text-muted)]">衡量分页归并的稳定程度。</p>
                    </div>
                    <div class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-3">
                      <p class="text-[11px] gov-muted">规则/智能一致度</p>
                      <p class="mt-1 text-sm font-semibold text-[var(--gov-text)]">{{ pct(assistantMetrics.avg_rule_llm_agreement) }}</p>
                      <p class="mt-1 text-[11px] text-[var(--gov-text-muted)]">越高说明推荐字段越可信。</p>
                    </div>
                  </div>
                  <p
                    v-else
                    class="mt-4 rounded-lg border border-dashed border-[var(--gov-border)] bg-white px-4 py-6 text-sm text-[var(--gov-text-muted)]"
                  >
                    质量摘要会在整合预览可用后一起展示。
                  </p>
                </section>
              </div>

              <section class="rounded-xl border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-4">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h4 class="text-sm font-semibold text-[var(--gov-text)]">快捷问答</h4>
                    <p class="mt-1 text-xs gov-muted">直接围绕当前批次提问，系统优先基于批次证据返回可追溯回答。</p>
                  </div>
                  <button
                    class="rounded-lg bg-white px-3 py-2 text-xs font-medium text-[var(--gov-text)] ring-1 ring-[var(--gov-border)] transition hover:bg-slate-50"
                    @click="openBatchInsights('qa')"
                  >
                    进入完整问答
                  </button>
                </div>

                <div class="mt-4">
                  <textarea
                    v-model="assistantQaInput"
                    rows="3"
                    class="w-full rounded-xl border border-[var(--gov-border)] bg-white px-3 py-3 text-sm focus:border-violet-300 focus:outline-none focus:ring-2 focus:ring-violet-200"
                    placeholder="例如：这个批次里哪些材料需要人工复核？"
                    @keydown.enter.exact.prevent="submitAssistantQa"
                  />
                  <div class="mt-3 flex flex-wrap items-center justify-between gap-3">
                    <p class="text-[11px] text-[var(--gov-text-muted)]">问题将只围绕当前批次材料和证据回答。</p>
                    <button
                      class="rounded-lg bg-violet-600 px-4 py-2 text-xs font-medium text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:bg-violet-300"
                      :disabled="assistantQaSubmitting"
                      @click="submitAssistantQa"
                    >
                      {{ assistantQaSubmitting ? '回答中…' : '立即提问' }}
                    </button>
                  </div>
                  <p v-if="assistantQaError" class="mt-2 text-xs text-red-600">{{ assistantQaError }}</p>
                </div>

                <div v-if="assistantQaAnswer" class="mt-4 rounded-lg border border-[var(--gov-border)] bg-white px-4 py-4">
                  <div class="mb-2 flex flex-wrap items-center gap-2 text-[11px]">
                    <span class="rounded-full bg-violet-100 px-2 py-1 text-violet-700">{{ assistantLatestSourceLabel || '智能回答' }}</span>
                    <span class="rounded-full bg-blue-50 px-2 py-1 text-blue-700">支持度：{{ qaSupportText(assistantQaAnswer.support_level) }}</span>
                    <span class="rounded-full bg-slate-100 px-2 py-1 text-slate-600">置信度：{{ decimalText(assistantQaAnswer.confidence, 3) }}</span>
                  </div>
                  <p class="rounded-lg bg-[var(--gov-surface-muted)] px-3 py-3 text-sm leading-6 text-[var(--gov-text)]">
                    {{ assistantQaAnswer.answer }}
                  </p>

                  <div v-if="assistantQaAnswer.evidence?.length" class="mt-3 space-y-2">
                    <div
                      v-for="evidence in assistantQaAnswer.evidence.slice(0, 2)"
                      :key="`${evidence.task_id}-${evidence.snippet}`"
                      class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2"
                    >
                      <div class="flex items-center justify-between gap-2">
                        <p class="text-[11px] text-[var(--gov-text-muted)]">#{{ evidence.task_id }} · {{ evidence.filename }}</p>
                        <button
                          class="rounded-lg bg-white px-2 py-1 text-[11px] text-[var(--gov-primary)] ring-1 ring-[var(--gov-border)] transition hover:bg-[var(--gov-primary-soft)]"
                          @click="handleViewResult(evidence.task_id)"
                        >
                          查看材料
                        </button>
                      </div>
                      <p class="mt-2 text-xs leading-5 text-[var(--gov-text)]">{{ evidence.snippet }}</p>
                    </div>
                  </div>
                </div>

                <div class="mt-4">
                  <div class="mb-2 flex items-center justify-between">
                    <p class="text-xs font-semibold text-[var(--gov-text)]">最近问答</p>
                    <span v-if="assistantLatestSourceLabel" class="text-[11px] text-[var(--gov-text-muted)]">
                      最近来源：{{ assistantLatestSourceLabel }}
                    </span>
                  </div>
                  <div v-if="assistantQaPreview.length" class="space-y-2">
                    <button
                      v-for="item in assistantQaPreview"
                      :key="item.qa_id || item.generated_at || item.question"
                      class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-3 text-left transition hover:border-violet-200 hover:bg-violet-50/40"
                      @click="assistantQaInput = item.question"
                    >
                      <p class="text-xs font-medium text-[var(--gov-text)]">Q：{{ item.question }}</p>
                      <p class="mt-1 text-[11px] text-[var(--gov-text-muted)]">
                        {{ qaSupportText(item.support_level) }} · {{ getAiAnswerSourceLabel(item.provider) }}
                      </p>
                    </button>
                  </div>
                  <p
                    v-else
                    class="rounded-lg border border-dashed border-[var(--gov-border)] bg-white px-4 py-6 text-sm text-[var(--gov-text-muted)]"
                  >
                    当前批次还没有问答记录，输入问题后这里会显示最近的问答历史。
                  </p>
                </div>
              </section>
            </div>

            <div class="mt-5 flex items-center gap-3">
              <button
                class="rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white transition hover:brightness-105"
                @click="handleAssistantPrimaryAction"
              >
                {{ hasBatchContext ? '进入完整智能分析中心' : '先去批量处理' }}
              </button>
              <button
                v-if="hasBatchContext"
                class="rounded-lg border border-[var(--gov-border)] bg-white px-5 py-2.5 text-sm font-medium text-[var(--gov-text)] transition hover:bg-slate-50"
                @click="openBatchInsights('truth')"
              >
                进入人工校核
              </button>
              <button
                v-if="hasBatchContext"
                class="rounded-lg border border-[var(--gov-border)] bg-white px-5 py-2.5 text-sm font-medium text-[var(--gov-text)] transition hover:bg-slate-50"
                @click="selectedTab = 'vl'"
              >
                返回批量处理区
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-show="selectedTab === 'history'">
        <div class="gov-panel overflow-hidden">
          <div class="border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-5 py-4">
            <h3 class="text-lg font-semibold text-[var(--gov-text)]">处理记录</h3>
            <p class="mt-1 text-xs gov-muted">每次提交算作一次任务，按提交快速回看处理结果</p>
          </div>
          <div class="bg-white p-5">
            <HistoryList ref="historyRef" @view-result="handleViewResult" @batch-context="handleHistoryBatchContext" @view-batch="handleHistoryViewBatch" />
          </div>
        </div>
      </div>
    </main>

    <MergeResultModal
      :visible="historyMergeVisible"
      :merge-result="historyMergeResult"
      :metrics="historyMetrics"
      :metrics-loading="historyMetricsLoading"
      :metrics-error="historyMetricsError"
      :loading-merge="historyMergeLoading"
      :merge-error="historyMergeError"
      :refreshing="historyMergeRefreshing"
      @close="historyMergeVisible = false"
      @recompute="handleHistoryMergeRecompute"
      @open-batch-insights="handleHistoryMergeOpenInsights"
      @open-boundary-review="handleHistoryMergeOpenReview"
      @open-task="handleHistoryMergeOpenTask"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import BufferZone from '@/components/BufferZone.vue'
import HistoryList from '@/components/HistoryList.vue'
import MergeResultModal from '@/components/MergeResultModal.vue'
import TaskBoard from '@/components/TaskBoard.vue'
import {
  aiMergeExtractBatch,
  askBatchQuestion,
  getBatchEvaluationMetrics,
  getBatchQaHistory,
  getTaskSubmissions,
} from '@/api/ocr.js'
import { getMyQuota, getMyAssignments } from '@/api/admin.js'
import { getModeMeta } from '@/constants/uiCopy.js'
import { getAiAnswerSourceLabel, normalizeAiErrorMessage, useAiCapabilityState } from '@/composables/useAiCapabilityState.js'
import { useAuthState } from '@/composables/useAuthState.js'
import { buildMergedDocumentViews } from '@/utils/mergeDocumentDisplay.js'

const router = useRouter()
const historyRef = ref(null)
const taskBoardRef = ref(null)
const authState = useAuthState()

const taskSubmitModel = {
  mode: 'vl',
  name: '提交任务',
  desc: '统一提交档案材料，后台自动排队、处理并生成结果。',
  icon: 'cloud',
  color: 'blue',
  badge: '',
}

const taskStatusGuide = [
  {
    key: 'submitting',
    label: '提交中',
    description: '材料正在上传并写入任务队列。',
    cardClass: 'border-blue-100 bg-blue-50/70',
    dotClass: 'bg-blue-500',
  },
  {
    key: 'queued',
    label: '排队中',
    description: '任务已接收，等待后台资源调度。',
    cardClass: 'border-slate-200 bg-slate-50',
    dotClass: 'bg-slate-500',
  },
  {
    key: 'processing',
    label: '处理中',
    description: '后台正在识别和整理材料。',
    cardClass: 'border-amber-100 bg-amber-50/80',
    dotClass: 'bg-amber-500',
  },
  {
    key: 'done',
    label: '完成',
    description: '任务已完成，可查看识别结果。',
    cardClass: 'border-emerald-100 bg-emerald-50/80',
    dotClass: 'bg-emerald-500',
  },
  {
    key: 'failed',
    label: '错误',
    description: '提交或处理失败，需要检查原因后重试。',
    cardClass: 'border-red-100 bg-red-50/80',
    dotClass: 'bg-red-500',
  },
]

// ── History merge modal ───────────────────────────────────────────────────
const historyMergeVisible = ref(false)
const historyMergeResult = ref(null)
const historyMergeLoading = ref(false)
const historyMergeError = ref('')
const historyMergeRefreshing = ref(false)
const historyMetrics = ref(null)
const historyMetricsLoading = ref(false)
const historyMetricsError = ref('')
const historyMergeBatchId = ref('')

// ── Operator quota ─────────────────────────────────────────────────────────
const myQuota = ref(null)
const quotaPercent = computed(() => {
  if (!myQuota.value || myQuota.value.quota_total <= 0) return 0
  return Math.min(100, Math.round((myQuota.value.quota_used / myQuota.value.quota_total) * 100))
})

async function loadMyQuota() {
  try {
    const { data } = await getMyQuota()
    myQuota.value = data
  } catch { /* silent */ }
}

// ── Assigned tasks ─────────────────────────────────────────────────────────
const assignedTasks = ref([])
const assignedLoading = ref(false)
const assignedPending = computed(() => assignedTasks.value.filter(t => t.status === 'pending').length)

async function loadAssignedTasks() {
  assignedLoading.value = true
  try {
    const { data } = await getMyAssignments()
    assignedTasks.value = data.items || []
  } catch { /* silent */ } finally {
    assignedLoading.value = false
  }
}

function assignedStatusClass(s) {
  return {
    pending: 'bg-yellow-50 text-yellow-700',
    processing: 'bg-blue-50 text-blue-700',
    done: 'bg-green-50 text-green-700',
    failed: 'bg-red-50 text-red-600',
    cancelled: 'bg-slate-100 text-slate-500',
  }[s] || 'bg-slate-100 text-slate-500'
}
function assignedStatusLabel(s) {
  return { pending: '待处理', processing: '处理中', done: '已完成', failed: '失败', cancelled: '已取消' }[s] || s
}
function fmtAssignDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.toLocaleDateString('zh-CN')} ${d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
}
function openAssignedBatch(batchId) {
  router.push({ path: `/batch-insights/${encodeURIComponent(batchId)}` })
}
const selectedTab = ref('submit')
watch(selectedTab, (v) => sessionStorage.setItem('ocr:selectedTab', v))
const aiCapability = useAiCapabilityState()

function sidebarActiveClass(color) {
  const map = {
    indigo: 'bg-indigo-50 ring-1 ring-indigo-200',
    blue: 'bg-blue-50 ring-1 ring-blue-200',
    green: 'bg-emerald-50 ring-1 ring-emerald-200',
  }
  return map[color] || 'bg-slate-100'
}

function sidebarIconClass(color) {
  const map = {
    indigo: 'bg-indigo-600 text-white',
    blue: 'bg-[var(--gov-primary)] text-white',
    green: 'bg-emerald-700 text-white',
  }
  return map[color] || 'bg-slate-500 text-white'
}

function badgeClass(color) {
  const map = {
    indigo: 'bg-indigo-100 text-indigo-700',
    blue: 'bg-blue-100 text-blue-700',
    green: 'bg-emerald-100 text-emerald-700',
  }
  return map[color] || 'bg-slate-100 text-slate-600'
}

const models = [
  {
    mode: 'vl',
    name: getModeMeta('vl').title,
    desc: getModeMeta('vl').description,
    icon: 'brain',
    color: 'indigo',
    badge: getModeMeta('vl').badge,
  },
  {
    mode: 'layout',
    name: getModeMeta('layout').title,
    desc: getModeMeta('layout').description,
    icon: 'layout',
    color: 'blue',
    badge: getModeMeta('layout').badge,
  },
  {
    mode: 'ocr',
    name: getModeMeta('ocr').title,
    desc: getModeMeta('ocr').description,
    icon: 'type',
    color: 'green',
    badge: getModeMeta('ocr').badge,
  },
]

const hasBatchContext = computed(() => aiCapability.hasBatchContext.value)
const latestBatchId = computed(() => aiCapability.latestBatchId.value)
const assistantPreviewLoading = ref(false)
const assistantPreviewBatchId = ref('')
const assistantPreviewError = ref('')
const assistantPreviewWarning = ref('')
const assistantMergePreview = ref(null)
const assistantMetricsPreview = ref(null)
const assistantQaPreview = ref([])
const assistantQaInput = ref('')
const assistantQaSubmitting = ref(false)
const assistantQaError = ref('')
const assistantQaAnswer = ref(null)

const assistantMergedDocuments = computed(() => buildMergedDocumentViews(assistantMergePreview.value).slice(0, 3))
const assistantMetrics = computed(() => assistantMetricsPreview.value?.operational_metrics || null)
const assistantHasPreview = computed(
  () => Boolean(assistantMergedDocuments.value.length || assistantMetrics.value || assistantQaPreview.value.length || assistantQaAnswer.value)
)
const assistantLatestProvider = computed(
  () => assistantQaAnswer.value?.provider || assistantQaPreview.value[0]?.provider || ''
)
const assistantLatestSourceLabel = computed(() =>
  assistantLatestProvider.value ? getAiAnswerSourceLabel(assistantLatestProvider.value) : ''
)
const assistantHeaderMessage = computed(() => {
  if (!hasBatchContext.value) {
    return '需先完成一次批量处理，当前页才会显示智能整合、质量概览和批次问答。'
  }
  if (assistantPreviewLoading.value && !assistantHasPreview.value) {
    return '正在加载当前批次的整合预览、质量摘要和快捷问答入口。'
  }
  if (assistantHasPreview.value) {
    return '当前批次已接入智能整合、质量概览和批次问答，可直接在这里使用，也可进入完整分析中心。'
  }
  if (assistantPreviewError.value) {
    return assistantPreviewError.value
  }
  return '已识别到当前批次，可点击上方功能卡片或下方快捷区继续处理。'
})
const capabilityBadgeText = computed(() => {
  if (!hasBatchContext.value) return '尚未形成批次'
  if (assistantPreviewLoading.value) return '加载中'
  if (assistantHasPreview.value) return '功能可用'
  if (assistantPreviewError.value) return '待检查'
  return '批次已识别'
})
const capabilityBadgeClass = computed(() => {
  if (assistantHasPreview.value) {
    return 'bg-emerald-100 text-emerald-700'
  }
  if (assistantPreviewLoading.value) {
    return 'bg-blue-100 text-blue-700'
  }
  if (assistantPreviewError.value) {
    return 'bg-amber-100 text-amber-700'
  }
  return 'bg-slate-100 text-slate-600'
})
const assistantSummaryCards = computed(() => [
  {
    label: '归并文件数',
    value: String(assistantMergePreview.value?.summary?.documents_count ?? 0),
    caption: '当前批次可归并后的文档数量',
  },
  {
    label: '原始材料数',
    value: String(assistantMergePreview.value?.summary?.total_tasks ?? 0),
    caption: '参与当前批次分析的材料数',
  },
  {
    label: '推荐字段完整率',
    value: pct(assistantMetrics.value?.field_fill_rate?.recommended),
    caption: '推荐字段的整体填充程度',
  },
  {
    label: '最近问答数',
    value: String(assistantQaPreview.value.length),
    caption: assistantLatestSourceLabel.value ? `最近来源：${assistantLatestSourceLabel.value}` : '点击右侧可直接提问',
  },
])
const assistantItems = computed(() => [
  {
    title: '智能整合',
    icon: 'merge',
    description: '对当前批次中的同一文档进行保守整合，返回可核对的分组与字段建议。',
    hint: hasBatchContext.value
      ? assistantMergedDocuments.value.length
        ? `已加载 ${assistantMergedDocuments.value.length} 条归并预览，可继续查看完整整合结果。`
        : '点击后可进入完整分析中心查看归并建议，当前页下方也会展示预览。'
      : '需先完成一次批量处理，系统才能生成同文档整合建议。',
    ctaLabel: hasBatchContext.value ? '查看整合预览' : '先处理批次',
    buttonClass: hasBatchContext.value
      ? 'bg-violet-600 text-white hover:brightness-105'
      : 'border border-[var(--gov-border)] bg-white text-[var(--gov-text)] hover:bg-slate-50',
    action: () => {
      if (!hasBatchContext.value) {
        selectedTab.value = 'vl'
        return
      }
      openBatchInsights('overview')
    },
  },
  {
    title: '质量概览',
    icon: 'chart',
    description: '集中查看批次处理质量、冲突项和人工核对结果，便于复核。',
    hint: hasBatchContext.value
      ? assistantMetrics.value
        ? `字段完整率 ${pct(assistantMetrics.value.field_fill_rate?.recommended)}，冲突率 ${pct(assistantMetrics.value.conflict_rate)}。`
        : '点击后可进入质量概览页查看更完整的评估指标和人工校核面板。'
      : '需先形成批次结果，才能汇总质量指标和复核建议。',
    ctaLabel: hasBatchContext.value ? '进入质量概览' : '先处理批次',
    buttonClass: hasBatchContext.value
      ? 'bg-white text-[var(--gov-text)] ring-1 ring-[var(--gov-border)] hover:bg-slate-50'
      : 'border border-[var(--gov-border)] bg-white text-[var(--gov-text)] hover:bg-slate-50',
    action: () => {
      if (!hasBatchContext.value) {
        selectedTab.value = 'vl'
        return
      }
      openBatchInsights('metrics')
    },
  },
  {
    title: '批次问答',
    icon: 'chat',
    description: '围绕当前批次做证据可追溯的知识问答，优先给出可解释结论。',
    hint: hasBatchContext.value
      ? assistantQaPreview.value.length
        ? `当前已有 ${assistantQaPreview.value.length} 条最近问答，可在右侧继续追问。`
        : '右侧可以直接提问，也可以进入完整问答页查看证据链和反馈。'
      : '需先完成批量处理，系统才能基于当前批次材料回答问题。',
    ctaLabel: hasBatchContext.value ? '进入批次问答' : '先处理批次',
    buttonClass: hasBatchContext.value
      ? 'bg-white text-[var(--gov-text)] ring-1 ring-[var(--gov-border)] hover:bg-slate-50'
      : 'border border-[var(--gov-border)] bg-white text-[var(--gov-text)] hover:bg-slate-50',
    action: () => {
      if (!hasBatchContext.value) {
        selectedTab.value = 'vl'
        return
      }
      openBatchInsights('qa')
    },
  },
])

function pct(value, empty = '—') {
  if (value === null || value === undefined || value === '') return empty
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(1)}%` : empty
}

function decimalText(value, digits = 2, empty = '—') {
  if (value === null || value === undefined || value === '') return empty
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric.toFixed(digits) : empty
}

function qaSupportText(level) {
  if (level === 'supported') return '证据充分'
  if (level === 'partial') return '部分支持'
  return '证据不足'
}

function openBatchInsights(tab = 'overview') {
  if (!latestBatchId.value) return
  const query = tab && tab !== 'overview' ? { tab } : {}
  router.push({
    path: `/batch-insights/${encodeURIComponent(latestBatchId.value)}`,
    query,
  })
}

async function loadAssistantPreview(options = {}) {
  const forceRefresh = Boolean(options.forceRefresh)
  if (!latestBatchId.value) {
    assistantPreviewBatchId.value = ''
    assistantMergePreview.value = null
    assistantMetricsPreview.value = null
    assistantQaPreview.value = []
    assistantQaAnswer.value = null
    assistantPreviewError.value = ''
    assistantPreviewWarning.value = ''
    return
  }

  if (assistantPreviewBatchId.value !== latestBatchId.value) {
    assistantQaAnswer.value = null
    assistantQaInput.value = ''
    assistantQaError.value = ''
  }
  assistantPreviewBatchId.value = latestBatchId.value

  assistantPreviewLoading.value = true
  assistantPreviewError.value = ''
  assistantPreviewWarning.value = ''

  const [mergeResult, metricsResult, qaHistoryResult] = await Promise.allSettled([
    aiMergeExtractBatch(latestBatchId.value, {
      include_evidence: false,
      persist: false,
      force_refresh: forceRefresh,
    }),
    getBatchEvaluationMetrics(latestBatchId.value, { forceRefresh }),
    getBatchQaHistory(latestBatchId.value, { page: 1, pageSize: 3 }),
  ])

  const partialWarnings = []
  let successCount = 0

  if (mergeResult.status === 'fulfilled' && mergeResult.value?.data?.batch_id) {
    assistantMergePreview.value = mergeResult.value.data
    successCount += 1
  } else {
    assistantMergePreview.value = null
    partialWarnings.push(
      normalizeAiErrorMessage(
        mergeResult.status === 'rejected' ? mergeResult.reason : null,
        '智能整合预览暂时不可用。'
      )
    )
  }

  if (metricsResult.status === 'fulfilled' && metricsResult.value?.data?.batch_id) {
    assistantMetricsPreview.value = metricsResult.value.data
    successCount += 1
  } else {
    assistantMetricsPreview.value = null
    partialWarnings.push(
      normalizeAiErrorMessage(
        metricsResult.status === 'rejected' ? metricsResult.reason : null,
        '质量摘要暂时不可用。'
      )
    )
  }

  if (qaHistoryResult.status === 'fulfilled' && Array.isArray(qaHistoryResult.value?.data?.items)) {
    assistantQaPreview.value = qaHistoryResult.value.data.items
    successCount += 1
  } else {
    assistantQaPreview.value = []
    partialWarnings.push(
      normalizeAiErrorMessage(
        qaHistoryResult.status === 'rejected' ? qaHistoryResult.reason : null,
        '最近问答暂时不可用。'
      )
    )
  }

  if (!successCount) {
    assistantPreviewError.value = partialWarnings[0] || '当前批次智能辅助暂时不可用，请稍后重试。'
  } else if (partialWarnings.length) {
    assistantPreviewWarning.value = partialWarnings[0]
  }

  assistantPreviewLoading.value = false
}

function handleAssistantPrimaryAction() {
  if (hasBatchContext.value && latestBatchId.value) {
    openBatchInsights('overview')
    return
  }
  selectedTab.value = 'vl'
}

async function tryResolveBatchFromHistory() {
  if (latestBatchId.value) {
    await aiCapability.refreshAiCapability({ passive: false, batchId: latestBatchId.value })
    return
  }

  try {
    const { data } = await getTaskSubmissions()
    const submissions = data || []
    for (const submission of submissions) {
      const batchId = submission.batch_id || ''
      if (batchId) {
        await aiCapability.refreshAiCapability({ passive: false, batchId })
        return
      }
    }
  } catch (_) {}
}

async function onAssistantTabClick() {
  selectedTab.value = 'assistant'
  if (!latestBatchId.value) {
    await tryResolveBatchFromHistory()
  } else {
    await aiCapability.refreshAiCapability({ passive: false, batchId: latestBatchId.value })
  }
  if (latestBatchId.value) {
    await loadAssistantPreview()
  }
}

function handleStartBatch() {
  taskBoardRef.value?.refresh?.({ silent: true })
}

async function handleBatchCompleted(payload = {}) {
  historyRef.value?.refresh()
  taskBoardRef.value?.refresh?.()
  if (!payload?.hasUsableResults || !payload?.batchId) {
    return
  }
  if (selectedTab.value !== 'assistant') {
    return
  }
  await aiCapability.refreshAiCapability({ passive: false, batchId: payload.batchId })
  if (selectedTab.value === 'assistant') {
    await loadAssistantPreview({ forceRefresh: true })
  }
}

async function handleHistoryBatchContext(payload = {}) {
  if (!payload?.batchId) {
    return
  }
  await aiCapability.refreshAiCapability({ passive: false, batchId: payload.batchId })
  if (selectedTab.value === 'assistant') {
    await loadAssistantPreview()
  }
}

async function handleHistoryViewBatch(payload = {}) {
  const batchId = payload?.batchId
  if (!batchId) return

  historyMergeBatchId.value = batchId
  historyMergeVisible.value = true
  historyMergeLoading.value = true
  historyMergeError.value = ''
  historyMergeResult.value = null
  historyMetrics.value = null
  historyMetricsError.value = ''

  try {
    const { data } = await aiMergeExtractBatch(batchId, {
      include_evidence: true,
      persist: false,
      force_refresh: false,
    })
    historyMergeResult.value = data
  } catch (error) {
    historyMergeError.value = normalizeAiErrorMessage(error, '智能整合数据暂时无法获取，请稍后重试。')
  } finally {
    historyMergeLoading.value = false
  }

  if (historyMergeResult.value) {
    historyMetricsLoading.value = true
    try {
      const { data } = await getBatchEvaluationMetrics(batchId, { forceRefresh: false })
      historyMetrics.value = data
    } catch (error) {
      historyMetricsError.value = normalizeAiErrorMessage(error, '质量概览暂时无法获取。')
    } finally {
      historyMetricsLoading.value = false
    }
  }
}

async function handleHistoryMergeRecompute() {
  const batchId = historyMergeBatchId.value
  if (!batchId) return
  historyMergeRefreshing.value = true
  try {
    const { data } = await aiMergeExtractBatch(batchId, {
      include_evidence: true,
      persist: false,
      force_refresh: true,
    })
    historyMergeResult.value = data
    historyMetricsLoading.value = true
    try {
      const { data: mData } = await getBatchEvaluationMetrics(batchId, { forceRefresh: true })
      historyMetrics.value = mData
    } catch { /* silent */ } finally { historyMetricsLoading.value = false }
  } catch (error) {
    historyMergeError.value = normalizeAiErrorMessage(error, '重新分析失败。')
  } finally {
    historyMergeRefreshing.value = false
  }
}

function handleHistoryMergeOpenTask(taskId) {
  historyMergeVisible.value = false
  router.push({ path: `/result/${taskId}`, query: { batch_id: historyMergeBatchId.value } })
}

function handleHistoryMergeOpenInsights() {
  historyMergeVisible.value = false
  router.push({ path: `/batch-insights/${encodeURIComponent(historyMergeBatchId.value)}` })
}

function handleHistoryMergeOpenReview() {
  historyMergeVisible.value = false
  router.push({ path: `/batch-insights/${encodeURIComponent(historyMergeBatchId.value)}`, query: { tab: 'truth' } })
}

function handleTaskBoardViewBatch(payload = {}) {
  const batchId = String(payload?.batchId || payload?.batch_id || '').trim()
  if (!batchId) return
  router.push({ path: `/batch-insights/${encodeURIComponent(batchId)}` })
}

async function submitAssistantQa() {
  if (!latestBatchId.value) {
    selectedTab.value = 'vl'
    return
  }

  const question = String(assistantQaInput.value || '').trim()
  if (!question) {
    assistantQaError.value = '请输入问题后再发送。'
    return
  }

  assistantQaSubmitting.value = true
  assistantQaError.value = ''
  try {
    const { data } = await askBatchQuestion(latestBatchId.value, {
      question,
      top_k: 8,
      persist: true,
    })
    assistantQaAnswer.value = data
    assistantQaPreview.value = [
      data,
      ...assistantQaPreview.value.filter((item) => Number(item.qa_id) !== Number(data?.qa_id)),
    ].slice(0, 3)
    assistantQaInput.value = ''
  } catch (error) {
    assistantQaError.value = normalizeAiErrorMessage(error, '批次问答暂时不可用，请稍后重试。')
  } finally {
    assistantQaSubmitting.value = false
  }
}

function handleViewResult(payload) {
  const taskId = typeof payload === 'object' && payload !== null
    ? payload.taskId || payload.id
    : payload
  if (!taskId) return

  const query = {}
  const folder = typeof payload === 'object' && payload !== null ? String(payload.folder || '').trim() : ''
  const submissionId = typeof payload === 'object' && payload !== null ? String(payload.submissionId || '').trim() : ''
  const batchId = typeof payload === 'object' && payload !== null ? String(payload.batchId || '').trim() : ''

  if (folder) {
    query.folder = folder
  }
  if (submissionId) {
    query.submission_id = submissionId
  }
  if (batchId) {
    query.batch_id = batchId
  }

  router.push({ path: `/result/${taskId}`, query })
}

onMounted(() => {
  loadMyQuota()
})
</script>
