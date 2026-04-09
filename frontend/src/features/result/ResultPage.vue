<template>
  <div class="flex h-screen flex-col overflow-hidden bg-gray-50">
    <div class="flex flex-shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4 py-2">
      <div class="flex min-w-0 items-center space-x-3">
        <button class="rounded p-1 transition hover:bg-gray-100" title="返回" @click="goBack">
          <svg class="h-5 w-5 text-gray-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7" /></svg>
        </button>
        <div class="min-w-0">
          <h2 class="truncate text-sm font-medium text-gray-800">{{ task?.filename || '加载中...' }}</h2>
          <p class="text-xs text-gray-400">{{ task?.page_count || 0 }} 页</p>
        </div>
        <span v-if="isMergedMaterialView" class="rounded bg-violet-100 px-1.5 py-0.5 text-xs font-medium text-violet-700">
          合并材料
        </span>
        <span class="rounded px-1.5 py-0.5 text-xs font-medium" :class="modeClass">{{ modeLabel }}</span>
        <span class="rounded px-1.5 py-0.5 text-xs font-medium" :class="statusClass(task?.status)">
          {{ statusLabel(task?.status) }}
        </span>
      </div>
      <div class="flex items-center space-x-2 text-xs text-gray-500">
        <span v-if="refreshing && !loading" class="text-blue-600">切换中...</span>
        <span v-if="polling" class="text-blue-600">后台处理中，结果会自动刷新</span>
        <span>{{ task?.updated_at ? formatTime(task.updated_at) : '' }}</span>
      </div>
    </div>

    <div v-if="loading" class="flex flex-1 items-center justify-center">
      <svg class="h-8 w-8 animate-spin text-blue-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
    </div>

    <div v-else-if="error" class="flex flex-1 items-center justify-center text-sm text-red-500">{{ error }}</div>

    <div v-else-if="isTaskProcessing" class="flex flex-1 items-center justify-center bg-white px-6">
      <div class="w-full max-w-lg rounded-2xl border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-6 py-8 text-center">
        <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--gov-primary-soft)] text-[var(--gov-primary)]">
          <svg class="h-7 w-7 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
        </div>
        <p class="mt-4 text-lg font-semibold text-[var(--gov-text)]">当前材料正在识别处理中</p>
        <p class="mt-2 text-sm leading-7 gov-muted">
          系统会在后台持续完成识别与结构整理，处理结束后会自动刷新当前页面。
        </p>
        <div class="mt-4 inline-flex items-center rounded-full border border-[var(--gov-border)] bg-white px-4 py-1.5 text-xs text-[var(--gov-text-muted)]">
          当前状态：{{ statusLabel(task?.status) }}
        </div>
        <div class="mt-5 flex justify-center gap-3">
          <button class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-2 text-sm text-[var(--gov-text)] hover:bg-slate-50" @click="goBack">
            返回工作台
          </button>
        </div>
      </div>
    </div>

    <div v-else-if="isTaskFailed" class="flex flex-1 items-center justify-center bg-white px-6">
      <div class="w-full max-w-lg rounded-2xl border border-red-200 bg-red-50 px-6 py-8 text-center">
        <div class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-white text-red-500">
          <svg class="h-7 w-7" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 9v4m0 4h.01" /><circle cx="12" cy="12" r="9" /></svg>
        </div>
        <p class="mt-4 text-lg font-semibold text-red-700">当前材料处理异常</p>
        <p class="mt-2 text-sm leading-7 text-red-600">
          {{ task?.error_message || '当前记录未能生成可展示的识别结果，请稍后重试或重新发起处理。' }}
        </p>
        <div class="mt-5 flex justify-center gap-3">
          <button class="rounded-lg border border-red-200 bg-white px-4 py-2 text-sm text-red-700 hover:bg-red-100" @click="goBack">
            返回工作台
          </button>
        </div>
      </div>
    </div>

    <div v-else class="flex min-h-0 flex-1">
      <aside v-if="folderPath" class="flex min-h-0 w-[32%] min-w-[320px] max-w-[420px] flex-shrink-0 flex-col border-r border-gray-200 bg-slate-50">
        <div class="border-b border-gray-200 bg-white px-4 py-3">
          <p class="truncate text-sm font-semibold text-slate-800">{{ folderLabel }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ materialCountLabel }}</p>
          <p v-if="folderMaterials.length > 1" class="mt-1 text-[11px] leading-5 text-slate-400">
            拖动左侧材料到目标组，可手动并入同一 PDF。
          </p>
        </div>
        <div v-if="folderLoading" class="flex flex-1 items-center justify-center text-xs text-slate-500">
          目录加载中...
        </div>
        <div v-else-if="!folderMaterials.length" class="flex flex-1 items-center justify-center px-4 text-center text-xs leading-6 text-slate-400">
          当前{{ materialScopeLabel }}暂无可展示材料
        </div>
        <div v-else class="flex-1 space-y-2 overflow-y-auto p-2">
          <div
            v-for="material in folderMaterials"
            :key="material.id"
            class="rounded-2xl border transition"
            :class="[
              isMaterialGroupActive(material)
                ? 'border-violet-300 bg-violet-50/80 shadow-sm ring-1 ring-violet-200'
                : isMaterialContextActive(material)
                  ? 'border-blue-200 bg-blue-50/40 shadow-sm'
                  : 'border-transparent bg-white hover:border-slate-200',
              draggingMaterialId === material.id ? 'opacity-60' : '',
              dragOverMaterialId === material.id ? 'border-violet-300 bg-violet-50/80 ring-2 ring-violet-200' : '',
            ]"
            draggable="true"
            @dragstart="onMaterialDragStart(material, $event)"
            @dragend="onMaterialDragEnd"
            @dragover.prevent="onMaterialDragOver(material)"
            @dragleave="onMaterialDragLeave(material, $event)"
            @drop.prevent="onMaterialDrop(material)"
          >
            <div
              class="flex cursor-pointer items-start gap-2 px-3 py-3"
              :title="material.isMerged ? '点击查看整组合并视图' : '点击查看当前材料'"
              role="button"
              tabindex="0"
              @click="openMaterial(material)"
              @keydown.enter.prevent="openMaterial(material)"
              @keydown.space.prevent="openMaterial(material)"
            >
              <div
                class="flex min-w-0 flex-1 items-start gap-3 rounded-xl px-2 py-2 text-left transition"
                :class="[
                  isMaterialGroupActive(material)
                    ? 'bg-white ring-1 ring-violet-200'
                    : isMaterialContextActive(material)
                      ? 'bg-white/90 ring-1 ring-blue-100'
                      : 'hover:bg-white',
                ]"
              >
                <div class="h-14 w-11 flex-shrink-0 overflow-hidden rounded border border-slate-200 bg-white">
                  <img
                    v-if="hasCardPreview(material.previewTask, `material:${material.id}`)"
                    :src="getCardPreviewUrl(material.previewTask, `material:${material.id}`)"
                    class="h-full w-full object-cover"
                    :alt="material.title"
                    @error="onCardPreviewError(material.previewTask, `material:${material.id}`)"
                  />
                  <div v-else class="flex h-full w-full items-center justify-center text-slate-300">
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path d="M4 5a2 2 0 0 1 2-2h8l6 6v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><path d="M14 3v6h6" /></svg>
                  </div>
                </div>
                <div class="min-w-0 flex-1">
                  <div class="line-clamp-2 text-xs font-medium text-slate-700">{{ material.title }}</div>
                  <p class="mt-1 text-[11px] leading-5 text-slate-500">{{ material.subtitle }}</p>
                  <div class="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                    <span class="rounded px-1.5 py-0.5" :class="statusClass(material.status)">
                      {{ statusLabel(material.status) }}
                    </span>
                    <span v-if="material.groupSource === 'manual'" class="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-700">
                      手动分组
                    </span>
                    <span v-if="material.isMerged" class="rounded bg-violet-100 px-1.5 py-0.5 font-medium text-violet-700">
                      整组 · {{ material.memberTaskIds.length }} 页
                    </span>
                    <span>{{ formatTime(material.updatedAt) }}</span>
                  </div>
                </div>
              </div>
              <div class="mt-1 flex flex-shrink-0 items-center gap-1">
                <button
                  v-if="material.groupSource === 'manual' && material.isMerged"
                  class="rounded-full px-2 py-1 text-[10px] font-medium text-amber-600 transition hover:bg-white hover:text-amber-700"
                  title="解散手动分组"
                  @click.stop="ungroupMaterial(material)"
                >
                  解组
                </button>
                <button
                  v-if="material.isMerged"
                  class="flex h-7 w-7 items-center justify-center rounded-full text-slate-400 transition hover:bg-white hover:text-slate-600"
                  :title="isMaterialExpanded(material.id) ? '收起材料页' : '展开材料页'"
                  @click.stop="toggleMaterialExpanded(material.id)"
                >
                  <svg class="h-4 w-4 transition" :class="isMaterialExpanded(material.id) ? 'rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m9 5 7 7-7 7" /></svg>
                </button>
              </div>
            </div>

            <div v-if="material.isMerged && isMaterialExpanded(material.id)" class="border-t border-slate-200 px-3 py-2">
              <p class="mb-2 px-1 text-[11px] leading-5 text-slate-400">拖动右侧手柄，或用上下按钮调整组内 PDF 顺序</p>
              <div class="space-y-1.5">
                <div
                  v-for="memberTask in material.memberTasks"
                  :key="memberTask.id"
                  class="relative cursor-pointer rounded-xl px-3 py-2 text-left transition"
                  :class="[
                    isMemberTaskActive(memberTask.id) ? 'bg-blue-100 text-blue-700 ring-1 ring-blue-200' : 'bg-slate-50 text-slate-600 hover:bg-slate-100',
                    draggingMemberMaterialId === material.id && Number(draggingMemberTaskId) === Number(memberTask.id) ? 'opacity-60 ring-2 ring-blue-200' : '',
                    memberDragOverMaterialId === material.id && Number(memberDragOverTaskId) === Number(memberTask.id) ? 'bg-violet-50' : '',
                  ]"
                  @dragover.prevent.stop="onMaterialMemberDragOver(material, memberTask, $event)"
                  @dragleave="onMaterialMemberDragLeave(material, memberTask, $event)"
                  @drop.prevent.stop="onMaterialMemberDrop(material, memberTask)"
                  @click="openMaterialMember(material, memberTask.id)"
                >
                  <div
                    v-if="memberDragOverMaterialId === material.id && Number(memberDragOverTaskId) === Number(memberTask.id) && memberDragOverPosition === 'before'"
                    class="pointer-events-none absolute inset-x-3 top-0 h-0.5 rounded-full bg-violet-500"
                  />
                  <div
                    v-if="memberDragOverMaterialId === material.id && Number(memberDragOverTaskId) === Number(memberTask.id) && memberDragOverPosition === 'after'"
                    class="pointer-events-none absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-violet-500"
                  />
                  <div class="flex items-start gap-3">
                    <div class="h-12 w-9 flex-shrink-0 overflow-hidden rounded border border-slate-200 bg-white">
                      <img
                        v-if="hasCardPreview(memberTask, `member:${material.id}:${memberTask.id}`)"
                        :src="getCardPreviewUrl(memberTask, `member:${material.id}:${memberTask.id}`)"
                        class="h-full w-full object-cover"
                        :alt="memberTask.filename"
                        @error="onCardPreviewError(memberTask, `member:${material.id}:${memberTask.id}`)"
                      />
                      <div v-else class="flex h-full w-full items-center justify-center text-slate-300">
                        <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path d="M4 5a2 2 0 0 1 2-2h8l6 6v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><path d="M14 3v6h6" /></svg>
                      </div>
                    </div>
                    <div class="min-w-0 flex-1 text-left">
                      <div class="line-clamp-2 break-all text-xs font-medium leading-5">{{ memberTask.filename }}</div>
                      <div class="mt-1 whitespace-nowrap text-[11px] text-slate-400">{{ formatTime(memberTask.updated_at || memberTask.created_at) }}</div>
                    </div>
                    <span class="ml-2 shrink-0 self-start rounded px-1.5 py-0.5 text-[10px]" :class="statusClass(memberTask.status)">
                      {{ statusLabel(memberTask.status) }}
                    </span>
                  </div>
                  <div class="mt-2 flex items-center justify-end gap-1.5 pl-12" @click.stop>
                    <button
                      class="flex h-7 w-7 items-center justify-center rounded-full text-slate-300 transition hover:bg-white hover:text-slate-500 disabled:cursor-not-allowed disabled:opacity-40"
                      :disabled="!canMoveMaterialMember(material, memberTask.id, -1)"
                      title="上移一位"
                      @click.stop="moveMaterialMemberByStep(material, memberTask.id, -1)"
                    >
                      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m6 15 6-6 6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
                    </button>
                    <button
                      class="flex h-7 w-7 items-center justify-center rounded-full text-slate-300 transition hover:bg-white hover:text-slate-500 disabled:cursor-not-allowed disabled:opacity-40"
                      :disabled="!canMoveMaterialMember(material, memberTask.id, 1)"
                      title="下移一位"
                      @click.stop="moveMaterialMemberByStep(material, memberTask.id, 1)"
                    >
                      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m18 9-6 6-6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
                    </button>
                    <span
                      class="flex h-8 w-8 cursor-grab items-center justify-center rounded-full text-slate-300 transition hover:bg-white hover:text-slate-500 active:cursor-grabbing"
                      draggable="true"
                      title="拖动调整顺序"
                      @dragstart="onMaterialMemberDragStart(material, memberTask, $event)"
                      @dragend="onMaterialMemberDragEnd"
                    >
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path d="M9 6h.01M9 12h.01M9 18h.01M15 6h.01M15 12h.01M15 18h.01" stroke-linecap="round"/></svg>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <section class="flex min-h-0 min-w-0 flex-[36_1_36%] flex-col border-r border-gray-200 bg-white">
        <div class="border-b border-gray-100 px-3 py-2 text-xs font-medium text-gray-500">原始文件预览</div>
        <div class="preview-container relative flex flex-1 items-start justify-center overflow-auto bg-gray-50 p-3">
          <div v-if="isMergedMaterialView" class="w-full max-w-4xl space-y-4">
            <button
              v-for="previewPage in mergedPreviewEntries"
              :key="previewPage.key"
              :ref="(element) => setMergedPreviewPageRef(previewPage.pageNumber, element)"
              class="w-full rounded-2xl border bg-white p-3 text-left shadow-sm transition"
              :class="pageNum === previewPage.pageNumber ? 'border-blue-300 ring-2 ring-blue-200' : 'border-slate-200 hover:border-slate-300'"
              @click="pageNum = previewPage.pageNumber"
            >
              <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p class="text-xs font-semibold text-slate-700">第 {{ previewPage.pageNumber }} 页</p>
                  <p class="mt-1 text-[11px] leading-5 text-slate-500">{{ previewPage.filename }}</p>
                </div>
                <span class="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-600">
                  源页 {{ previewPage.sourcePageLabel }}
                </span>
              </div>
              <img :src="previewPage.imageUrl" class="mx-auto max-w-full rounded shadow-sm" :alt="previewPage.filename" />
            </button>
          </div>
          <iframe v-else-if="isPdf && pdfImgFailed" :src="fileUrl" class="h-full w-full rounded border-0" />
          <div v-else class="relative inline-block">
            <img :src="previewImageUrl" class="max-w-full rounded shadow" ref="previewImg" @load="onImgLoad" @error="onImgError" />
            <svg
              v-if="imgW && imgH"
              class="pointer-events-none absolute left-0 top-0"
              :width="imgW"
              :height="imgH"
              :viewBox="`0 0 ${natW} ${natH}`"
            >
              <template v-for="item in currentPreviewItems" :key="item._key">
                <polygon
                  v-if="item.bbox_type === 'poly' && item.bbox?.length >= 3"
                  class="pointer-events-auto cursor-pointer"
                  :fill="regionFill(item)"
                  :points="item.bbox.map((point) => point.join(',')).join(' ')"
                  :stroke="regionStroke(item)"
                  :stroke-width="regionStrokeWidth(item)"
                  @click="selectItem(item)"
                />
                <rect
                  v-else-if="item.bbox?.length >= 4"
                  class="pointer-events-auto cursor-pointer"
                  :x="item.bbox[0]"
                  :y="item.bbox[1]"
                  :width="item.bbox[2] - item.bbox[0]"
                  :height="item.bbox[3] - item.bbox[1]"
                  :fill="regionFill(item)"
                  :stroke="regionStroke(item)"
                  :stroke-width="regionStrokeWidth(item)"
                  rx="2"
                  @click="selectItem(item)"
                />
              </template>
            </svg>
          </div>
        </div>

        <div v-if="!isMergedMaterialView && totalPages > 1" class="flex items-center justify-center space-x-3 border-t border-gray-100 bg-white px-3 py-2">
          <button class="flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30" :disabled="pageNum <= 1" @click="pageNum -= 1">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div class="text-xs text-gray-500">第 {{ pageNum }} / {{ totalPages }} 页</div>
          <button class="flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30" :disabled="pageNum >= totalPages" @click="pageNum += 1">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" /></svg>
          </button>
        </div>
      </section>

      <section class="flex min-h-0 min-w-[320px] flex-[32_1_32%] flex-col bg-white">
        <div class="flex flex-shrink-0 items-center justify-between border-b border-gray-100 px-4 py-2">
          <div class="flex items-center space-x-1">
            <button class="rounded px-3 py-1 text-xs font-medium transition" :class="activeTab === 'parsed' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'" @click="activeTab = 'parsed'">
              识别结果
            </button>
            <button class="rounded px-3 py-1 text-xs font-medium transition" :class="activeTab === 'json' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'" @click="activeTab = 'json'">
              结构数据
            </button>
            <button class="rounded px-3 py-1 text-xs font-medium transition" :class="activeTab === 'fields' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'" @click="activeTab = 'fields'">
              字段提取
            </button>
            <button class="rounded px-3 py-1 text-xs font-medium transition" :class="activeTab === 'report' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'" @click="activeTab = 'report'">
              识别报告
            </button>
          </div>
          <div class="flex items-center space-x-1">
            <button class="rounded p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600" title="复制全文" @click="copyAllContent">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
            </button>
            <button class="rounded p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600" title="下载文本" @click="downloadTxtContent">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
            </button>
          </div>
        </div>

        <div v-if="activeTab === 'parsed'" class="flex-1 overflow-y-auto px-5 py-4">
          <div v-if="task?.status === 'failed'" class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-600">
            当前记录处理异常，暂时没有可展示内容，请稍后重试或重新发起处理。
          </div>
          <div v-else-if="!allItems.length" class="flex h-full items-center justify-center text-sm text-gray-400">暂无识别内容。</div>
          <div v-else class="space-y-2">
            <template v-for="item in allItems" :key="item._key">
              <div v-if="item._pageSeparator" class="flex items-center space-x-3 py-2">
                <div class="h-px flex-1 bg-gray-200"></div>
                <span class="text-xs text-gray-400">第 {{ item._pageNumber }} 页</span>
                <div class="h-px flex-1 bg-gray-200"></div>
              </div>

              <div
                v-else
                :ref="(element) => setRegionRef(item._key, element)"
                class="rounded-lg border px-4 py-3 transition"
                :class="activeKey === item._key ? 'border-blue-200 bg-blue-50/60 shadow-sm' : 'border-transparent hover:bg-gray-50'"
                @click="selectItem(item)"
              >
                <template v-if="item._renderMode === 'ocr_line'">
                  <div
                    class="rounded-md px-2 py-1 transition"
                    :class="activeKey === item._key ? 'bg-blue-50/80' : 'hover:bg-gray-50/90'"
                    :style="ocrLineContainerStyle(item)"
                  >
                    <p class="whitespace-pre-wrap text-gray-800" :style="ocrLineTextStyle(item)">{{ item.content }}</p>
                  </div>
                </template>

                <template v-else>
                <div v-if="showRegionHeader(item)" class="mb-1.5 flex items-center justify-between">
                  <span class="inline-block rounded px-2 py-0.5 text-xs font-medium" :class="labelClass(item.type)">
                    {{ labelName(item.type) }}
                  </span>
                  <div class="flex items-center space-x-1">
                    <button v-if="item.type !== 'seal'" class="rounded px-2 py-0.5 text-xs text-gray-500 transition hover:bg-white hover:text-blue-600" @click.stop="copyRegion(item)">
                      复制
                    </button>
                    <button
                      v-if="task?.status === 'done' && !isMergedMaterialView && item.type !== 'table' && item.type !== 'seal' && item._editable !== false"
                      class="rounded px-2 py-0.5 text-xs text-gray-500 transition hover:bg-white hover:text-blue-600"
                      @click.stop="startTextEdit(item)"
                    >
                      编辑
                    </button>
                    <button
                      v-if="task?.status === 'done' && !isMergedMaterialView && item.type === 'table' && item._editable !== false"
                      class="rounded px-2 py-0.5 text-xs text-gray-500 transition hover:bg-white hover:text-blue-600"
                      @click.stop="startTableEdit(item)"
                    >
                      编辑表格
                    </button>
                  </div>
                </div>

                <template v-if="editingKey === item._key">
                  <textarea
                    v-model="editText"
                    rows="4"
                    class="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-100"
                  />
                  <div class="mt-2 flex items-center justify-end space-x-2">
                    <button class="rounded bg-gray-100 px-3 py-1 text-xs text-gray-600 hover:bg-gray-200" @click.stop="cancelTextEdit">
                      取消
                    </button>
                    <button class="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700" @click.stop="saveTextEdit(item)">
                      保存
                    </button>
                  </div>
                </template>

                <template v-else-if="item.type === 'table'">
                  <EditableTable
                    :model-value="editingTableKey === item._key ? tableDraft : item.table_data"
                    :editing="editingTableKey === item._key"
                    @update:model-value="tableDraft = $event"
                  />
                  <div v-if="editingTableKey === item._key" class="mt-2 flex items-center justify-end space-x-2">
                    <button class="rounded bg-gray-100 px-3 py-1 text-xs text-gray-600 hover:bg-gray-200" @click.stop="cancelTableEdit">
                      取消
                    </button>
                    <button class="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700" @click.stop="saveTableEdit(item)">
                      保存
                    </button>
                  </div>
                </template>

                <template v-else-if="item._renderMode === 'region_formatted_text'">
                  <div class="space-y-0.5">
                    <div
                      v-for="line in item._displayLines"
                      :key="line._key"
                      class="rounded-md px-2 py-1"
                      :style="ocrLineContainerStyle(line)"
                    >
                      <p class="whitespace-pre-wrap text-gray-800" :style="ocrLineTextStyle(line)">{{ line.content }}</p>
                    </div>
                  </div>
                </template>

                <template v-else>
                  <div
                    v-if="showRegionPreview(item)"
                    class="mb-3 overflow-hidden rounded-lg border border-gray-200 bg-slate-50"
                    :style="cropFrameStyle(item)"
                  >
                    <img :src="previewImageUrl" class="pointer-events-none max-w-none select-none" :style="cropImageStyle(item)" />
                  </div>
                  <p v-if="itemBodyText(item)" class="whitespace-pre-wrap text-sm leading-6 text-gray-700">{{ itemBodyText(item) }}</p>
                  <p v-else-if="item.type === 'seal'" class="text-xs tracking-wide text-gray-400">印章区域</p>
                  <p v-else class="whitespace-pre-wrap text-sm leading-6 text-gray-700">{{ item.content }}</p>
                </template>
                </template>
              </div>
            </template>
          </div>
        </div>

        <div v-else-if="activeTab === 'fields'" class="flex-1 overflow-y-auto px-5 py-4">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold text-gray-800">档案字段提取</h3>
              <p class="mt-0.5 text-xs text-gray-400">基于识别结果自动提取关键归档字段，可手动修正</p>
            </div>
            <button
              class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition"
              :class="aiLoading || isMergedMaterialView ? 'bg-indigo-50 text-indigo-400' : 'bg-indigo-600 text-white hover:bg-indigo-700'"
              :disabled="aiLoading || task?.status !== 'done' || isMergedMaterialView"
              @click="runAiExtraction"
            >
              <svg v-if="aiLoading" class="h-3.5 w-3.5 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
              <svg v-else class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
              {{ aiLoading ? '提取中…' : 'AI 智能提取' }}
            </button>
          </div>

          <div v-if="isMergedMaterialView" class="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-700">
            当前为同文件合并视图，识别结果已按连续页收纳展示。字段提取与字段编辑仍按单页任务管理，如需修正字段，请点击左侧具体页进入单页视图。
          </div>

          <div v-if="fieldsLoading" class="flex items-center justify-center py-12 text-sm text-gray-400">
            <svg class="mr-2 h-5 w-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
            正在提取字段…
          </div>

          <div v-else-if="fieldsError" class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-700">
            {{ fieldsError }}
          </div>

          <div v-else-if="task?.status !== 'done'" class="flex items-center justify-center py-12 text-sm text-gray-400">
            任务完成后可提取字段信息
          </div>

          <div v-else class="space-y-3">
            <div v-if="aiFields" class="mb-3 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2">
              <svg class="h-4 w-4 flex-shrink-0 text-green-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <span class="text-xs text-green-700">已完成 AI 智能提取，字段已自动择优合并</span>
            </div>

            <div
              v-for="field in FIELD_LABELS"
              :key="field.key"
              class="rounded-xl border transition"
              :class="fieldHasConflict(field.key) ? 'border-amber-200 bg-amber-50/50' : 'border-gray-100 bg-white hover:border-gray-200'"
            >
              <div class="flex items-start gap-3 px-4 py-3">
                <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-xs font-bold" :class="fieldHasConflict(field.key) ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'">
                  {{ field.icon }}
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-gray-500">{{ field.key }}</span>
                    <div class="flex items-center gap-1">
                      <span v-if="fieldHasConflict(field.key)" class="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-600">有差异</span>
                      <span v-else-if="aiFields && fieldDisplayValue(field.key)" class="rounded bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-600">已确认</span>
                      <button
                        v-if="editingFieldKey !== field.key && task?.status === 'done' && !isMergedMaterialView"
                        class="rounded px-1.5 py-0.5 text-[10px] text-gray-400 hover:bg-gray-100 hover:text-blue-600"
                        @click.stop="startFieldEdit(field.key)"
                      >编辑</button>
                    </div>
                  </div>

                  <template v-if="editingFieldKey === field.key">
                    <textarea
                      v-model="editingFieldValue"
                      rows="2"
                      class="mt-1.5 w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-100"
                    />
                    <div class="mt-1.5 flex items-center justify-end gap-2">
                      <button class="rounded bg-gray-100 px-3 py-1 text-xs text-gray-600 hover:bg-gray-200" @click="cancelFieldEdit">取消</button>
                      <button class="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700" @click="saveFieldEdit(field.key)">保存</button>
                    </div>
                  </template>

                  <template v-else>
                    <p class="mt-1 text-sm leading-6 text-gray-800" :class="{ 'italic text-gray-300': !fieldDisplayValue(field.key) }">
                      {{ fieldDisplayValue(field.key) || '未提取到' }}
                    </p>
                  </template>

                  <div v-if="fieldHasConflict(field.key)" class="mt-2 space-y-1 border-t border-amber-100 pt-2">
                    <p class="text-[11px] text-gray-500"><span class="font-medium text-gray-600">规则：</span>{{ fieldConflicts[field.key]?.rule || '—' }}</p>
                    <p class="text-[11px] text-gray-500"><span class="font-medium text-indigo-600">AI：</span>{{ fieldConflicts[field.key]?.llm || '—' }}</p>
                    <p v-if="fieldConflicts[field.key]?.evidence" class="text-[11px] italic text-gray-400">依据：{{ fieldConflicts[field.key].evidence }}</p>
                  </div>

                  <p v-else-if="fieldEvidence[field.key]" class="mt-1 text-[11px] italic text-gray-400">
                    依据：{{ fieldEvidence[field.key] }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'report'" class="flex-1 overflow-y-auto bg-slate-50 px-4 py-4">
          <div class="grid grid-cols-2 gap-3">
            <div v-for="card in reportOverviewCards" :key="card.label" class="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p class="text-[11px] font-medium uppercase tracking-[0.08em] text-slate-400">{{ card.label }}</p>
              <p class="mt-2 text-lg font-semibold text-slate-800">{{ card.value }}</p>
              <p v-if="card.hint" class="mt-1 text-xs leading-5 text-slate-500">{{ card.hint }}</p>
            </div>
          </div>

          <div class="mt-4 grid gap-4">
            <section class="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <div class="flex items-center justify-between">
                <div>
                  <h3 class="text-sm font-semibold text-slate-800">识别链路</h3>
                  <p class="mt-1 text-xs leading-5 text-slate-500">展示本次任务的主链路、模型配置与页级路由决策</p>
                </div>
                <span class="rounded-full px-2.5 py-1 text-[11px] font-medium" :class="reportStatusBadgeClass(recognitionReport.reviewStatusTone)">
                  {{ recognitionReport.reviewStatusLabel }}
                </span>
              </div>

              <div class="mt-4 space-y-3">
                <div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <p class="text-xs font-medium text-slate-500">主链路摘要</p>
                  <p class="mt-1 text-sm leading-6 text-slate-700">{{ recognitionReport.pipelineSummary }}</p>
                </div>
                <div class="grid gap-3">
                  <div class="rounded-xl border border-slate-200 px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">OCR 后端</p>
                    <p class="mt-1 text-sm text-slate-800">{{ recognitionReport.ocrBackend }}</p>
                  </div>
                  <div class="rounded-xl border border-slate-200 px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">第二路后端</p>
                    <p class="mt-1 text-sm text-slate-800">{{ recognitionReport.secondaryBackend }}</p>
                  </div>
                  <div class="rounded-xl border border-slate-200 px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">工作流</p>
                    <p class="mt-1 break-all text-sm text-slate-800">{{ recognitionReport.workflow }}</p>
                  </div>
                  <div class="rounded-xl border border-slate-200 px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">线程 ID</p>
                    <p class="mt-1 break-all text-sm text-slate-800">{{ recognitionReport.workflowThreadId }}</p>
                  </div>
                </div>
                <div v-if="recognitionReport.primaryRouteReason || recognitionReport.primaryReasoning" class="grid gap-3">
                  <div class="rounded-xl border border-slate-200 px-3 py-3" v-if="recognitionReport.primaryRouteReason">
                    <p class="text-xs font-medium text-slate-500">路由原因</p>
                    <p class="mt-1 text-sm leading-6 text-slate-700">{{ recognitionReport.primaryRouteReason }}</p>
                  </div>
                  <div class="rounded-xl border border-slate-200 px-3 py-3" v-if="recognitionReport.primaryReasoning">
                    <p class="text-xs font-medium text-slate-500">融合说明</p>
                    <p class="mt-1 text-sm leading-6 text-slate-700">{{ recognitionReport.primaryReasoning }}</p>
                  </div>
                </div>
              </div>
            </section>

            <section class="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
              <h3 class="text-sm font-semibold text-slate-800">人工复核结论</h3>
              <p class="mt-1 text-xs leading-5 text-slate-500">结合任务状态、批次结论与人工复核挂起信息生成</p>

              <div class="mt-4 rounded-xl border px-3 py-3" :class="reportStatusPanelClass(recognitionReport.reviewStatusTone)">
                <div class="flex items-center justify-between">
                  <span class="text-xs font-medium">{{ recognitionReport.reviewStatusLabel }}</span>
                  <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="reportStatusBadgeClass(recognitionReport.reviewStatusTone)">
                    {{ recognitionReport.reviewDecision }}
                  </span>
                </div>
                <p class="mt-2 text-sm leading-6">{{ recognitionReport.reviewReason }}</p>
              </div>

              <div class="mt-3 grid gap-3">
                <div class="rounded-xl border border-slate-200 px-3 py-3">
                  <p class="text-xs font-medium text-slate-500">页级人工复核标记</p>
                  <p class="mt-1 text-sm text-slate-800">{{ recognitionReport.pageReviewSummary }}</p>
                </div>
                <div class="rounded-xl border border-slate-200 px-3 py-3">
                  <p class="text-xs font-medium text-slate-500">问题条目</p>
                  <p class="mt-1 text-sm text-slate-800">{{ recognitionReport.issueSummary }}</p>
                </div>
              </div>
            </section>
          </div>

          <section class="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="text-sm font-semibold text-slate-800">问题清单</h3>
                <p class="mt-1 text-xs leading-5 text-slate-500">汇总任务级与页级识别问题，便于快速定位风险</p>
              </div>
              <span class="text-xs text-slate-400">{{ recognitionReport.issues.length }} 条</span>
            </div>

            <div v-if="recognitionReport.issues.length" class="mt-4 space-y-2">
              <div v-for="(issue, index) in recognitionReport.issues" :key="`${issue}-${index}`" class="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-800">
                {{ issue }}
              </div>
            </div>
            <div v-else class="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm text-emerald-700">
              当前任务没有检测到需要额外关注的问题，识别链路整体稳定。
            </div>
          </section>

          <section class="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="text-sm font-semibold text-slate-800">页级报告</h3>
                <p class="mt-1 text-xs leading-5 text-slate-500">逐页展示置信度、路由来源、重试与人工复核标记</p>
              </div>
              <span class="text-xs text-slate-400">{{ reportPages.length }} 页</span>
            </div>

            <div v-if="reportPages.length" class="mt-4 space-y-3">
              <div v-for="pageReport in reportPages" :key="`report-page-${pageReport.pageNumber}`" class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h4 class="text-sm font-semibold text-slate-800">第 {{ pageReport.pageNumber }} 页</h4>
                    <p class="mt-1 text-xs text-slate-500">{{ pageReport.sourceLabel }} · {{ pageReport.processingStrategyLabel }}</p>
                  </div>
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">置信度 {{ pageReport.confidenceLabel }}</span>
                    <span class="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">重试 {{ pageReport.retryCount }} 次</span>
                    <span class="rounded-full px-2.5 py-1 text-[11px] font-medium" :class="reportStatusBadgeClass(pageReport.reviewTone)">
                      {{ pageReport.reviewLabel }}
                    </span>
                  </div>
                </div>

                <div class="mt-3 grid grid-cols-2 gap-3">
                    <div class="rounded-xl border border-slate-200 bg-white px-3 py-3">
                      <p class="text-xs font-medium text-slate-500">主路原始置信度</p>
                      <p class="mt-1 text-sm text-slate-800">{{ pageReport.ocrConfidenceLabel }}</p>
                    </div>
                    <div class="rounded-xl border border-slate-200 bg-white px-3 py-3">
                      <p class="text-xs font-medium text-slate-500">第二路原始置信度</p>
                      <p class="mt-1 text-sm text-slate-800">{{ pageReport.secondaryConfidenceLabel }}</p>
                    </div>
                  <div class="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">复杂度</p>
                    <p class="mt-1 text-sm text-slate-800">{{ pageReport.pageComplexityLabel }}</p>
                  </div>
                </div>

                <div v-if="pageReport.routeReason || pageReport.reasoning || pageReport.reviewReason" class="mt-3 grid gap-3">
                  <div v-if="pageReport.routeReason" class="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">路由原因</p>
                    <p class="mt-1 text-sm leading-6 text-slate-700">{{ pageReport.routeReason }}</p>
                  </div>
                  <div v-if="pageReport.reasoning" class="rounded-xl border border-slate-200 bg-white px-3 py-3">
                    <p class="text-xs font-medium text-slate-500">识别说明</p>
                    <p class="mt-1 text-sm leading-6 text-slate-700">{{ pageReport.reasoning }}</p>
                  </div>
                  <div v-if="pageReport.reviewReason" class="rounded-xl border border-slate-200 bg-white px-3 py-3 md:col-span-2">
                    <p class="text-xs font-medium text-slate-500">复核原因</p>
                    <p class="mt-1 text-sm leading-6 text-slate-700">{{ pageReport.reviewReason }}</p>
                  </div>
                </div>

                <div v-if="pageReport.issues.length" class="mt-3 flex flex-wrap gap-2">
                  <span v-for="(issue, issueIndex) in pageReport.issues" :key="`${pageReport.pageNumber}-${issueIndex}`" class="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-medium text-amber-700">
                    {{ issue }}
                  </span>
                </div>
              </div>
            </div>
            <div v-else class="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
              当前任务尚未返回页级识别报告数据。
            </div>
          </section>
        </div>

        <pre v-else class="flex-1 overflow-auto bg-slate-950 px-4 py-3 text-xs leading-6 text-slate-100">{{ jsonText }}</pre>
      </section>
    </div>

    <transition name="fade">
      <div v-if="toast" class="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-slate-900 px-4 py-2 text-sm text-white shadow-lg">
        {{ toast }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  aiExtractFields,
  ensureFolderBatch,
  getBatchBoundaryAnalysis,
  getTask,
  getTaskFields,
  getTaskFileUrl,
  getTaskPageImageUrl,
  getTaskThumbnailUrl,
} from '@/api/ocr.js'
import EditableTable from '@/components/EditableTable.vue'
import { useResultViewState } from '@/composables/useResultViewState.js'
import { normalizeTaskForDisplay } from '@/utils/ocrDisplay.js'

const props = defineProps({
  id: {
    type: [String, Number],
    required: true,
  },
})

const router = useRouter()
const route = useRoute()

function goBack() {
  sessionStorage.setItem('ocr:selectedTab', 'history')
  router.push('/')
}

const taskIdRef = computed(() => props.id)
const {
  task: baseTask,
  resultData: baseResultData,
  loading,
  error,
  toast,
  activeTab,
  activeKey,
  pageNum,
  folderTasks,
  folderLoading,
  regionRefs,
  editingKey,
  editText,
  editingTableKey,
  tableDraft,
  previewImg,
  imgW,
  imgH,
  natW,
  natH,
  fileUrl: baseFileUrl,
  folderPath,
  folderSourcePath,
  materialContextKind,
  materialContextValue,
  folderLabel,
  pages: basePages,
  totalPages: baseTotalPages,
  isPdf: baseIsPdf,
  jsonText: baseJsonText,
  modeLabel,
  modeClass,
  polling,
  refreshing,
  formatTime,
  showToast,
  statusLabel,
  statusClass,
  switchTask,
  copyRegion,
  setRegionRef,
  startTextEdit,
  cancelTextEdit,
  startTableEdit,
  cancelTableEdit,
  cloneTableData,
  tableDataToText,
  saveTextEdit,
  saveTableEdit,
} = useResultViewState({
  taskId: taskIdRef,
  route,
  router,
})

const EMPTY_BOUNDARY_ANALYSIS = Object.freeze({
  batch_id: '',
  sequences: [],
  decisions: [],
  groups: [],
  task_to_group: {},
  summary: {
    sequence_count: 0,
    decision_count: 0,
    group_count: 0,
  },
  truth_updated_at: null,
})

const boundaryBatchId = ref('')
const boundaryLoading = ref(false)
const boundaryAnalysis = ref({ ...EMPTY_BOUNDARY_ANALYSIS })
const materialDetailCache = ref({})
const materialDetailsLoading = ref(false)
const expandedMaterialIds = ref({})
const cardPreviewFallbackStages = ref({})

function normalizePageList(value) {
  if (Array.isArray(value)) return value
  if (value && typeof value === 'object' && Array.isArray(value.pages)) {
    return value.pages
  }
  return []
}

function normalizeTaskPayload(value) {
  const raw = value && typeof value === 'object' ? value : {}
  const rawResultData = raw.result_data && typeof raw.result_data === 'object' ? raw.result_data : {}
  const pages = normalizePageList(rawResultData.pages ?? raw.result_json)
  return normalizeTaskForDisplay({
    ...raw,
    result_data: {
      ...rawResultData,
      pages,
    },
    result_json: pages,
  })
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value))
}

function aggregateMaterialStatus(tasks) {
  const statuses = tasks.map((item) => String(item?.status || '').trim().toLowerCase())
  if (statuses.includes('failed')) return 'failed'
  if (statuses.includes('human_review')) return 'human_review'
  if (statuses.some((status) => status === 'pending' || status === 'processing')) return 'processing'
  return 'done'
}

function latestMaterialTime(tasks) {
  return [...tasks]
    .map((item) => item?.updated_at || item?.created_at || '')
    .filter(Boolean)
    .sort()
    .at(-1) || ''
}

function buildMaterialTitle(tasks, material = null) {
  if (!tasks.length) return '未命名材料'
  const explicitTitle = String(material?.title || '').trim()
  if (explicitTitle) {
    return explicitTitle
  }
  const suggestedPdfFilename = String(material?.suggested_pdf_filename || '').trim()
  if (suggestedPdfFilename) {
    return suggestedPdfFilename.replace(/\.pdf$/i, '')
  }
  if (tasks.length === 1) return tasks[0].filename || `材料 #${tasks[0].id}`
  const firstName = String(tasks[0].filename || '').trim()
  const lastName = String(tasks[tasks.length - 1].filename || '').trim()
  if (firstName && lastName && firstName !== lastName) {
    return `${firstName} 至 ${lastName}`
  }
  return `${firstName || '合并材料'}（${tasks.length} 页）`
}

function materialSubtitle(tasks, material) {
  if (tasks.length <= 1) return '单页材料'
  const confidence = Number(material?.confidence ?? material?.sameDocumentConfidence ?? 0)
  const pageRange = material?.start_page && material?.end_page
    ? `页码 ${String(material.start_page).padStart(3, '0')}-${String(material.end_page).padStart(3, '0')}`
    : ''
  const confidenceLabel = Number.isFinite(confidence) && confidence > 0
    ? ` · 置信度 ${(confidence > 1 ? confidence : confidence * 100).toFixed(1)}%`
    : ''
  return `${tasks.length} 页合并材料${pageRange ? ` · ${pageRange}` : ''}${confidenceLabel}`
}

const taskOrderIndex = computed(() => new Map(
  (folderTasks.value || []).map((item, index) => [Number(item.id), index])
))

const folderTaskMap = computed(() => new Map(
  (folderTasks.value || []).map((item) => [Number(item.id), item])
))

const boundaryGroupById = computed(() => new Map(
  (Array.isArray(boundaryAnalysis.value?.groups) ? boundaryAnalysis.value.groups : [])
    .map((group) => [String(group?.group_id || ''), group])
    .filter(([groupId]) => groupId)
))

const manualMaterialGroups = ref([])
const draggingMaterialId = ref('')
const dragOverMaterialId = ref('')
const draggingMemberTaskId = ref(null)
const draggingMemberMaterialId = ref('')
const memberDragOverTaskId = ref(null)
const memberDragOverMaterialId = ref('')
const memberDragOverPosition = ref('')
const pendingMemberTaskId = ref(null)

const manualMaterialGroupsStorageKey = computed(() => {
  if (!materialContextKind.value || !materialContextValue.value) return ''
  return `ocr:manual-material-groups:${materialContextKind.value}:${materialContextValue.value}`
})

function canUseSessionStorage() {
  try {
    return typeof window !== 'undefined' && typeof window.sessionStorage !== 'undefined'
  } catch (_) {
    return false
  }
}

function readSessionStorage(key, fallback = null) {
  if (!key || !canUseSessionStorage()) return fallback
  try {
    const value = window.sessionStorage.getItem(key)
    return value ?? fallback
  } catch (_) {
    return fallback
  }
}

function writeSessionStorage(key, value) {
  if (!key || !canUseSessionStorage()) return
  try {
    window.sessionStorage.setItem(key, value)
  } catch (_) {
    // Ignore storage persistence failures so the page can still render.
  }
}

function removeSessionStorage(key) {
  if (!key || !canUseSessionStorage()) return
  try {
    window.sessionStorage.removeItem(key)
  } catch (_) {
    // Ignore storage cleanup failures so the page can still render.
  }
}

function sortTaskIds(taskIds) {
  return [...new Set(
    (Array.isArray(taskIds) ? taskIds : [])
      .map((taskId) => Number(taskId))
      .filter((taskId) => Number.isFinite(taskId))
  )].sort((left, right) => {
    const leftIndex = taskOrderIndex.value.get(left) ?? Number.MAX_SAFE_INTEGER
    const rightIndex = taskOrderIndex.value.get(right) ?? Number.MAX_SAFE_INTEGER
    if (leftIndex !== rightIndex) return leftIndex - rightIndex
    return left - right
  })
}

function normalizeTaskIds(taskIds, { sort = false } = {}) {
  const normalized = [...new Set(
    (Array.isArray(taskIds) ? taskIds : [])
      .map((taskId) => Number(taskId))
      .filter((taskId) => Number.isFinite(taskId))
  )]
  return sort
    ? sortTaskIds(normalized)
    : normalized
}

function normalizeManualGroupPayload(rawValue) {
  if (!Array.isArray(rawValue)) return []
  return rawValue
    .map((group, index) => {
      const id = String(group?.id || `manual-group-${index + 1}`).trim()
      const taskIds = normalizeTaskIds(group?.taskIds || group?.task_ids || [])
      const title = String(group?.title || '').trim()
      if (!id || taskIds.length <= 1) return null
      return {
        id,
        taskIds,
        title,
      }
    })
    .filter(Boolean)
}

function loadManualMaterialGroups() {
  const storageKey = manualMaterialGroupsStorageKey.value
  if (!storageKey) {
    manualMaterialGroups.value = []
    return
  }
  try {
    const parsed = JSON.parse(readSessionStorage(storageKey, '[]') || '[]')
    manualMaterialGroups.value = normalizeManualGroupPayload(parsed)
  } catch (_) {
    manualMaterialGroups.value = []
  }
}

function persistManualMaterialGroups(groups = normalizedManualMaterialGroups.value) {
  const storageKey = manualMaterialGroupsStorageKey.value
  if (!storageKey) return
  if (!groups.length) {
    removeSessionStorage(storageKey)
    return
  }
  writeSessionStorage(storageKey, JSON.stringify(groups))
}

const normalizedManualMaterialGroups = computed(() =>
  normalizeManualGroupPayload(manualMaterialGroups.value).map((group) => ({
    ...group,
    taskIds: group.taskIds.filter((taskId) => folderTaskMap.value.has(taskId)),
  })).filter((group) => group.taskIds.length > 1)
)

function buildMaterialEntry(id, tasks, group = null, options = {}) {
  const orderedTasks = Array.isArray(group?.task_ids) && group.task_ids.length
    ? group.task_ids.map((taskId) => tasks.find((task) => Number(task.id) === Number(taskId))).filter(Boolean)
    : Array.isArray(group?.taskIds) && group.taskIds.length
      ? group.taskIds.map((taskId) => tasks.find((task) => Number(task.id) === Number(taskId))).filter(Boolean)
      : [...tasks]
  return {
    id,
    isMerged: orderedTasks.length > 1,
    memberTasks: orderedTasks,
    memberTaskIds: orderedTasks.map((task) => Number(task.id)),
    representativeTaskId: orderedTasks[0]?.id ?? null,
    previewTaskId: orderedTasks[0]?.id ?? null,
    previewTask: orderedTasks[0] ?? null,
    title: buildMaterialTitle(orderedTasks, group),
    subtitle: materialSubtitle(orderedTasks, {
      confidence: group?.confidence,
      sameDocumentConfidence: group?.same_document_confidence,
      start_page: group?.start_page,
      end_page: group?.end_page,
    }),
    status: aggregateMaterialStatus(orderedTasks),
    updatedAt: latestMaterialTime(orderedTasks),
    confidence: Number(group?.confidence ?? group?.same_document_confidence ?? 0),
    suggested_pdf_filename: group?.suggested_pdf_filename || '',
    groupSource: options.groupSource || (group ? 'auto' : 'single'),
    reasons: Array.isArray(group?.reasons)
      ? group.reasons
      : Array.isArray(group?.decision_reasons)
        ? group.decision_reasons
        : [],
  }
}

const folderMaterials = computed(() => {
  const materials = []
  const usedTaskIds = new Set()
  const usedGroupIds = new Set()

  for (const manualGroup of normalizedManualMaterialGroups.value) {
    const groupedTasks = manualGroup.taskIds
      .map((taskId) => folderTaskMap.value.get(Number(taskId)))
      .filter(Boolean)
    if (groupedTasks.length <= 1) continue
    groupedTasks.forEach((item) => usedTaskIds.add(Number(item.id)))
    materials.push(buildMaterialEntry(manualGroup.id, groupedTasks, manualGroup, { groupSource: 'manual' }))
  }

  for (const folderTask of folderTasks.value || []) {
    const taskId = Number(folderTask.id)
    if (!Number.isFinite(taskId) || usedTaskIds.has(taskId)) continue

    const groupId = String(
      boundaryAnalysis.value?.task_to_group?.[taskId]
      ?? boundaryAnalysis.value?.task_to_group?.[String(taskId)]
      ?? ''
    ).trim()
    const group = groupId ? boundaryGroupById.value.get(groupId) : null
    const groupedTasks = Array.isArray(group?.task_ids)
      ? group.task_ids
        .map((memberTaskId) => folderTaskMap.value.get(Number(memberTaskId)))
        .filter((task) => task && !usedTaskIds.has(Number(task.id)))
      : []

    if (group && groupedTasks.length > 1 && !usedGroupIds.has(groupId)) {
      usedGroupIds.add(groupId)
      groupedTasks.forEach((item) => usedTaskIds.add(Number(item.id)))
      materials.push(buildMaterialEntry(groupId, groupedTasks, group, { groupSource: 'auto' }))
      continue
    }

    usedTaskIds.add(taskId)
    materials.push(buildMaterialEntry(`task-${taskId}`, [folderTask], null, { groupSource: 'single' }))
  }

  return materials
})

const currentMaterial = computed(() => {
  const currentTaskId = Number(props.id)
  return folderMaterials.value.find((material) => material.memberTaskIds.includes(currentTaskId)) || null
})

const currentMaterialId = computed(() => currentMaterial.value?.id || '')
const materialScopeLabel = computed(() => {
  if (materialContextKind.value === 'submission') return '提交范围'
  if (materialContextKind.value === 'batch') return '批次范围'
  return '目录'
})
const materialCountLabel = computed(() => {
  if (materialContextKind.value === 'submission') {
    return `${folderMaterials.value.length} 份同次提交材料`
  }
  if (materialContextKind.value === 'batch') {
    return `${folderMaterials.value.length} 份同批次材料`
  }
  return `${folderMaterials.value.length} 份同目录材料`
})

function isMaterialContextActive(material) {
  return Boolean(material && String(material.id) === String(currentMaterialId.value))
}

function isMaterialGroupActive(material) {
  return Boolean(material?.isMerged && isMaterialContextActive(material) && materialViewMode.value === 'merged')
}

function isMaterialExpanded(materialId) {
  return Boolean(expandedMaterialIds.value?.[materialId])
}

function setMaterialExpanded(materialId, expanded) {
  expandedMaterialIds.value = {
    ...expandedMaterialIds.value,
    [materialId]: expanded,
  }
}

function isPdfLikeTask(taskLike) {
  return String(taskLike?.file_type || '').trim().toLowerCase() === '.pdf'
}

function getCardPreviewCandidates(taskLike) {
  const taskId = Number(taskLike?.id)
  if (!Number.isFinite(taskId)) return []

  const candidates = isPdfLikeTask(taskLike)
    ? [getTaskPageImageUrl(taskId, 1), getTaskThumbnailUrl(taskId)]
    : [getTaskFileUrl(taskId), getTaskThumbnailUrl(taskId)]

  return [...new Set(candidates.filter(Boolean))]
}

function getCardPreviewUrl(taskLike, cacheKey) {
  const candidates = getCardPreviewCandidates(taskLike)
  const fallbackStage = Number(cardPreviewFallbackStages.value?.[cacheKey] || 0)
  return candidates[fallbackStage] || candidates[0] || ''
}

function hasCardPreview(taskLike, cacheKey) {
  const candidates = getCardPreviewCandidates(taskLike)
  const fallbackStage = Number(cardPreviewFallbackStages.value?.[cacheKey] || 0)
  return fallbackStage < candidates.length && Boolean(candidates[fallbackStage] || candidates[0])
}

function onCardPreviewError(taskLike, cacheKey) {
  const candidates = getCardPreviewCandidates(taskLike)
  if (!candidates.length) return
  const fallbackStage = Number(cardPreviewFallbackStages.value?.[cacheKey] || 0)
  if (fallbackStage + 1 >= candidates.length) {
    cardPreviewFallbackStages.value = {
      ...cardPreviewFallbackStages.value,
      [cacheKey]: candidates.length,
    }
    return
  }
  cardPreviewFallbackStages.value = {
    ...cardPreviewFallbackStages.value,
    [cacheKey]: fallbackStage + 1,
  }
}

function toggleMaterialExpanded(materialId) {
  setMaterialExpanded(materialId, !isMaterialExpanded(materialId))
}

function materialById(materialId) {
  return folderMaterials.value.find((material) => String(material.id) === String(materialId)) || null
}

function canMergeMaterials(sourceMaterial, targetMaterial) {
  if (!sourceMaterial || !targetMaterial) return false
  if (String(sourceMaterial.id) === String(targetMaterial.id)) return false
  return !sourceMaterial.memberTaskIds.some((taskId) => targetMaterial.memberTaskIds.includes(taskId))
}

function createManualGroupId() {
  return `manual-group-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function upsertManualGroup(material, nextTaskIds) {
  const normalizedTaskIds = normalizeTaskIds(nextTaskIds)
  if (normalizedTaskIds.length <= 1) return

  const nextGroupId = String(material?.id || createManualGroupId()).trim() || createManualGroupId()
  const existingManualGroup = normalizedManualMaterialGroups.value.find(
    (group) => String(group.id) === nextGroupId
  )
  const nextGroupTitle = String(existingManualGroup?.title || material?.title || '').trim()

  manualMaterialGroups.value = [
    ...normalizedManualMaterialGroups.value
      .filter((group) => String(group.id) !== nextGroupId)
      .filter((group) => !group.taskIds.some((taskId) => normalizedTaskIds.includes(taskId))),
    {
      id: nextGroupId,
      taskIds: normalizedTaskIds,
      title: nextGroupTitle,
    },
  ]

  setMaterialExpanded(nextGroupId, true)
}

function mergeMaterials(sourceMaterial, targetMaterial) {
  if (!canMergeMaterials(sourceMaterial, targetMaterial)) return

  const mergedTaskIds = sortTaskIds([
    ...targetMaterial.memberTaskIds,
    ...sourceMaterial.memberTaskIds,
  ])
  const targetGroupId = normalizedManualMaterialGroups.value.find(
    (group) => String(group.id) === String(targetMaterial.id)
  )?.id || targetMaterial.id || createManualGroupId()
  upsertManualGroup({ ...targetMaterial, id: targetGroupId }, mergedTaskIds)
}

function ungroupMaterial(material) {
  if (!material || material.groupSource !== 'manual') return
  manualMaterialGroups.value = normalizedManualMaterialGroups.value.filter(
    (group) => String(group.id) !== String(material.id)
  )
}

function onMaterialDragStart(material, event) {
  if (!material?.memberTaskIds?.length) return
  draggingMaterialId.value = String(material.id)
  dragOverMaterialId.value = ''
  if (event?.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(material.id))
  }
}

function onMaterialDragEnd() {
  draggingMaterialId.value = ''
  dragOverMaterialId.value = ''
}

function onMaterialDragOver(material) {
  const sourceMaterial = materialById(draggingMaterialId.value)
  dragOverMaterialId.value = canMergeMaterials(sourceMaterial, material) ? String(material.id) : ''
}

function onMaterialDragLeave(material, event) {
  const relatedTarget = event?.relatedTarget
  if (!relatedTarget || !event?.currentTarget?.contains?.(relatedTarget)) {
    if (String(dragOverMaterialId.value) === String(material?.id || '')) {
      dragOverMaterialId.value = ''
    }
  }
}

function onMaterialDrop(material) {
  const sourceMaterial = materialById(draggingMaterialId.value)
  if (canMergeMaterials(sourceMaterial, material)) {
    mergeMaterials(sourceMaterial, material)
  }
  draggingMaterialId.value = ''
  dragOverMaterialId.value = ''
}

function onMaterialMemberDragStart(material, memberTask, event) {
  if (!material?.isMerged || !memberTask?.id) return
  event?.stopPropagation?.()
  draggingMemberMaterialId.value = String(material.id)
  draggingMemberTaskId.value = Number(memberTask.id)
  memberDragOverMaterialId.value = ''
  memberDragOverTaskId.value = null
  memberDragOverPosition.value = ''
  if (event?.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(memberTask.id))
  }
}

function onMaterialMemberDragEnd(event) {
  event?.stopPropagation?.()
  draggingMemberMaterialId.value = ''
  draggingMemberTaskId.value = null
  memberDragOverMaterialId.value = ''
  memberDragOverTaskId.value = null
  memberDragOverPosition.value = ''
}

function canReorderMaterialMembers(material, memberTask) {
  if (!material?.isMerged || !memberTask?.id) return false
  if (String(draggingMemberMaterialId.value) !== String(material.id)) return false
  if (!Number.isFinite(Number(draggingMemberTaskId.value))) return false
  return Number(draggingMemberTaskId.value) !== Number(memberTask.id)
}

function resolveMemberDropPosition(event) {
  const rect = event?.currentTarget?.getBoundingClientRect?.()
  if (!rect) return 'before'
  const offsetY = Number(event?.clientY || 0) - rect.top
  return offsetY > rect.height / 2 ? 'after' : 'before'
}

function onMaterialMemberDragOver(material, memberTask, event) {
  if (canReorderMaterialMembers(material, memberTask)) {
    memberDragOverMaterialId.value = String(material.id)
    memberDragOverTaskId.value = Number(memberTask.id)
    memberDragOverPosition.value = resolveMemberDropPosition(event)
    return
  }
  memberDragOverMaterialId.value = ''
  memberDragOverTaskId.value = null
  memberDragOverPosition.value = ''
}

function onMaterialMemberDragLeave(material, memberTask, event) {
  event?.stopPropagation?.()
  const relatedTarget = event?.relatedTarget
  if (!relatedTarget || !event?.currentTarget?.contains?.(relatedTarget)) {
    if (
      String(memberDragOverMaterialId.value) === String(material?.id || '')
      && Number(memberDragOverTaskId.value) === Number(memberTask?.id)
    ) {
      memberDragOverMaterialId.value = ''
      memberDragOverTaskId.value = null
      memberDragOverPosition.value = ''
    }
  }
}

function reorderMaterialMembers(material, draggedTaskId, targetTaskId, position = 'before') {
  const orderedTaskIds = normalizeTaskIds(material?.memberTaskIds || [])
  const fromIndex = orderedTaskIds.findIndex((taskId) => Number(taskId) === Number(draggedTaskId))
  const targetIndex = orderedTaskIds.findIndex((taskId) => Number(taskId) === Number(targetTaskId))
  if (fromIndex < 0 || targetIndex < 0 || fromIndex === targetIndex) return

  const nextTaskIds = [...orderedTaskIds]
  const [movedTaskId] = nextTaskIds.splice(fromIndex, 1)
  let insertionIndex = targetIndex
  if (fromIndex < targetIndex) {
    insertionIndex = position === 'after' ? targetIndex : targetIndex - 1
  } else {
    insertionIndex = position === 'after' ? targetIndex + 1 : targetIndex
  }
  const clampedIndex = Math.max(0, Math.min(nextTaskIds.length, insertionIndex))
  nextTaskIds.splice(clampedIndex, 0, movedTaskId)
  upsertManualGroup(material, nextTaskIds)
}

function canMoveMaterialMember(material, taskId, step) {
  const orderedTaskIds = normalizeTaskIds(material?.memberTaskIds || [])
  const index = orderedTaskIds.findIndex((item) => Number(item) === Number(taskId))
  if (index < 0) return false
  const targetIndex = index + Number(step)
  return targetIndex >= 0 && targetIndex < orderedTaskIds.length
}

function moveMaterialMemberByStep(material, taskId, step) {
  if (!canMoveMaterialMember(material, taskId, step)) return
  const orderedTaskIds = normalizeTaskIds(material?.memberTaskIds || [])
  const fromIndex = orderedTaskIds.findIndex((item) => Number(item) === Number(taskId))
  const targetIndex = fromIndex + Number(step)
  const nextTaskIds = [...orderedTaskIds]
  const [movedTaskId] = nextTaskIds.splice(fromIndex, 1)
  nextTaskIds.splice(targetIndex, 0, movedTaskId)
  upsertManualGroup(material, nextTaskIds)
}

function onMaterialMemberDrop(material, memberTask) {
  if (canReorderMaterialMembers(material, memberTask)) {
    reorderMaterialMembers(
      material,
      draggingMemberTaskId.value,
      memberTask.id,
      memberDragOverPosition.value || 'before'
    )
  }
  draggingMemberMaterialId.value = ''
  draggingMemberTaskId.value = null
  memberDragOverMaterialId.value = ''
  memberDragOverTaskId.value = null
  memberDragOverPosition.value = ''
}

function openMaterial(material) {
  if (!material) return
  if (material.isMerged) {
    setMaterialExpanded(material.id, true)
  }
  if (material.representativeTaskId) {
    navigateToMaterialTask(material.representativeTaskId, material.isMerged ? 'merged' : 'single')
  }
}

const materialViewMode = computed(() => (String(route.query.material_view || '').trim().toLowerCase() === 'merged' ? 'merged' : 'single'))

function buildResultRoute(nextTaskId, viewMode = 'single') {
  const query = {}
  if (materialContextKind.value === 'folder' && materialContextValue.value) {
    query.folder = materialContextValue.value
  } else if (materialContextKind.value === 'submission' && materialContextValue.value) {
    query.submission_id = materialContextValue.value
  } else if (materialContextKind.value === 'batch' && materialContextValue.value) {
    query.batch_id = materialContextValue.value
  }
  if (viewMode === 'merged') {
    query.material_view = 'merged'
  }
  return {
    path: `/result/${nextTaskId}`,
    query,
  }
}

function navigateToMaterialTask(nextTaskId, viewMode = 'single', { replace = false } = {}) {
  const routeTarget = buildResultRoute(nextTaskId, viewMode)
  const isSameTask = String(nextTaskId) === String(props.id)
  const isSameViewMode = materialViewMode.value === viewMode
  if (isSameTask && isSameViewMode) {
    return
  }
  if (isSameTask) {
    router.replace(routeTarget)
    return
  }
  const navigate = replace ? router.replace : router.push
  navigate(routeTarget)
}

function isMemberTaskActive(taskId) {
  if (pendingMemberTaskId.value !== null && pendingMemberTaskId.value !== undefined) {
    return Number(pendingMemberTaskId.value) === Number(taskId)
  }
  if (isMergedMaterialView.value) {
    return false
  }
  const activeTaskId = pendingMemberTaskId.value ?? Number(props.id)
  return Number(activeTaskId) === Number(taskId)
}

function openMaterialMember(material, taskId) {
  if (!taskId) return
  if (material?.isMerged) {
    setMaterialExpanded(material.id, true)
  }
  pendingMemberTaskId.value = Number(taskId)
  navigateToMaterialTask(taskId, 'single', { replace: true })
}

async function loadBoundaryAnalysis() {
  if (!folderPath.value || !folderTasks.value?.length) {
    boundaryBatchId.value = ''
    boundaryAnalysis.value = { ...EMPTY_BOUNDARY_ANALYSIS }
    return
  }

  boundaryLoading.value = true
  try {
    let batchId = String(
      baseTask.value?.batch_id
      || folderTasks.value.find((item) => item?.batch_id)?.batch_id
      || ''
    ).trim()

    if (!batchId && materialContextKind.value === 'folder' && folderSourcePath.value) {
      const { data } = await ensureFolderBatch(folderSourcePath.value)
      batchId = String(data?.batch_id || '').trim()
    }

    boundaryBatchId.value = batchId
    if (!batchId) {
      boundaryAnalysis.value = { ...EMPTY_BOUNDARY_ANALYSIS }
      return
    }

    const normalizeBoundaryPayload = (data) => ({
      ...EMPTY_BOUNDARY_ANALYSIS,
      ...data,
      groups: Array.isArray(data?.groups) ? data.groups : [],
      task_to_group: data?.task_to_group && typeof data.task_to_group === 'object' ? data.task_to_group : {},
    })

    const hasMergedGroup = (payload) => Array.isArray(payload?.groups)
      && payload.groups.some((group) => Array.isArray(group?.task_ids) && group.task_ids.length > 1)

    let response = await getBatchBoundaryAnalysis(batchId, { forceRefresh: false })
    let payload = response?.data && typeof response.data === 'object' && response.data.batch_id
      ? normalizeBoundaryPayload(response.data)
      : null

    if (
      payload
      && !hasMergedGroup(payload)
      && (folderTasks.value?.length || 0) > 1
    ) {
      response = await getBatchBoundaryAnalysis(batchId, { forceRefresh: true })
      payload = response?.data && typeof response.data === 'object' && response.data.batch_id
        ? normalizeBoundaryPayload(response.data)
        : payload
    }

    if (payload?.batch_id) {
      boundaryAnalysis.value = payload
      return
    }

    boundaryAnalysis.value = { ...EMPTY_BOUNDARY_ANALYSIS }
  } catch (error) {
    console.warn('Failed to load boundary analysis for folder materials.', error)
    boundaryAnalysis.value = { ...EMPTY_BOUNDARY_ANALYSIS }
  } finally {
    boundaryLoading.value = false
  }
}

async function ensureCurrentMaterialDetails(material) {
  if (!material?.isMerged) return
  const currentTaskId = Number(props.id)
  const missingIds = material.memberTaskIds.filter(
    (taskId) => Number(taskId) !== currentTaskId && !materialDetailCache.value?.[taskId]
  )
  if (!missingIds.length) return

  materialDetailsLoading.value = true
  try {
    const results = await Promise.all(
      missingIds.map(async (taskId) => {
        try {
          const { data } = await getTask(taskId)
          return [taskId, normalizeTaskPayload(data)]
        } catch (_) {
          return [taskId, null]
        }
      })
    )

    const nextCache = { ...materialDetailCache.value }
    for (const [taskId, detail] of results) {
      if (detail) {
        nextCache[taskId] = detail
      }
    }
    materialDetailCache.value = nextCache
  } finally {
    materialDetailsLoading.value = false
  }
}

watch(
  () => currentMaterial.value?.id,
  async () => {
    if (currentMaterial.value?.id) {
      setMaterialExpanded(currentMaterial.value.id, true)
    }
    await ensureCurrentMaterialDetails(currentMaterial.value)
  },
  { immediate: true }
)

watch(
  () => `${props.id}:${route.fullPath}`,
  () => {
    pendingMemberTaskId.value = null
  },
  { immediate: true }
)

watch(
  () => `${manualMaterialGroupsStorageKey.value}::${(folderTasks.value || []).map((item) => item.id).join('|')}`,
  () => {
    loadManualMaterialGroups()
  },
  { immediate: true }
)

watch(
  normalizedManualMaterialGroups,
  () => {
    persistManualMaterialGroups(normalizedManualMaterialGroups.value)
  },
  { deep: true }
)

watch(
  () => `${folderPath.value}::${(folderTasks.value || []).map((item) => `${item.id}:${item.status}:${item.batch_id || ''}`).join('|')}::${baseTask.value?.batch_id || ''}`,
  async () => {
    await loadBoundaryAnalysis()
  },
  { immediate: true }
)

const currentMaterialDetails = computed(() => {
  const normalizedBaseTask = normalizeTaskPayload(baseTask.value)
  const material = currentMaterial.value
  if (!material?.isMerged) {
    return normalizedBaseTask?.id ? [normalizedBaseTask] : []
  }

  return material.memberTaskIds
    .map((taskId) => {
      if (Number(taskId) === Number(props.id)) {
        return normalizedBaseTask
      }
      return materialDetailCache.value?.[taskId] || null
    })
    .filter(Boolean)
})

const currentMaterialDetailsReady = computed(() => {
  const material = currentMaterial.value
  if (!material?.isMerged) return true
  return material.memberTaskIds.every((taskId) =>
    Number(taskId) === Number(props.id) || Boolean(materialDetailCache.value?.[taskId])
  )
})

function buildMergedPages(taskDetails) {
  let pageCounter = 1
  const mergedPages = []

  for (const taskDetail of taskDetails) {
    const taskPages = normalizePageList(taskDetail?.result_data?.pages ?? taskDetail?.result_json)
    for (let index = 0; index < taskPages.length; index += 1) {
      const page = taskPages[index]
      const clonedPage = deepClone(page)
      clonedPage.page_num = pageCounter
      clonedPage._material_source_task_id = Number(taskDetail.id)
      clonedPage._material_source_page_num = Number(page?.page_num) || index + 1
      clonedPage._material_source_file_type = String(taskDetail.file_type || '')
      clonedPage._material_source_filename = taskDetail.filename || ''
      mergedPages.push(clonedPage)
      pageCounter += 1
    }
  }

  return mergedPages
}

const mergedMaterialPages = computed(() => {
  if (!currentMaterial.value?.isMerged || !currentMaterialDetailsReady.value) {
    return basePages.value
  }
  return buildMergedPages(currentMaterialDetails.value)
})

const mergedMaterialFullText = computed(() => {
  if (!currentMaterial.value?.isMerged || !currentMaterialDetailsReady.value) {
    return String(baseTask.value?.full_text || '')
  }
  return currentMaterialDetails.value
    .map((detail) => String(detail?.full_text || '').trim())
    .filter(Boolean)
    .join('\n\n')
})

const isMergedMaterialView = computed(() =>
  Boolean(
    materialViewMode.value === 'merged'
    && currentMaterial.value?.isMerged
    && currentMaterialDetailsReady.value
  )
)

const task = computed(() => {
  if (!isMergedMaterialView.value) {
    return baseTask.value
  }

  const material = currentMaterial.value
  const base = normalizeTaskPayload(baseTask.value)
  const mergedPages = mergedMaterialPages.value
  return {
    ...base,
    filename: material?.title || base?.filename || '合并材料',
    page_count: mergedPages.length || material?.memberTaskIds?.length || 0,
    full_text: mergedMaterialFullText.value,
    status: material?.status || base?.status || 'done',
    batch_id: boundaryBatchId.value || base?.batch_id || '',
    review_status: material?.status === 'human_review'
      ? 'pending_human_review'
      : (base?.review_status || ''),
    review_reason: material?.reasons?.length
      ? material.reasons.join('；')
      : (base?.review_reason || ''),
    updated_at: material?.updatedAt || base?.updated_at || base?.created_at || '',
    result_json: mergedPages,
    result_data: {
      ...(base?.result_data || {}),
      pages: mergedPages,
      material_group_id: material?.id || '',
      material_task_ids: material?.memberTaskIds || [],
    },
    agent_meta: {
      ...(base?.agent_meta && typeof base.agent_meta === 'object' ? base.agent_meta : {}),
      material_group_id: material?.id || '',
      material_task_ids: material?.memberTaskIds || [],
      material_member_count: material?.memberTaskIds?.length || 0,
      same_document_confidence: material?.confidence || 0,
      material_decision_reasons: material?.reasons || [],
    },
  }
})

const resultData = computed(() => {
  if (!isMergedMaterialView.value) {
    return baseResultData.value
  }
  return task.value?.result_data || { pages: [] }
})

const pages = computed(() => (isMergedMaterialView.value ? mergedMaterialPages.value : basePages.value))
const totalPages = computed(() => (isMergedMaterialView.value ? mergedMaterialPages.value.length || 1 : baseTotalPages.value))
const currentPage = computed(() => pages.value[pageNum.value - 1] || { regions: [], lines: [] })
const jsonText = computed(() => (isMergedMaterialView.value ? JSON.stringify(resultData.value, null, 2) : baseJsonText.value))

const mergedPreviewPageRefs = ref({})

function setMergedPreviewPageRef(pageNumber, element) {
  if (element) {
    mergedPreviewPageRefs.value[pageNumber] = element
  } else {
    delete mergedPreviewPageRefs.value[pageNumber]
  }
}

const mergedPreviewEntries = computed(() => {
  if (!isMergedMaterialView.value) return []
  return mergedMaterialPages.value.map((page, pageIndex) => {
    const taskId = Number(page?._material_source_task_id || props.id)
    const sourcePageNum = Number(page?._material_source_page_num || pageIndex + 1)
    const fileType = String(page?._material_source_file_type || '')
    const isPdfPage = fileType.toLowerCase() === '.pdf'
    return {
      key: `merged-preview-${taskId}-${sourcePageNum}-${pageIndex + 1}`,
      pageNumber: pageIndex + 1,
      taskId,
      sourcePageNum,
      sourcePageLabel: String(sourcePageNum).padStart(3, '0'),
      filename: String(page?._material_source_filename || task.value?.filename || `第 ${pageIndex + 1} 页`),
      imageUrl: isPdfPage ? getTaskPageImageUrl(taskId, sourcePageNum) : getTaskFileUrl(taskId),
    }
  })
})

const currentPreviewSource = computed(() => {
  if (!isMergedMaterialView.value) {
    return {
      taskId: Number(props.id),
      pageNum: pageNum.value,
      fileType: String(baseTask.value?.file_type || ''),
    }
  }

  return {
    taskId: Number(currentPage.value?._material_source_task_id || props.id),
    pageNum: Number(currentPage.value?._material_source_page_num || 1),
    fileType: String(currentPage.value?._material_source_file_type || ''),
  }
})

const isPdf = computed(() => {
  if (!isMergedMaterialView.value) return baseIsPdf.value
  return currentPreviewSource.value.fileType.toLowerCase() === '.pdf'
})

const fileUrl = computed(() => {
  if (!isMergedMaterialView.value) return baseFileUrl.value
  return getTaskFileUrl(currentPreviewSource.value.taskId)
})

const pendingActiveKey = ref('')
const pdfImgFailed = ref(false)
const previewImageUrl = computed(() => {
  if (isMergedMaterialView.value) {
    return isPdf.value
      ? getTaskPageImageUrl(currentPreviewSource.value.taskId, currentPreviewSource.value.pageNum)
      : getTaskFileUrl(currentPreviewSource.value.taskId)
  }
  return isPdf.value ? getTaskPageImageUrl(props.id, pageNum.value) : fileUrl.value
})

function copyAllContent() {
  navigator.clipboard.writeText(String(task.value?.full_text || '')).then(() => showToast('已复制全文。'))
}

function downloadTxtContent() {
  const blob = new Blob([String(task.value?.full_text || '')], { type: 'text/plain;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${task.value?.filename || 'result'}.txt`
  link.click()
}

function onImgError() {
  if (isPdf.value) pdfImgFailed.value = true
}

watch(
  () => `${currentPreviewSource.value.taskId}:${currentPreviewSource.value.pageNum}:${isPdf.value}`,
  () => {
    pdfImgFailed.value = false
  },
  { immediate: true }
)


const currentPreviewItems = computed(() => buildPreviewItems(currentPage.value, pageNum.value - 1))
const allItems = computed(() =>
  (Array.isArray(pages.value) ? pages.value : []).flatMap((page, pageIndex) => {
    const items = []
    if (pages.value.length > 1) {
      items.push({
        _key: `page-${pageIndex + 1}`,
        _pageSeparator: true,
        _pageNumber: pageIndex + 1,
      })
    }
    return [...items, ...buildPageItems(page, pageIndex)]
  })
)
const isTaskProcessing = computed(() => ['pending', 'processing'].includes(String(task.value?.status || '')))
const isTaskFailed = computed(() => String(task.value?.status || '') === 'failed')

const REPORT_SOURCE_LABELS = {
  ocr: 'PP-OCRv5 主路',
  ppocr_vl: 'PP-OCR-VL-1.5 第二路',
  vl: 'PP-OCR-VL-1.5 第二路',
  hybrid: '双路融合',
  fallback: '回退结果',
}

const REPORT_REVIEW_STATUS_LABELS = {
  approved: '自动通过',
  approved_by_human: '人工确认通过',
  pending_human_review: '待人工复核',
  required: '需要人工复核',
  resume_requested: '已提交复核恢复',
}

const REPORT_REVIEW_DECISION_LABELS = {
  pass: '通过',
  review: '复核',
  human: '人工确认',
  progress: '处理中',
}

function normalizeReportText(value, fallback = '未提供') {
  const text = String(value || '').trim()
  return text || fallback
}

function safeMetricNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeReportIssues(values) {
  return Array.isArray(values)
    ? values.map((value) => String(value || '').trim()).filter(Boolean)
    : []
}

function uniqueReportIssues(values) {
  return [...new Set(normalizeReportIssues(values))]
}

function averageMetric(values) {
  if (!values.length) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function formatConfidenceLabel(value) {
  const normalized = safeMetricNumber(value)
  if (normalized === null) return '--'
  const ratio = normalized > 1 ? normalized / 100 : normalized
  return `${(ratio * 100).toFixed(1)}%`
}

function formatRawConfidenceLabel(value, available = true) {
  if (!available) return '未提供'
  const label = formatConfidenceLabel(value)
  return label === '--' ? '未提供' : label
}

function formatComplexityLabel(value) {
  const normalized = safeMetricNumber(value)
  if (normalized === null) return '--'
  return normalized.toFixed(3)
}

function reportStatusTone(reviewStatus, taskStatus, humanReview) {
  if (taskStatus === 'failed') return 'danger'
  if (reviewStatus === 'approved_by_human') return 'success'
  if (reviewStatus === 'pending_human_review' || reviewStatus === 'required' || humanReview) return 'warning'
  if (taskStatus === 'pending' || taskStatus === 'processing') return 'info'
  return 'success'
}

function reportStatusBadgeClass(tone) {
  return {
    success: 'bg-emerald-100 text-emerald-700',
    warning: 'bg-amber-100 text-amber-700',
    danger: 'bg-red-100 text-red-700',
    info: 'bg-blue-100 text-blue-700',
  }[tone] || 'bg-slate-100 text-slate-600'
}

function reportStatusPanelClass(tone) {
  return {
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    warning: 'border-amber-200 bg-amber-50 text-amber-800',
    danger: 'border-red-200 bg-red-50 text-red-800',
    info: 'border-blue-200 bg-blue-50 text-blue-800',
  }[tone] || 'border-slate-200 bg-slate-50 text-slate-700'
}

function reviewStatusLabel(value, taskStatus, humanReview) {
  const normalized = String(value || '').trim().toLowerCase()
  if (REPORT_REVIEW_STATUS_LABELS[normalized]) return REPORT_REVIEW_STATUS_LABELS[normalized]
  if (taskStatus === 'failed') return '处理异常'
  if (humanReview) return '待人工复核'
  if (taskStatus === 'pending' || taskStatus === 'processing') return '后台处理中'
  if (taskStatus === 'human_review') return '待人工复核'
  return '自动通过'
}

function reviewDecisionLabel(value, taskStatus, humanReview) {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'approved_by_human') return REPORT_REVIEW_DECISION_LABELS.human
  if (normalized === 'pending_human_review' || normalized === 'required' || humanReview) return REPORT_REVIEW_DECISION_LABELS.review
  if (taskStatus === 'pending' || taskStatus === 'processing') return REPORT_REVIEW_DECISION_LABELS.progress
  return REPORT_REVIEW_DECISION_LABELS.pass
}

const taskAgentMeta = computed(() => (task.value?.agent_meta && typeof task.value.agent_meta === 'object' ? task.value.agent_meta : {}))
const reviewPayload = computed(() => (task.value?.human_review_payload && typeof task.value.human_review_payload === 'object' ? task.value.human_review_payload : {}))

const reportPages = computed(() =>
  (Array.isArray(pages.value) ? pages.value : []).map((page, pageIndex) => {
    const meta = page?.agent_meta && typeof page.agent_meta === 'object' ? page.agent_meta : {}
    const secondaryConfidence = safeMetricNumber(meta.ppocr_vl_confidence ?? meta.vl_confidence)
    const ocrConfidenceAvailable = meta.ocr_confidence_available !== false
    const secondaryConfidenceAvailable = meta.ppocr_vl_confidence_available !== false && meta.vl_confidence_available !== false
    const reviewStatusValue = String(meta.review_status || '').trim().toLowerCase()
    const humanReview = Boolean(meta.human_review)
    const tone = reportStatusTone(reviewStatusValue, String(task.value?.status || '').trim().toLowerCase(), humanReview)
    return {
      pageNumber: Number(page?.page_num) || pageIndex + 1,
      source: String(meta.source || '').trim().toLowerCase(),
      sourceLabel: REPORT_SOURCE_LABELS[String(meta.source || '').trim().toLowerCase()] || normalizeReportText(meta.source, '未标注来源'),
      confidence: safeMetricNumber(meta.confidence),
      confidenceLabel: formatConfidenceLabel(meta.confidence),
      ocrConfidenceLabel: formatRawConfidenceLabel(meta.ocr_confidence, ocrConfidenceAvailable),
      secondaryConfidenceLabel: formatRawConfidenceLabel(secondaryConfidence, secondaryConfidenceAvailable),
      pageComplexity: safeMetricNumber(meta.page_complexity),
      pageComplexityLabel: formatComplexityLabel(meta.page_complexity),
      retryCount: Number(meta.retry_count || 0),
      processingStrategyLabel: normalizeReportText(meta.processing_strategy, '默认策略'),
      routeReason: String(meta.route_reason || '').trim(),
      reasoning: String(meta.reasoning || '').trim(),
      reviewReason: String(meta.review_reason || '').trim(),
      issues: uniqueReportIssues(meta.issues),
      reviewTone: tone,
      reviewLabel: humanReview ? '页级建议复核' : '页级自动通过',
      reviewStatusValue,
      humanReview,
    }
  })
)

const recognitionReport = computed(() => {
  const rootMeta = taskAgentMeta.value
  const taskStatus = String(task.value?.status || '').trim().toLowerCase()
  const reviewStatusValue = String(task.value?.review_status || rootMeta.review_status || reviewPayload.value.review_status || '').trim().toLowerCase()
  const reviewReason = String(task.value?.review_reason || rootMeta.review_reason || reviewPayload.value.review_reason || '').trim()
    || (taskStatus === 'failed' ? normalizeReportText(task.value?.error_message, '处理失败') : '当前任务未触发人工复核。')
  const pageConfidenceValues = reportPages.value
    .map((page) => page.confidence)
    .filter((value) => value !== null)
  const pageComplexities = reportPages.value
    .map((page) => page.pageComplexity)
    .filter((value) => value !== null)
  const sourceCounts = reportPages.value.reduce((accumulator, page) => {
    const key = page.sourceLabel
    accumulator[key] = (accumulator[key] || 0) + 1
    return accumulator
  }, {})
  const pipelineSummary = Object.keys(sourceCounts).length
    ? Object.entries(sourceCounts).map(([label, count]) => `${label} ${count} 页`).join(' / ')
    : '当前任务暂无可展示的链路统计'
  const issues = uniqueReportIssues([
    ...(rootMeta.issues || []),
    ...(reviewPayload.value.issues || []),
    ...reportPages.value.flatMap((page) => page.issues),
  ])
  const primaryPage = reportPages.value[0] || null
  const pagesWithReview = reportPages.value.filter((page) => page.humanReview).length
  const tone = reportStatusTone(reviewStatusValue, taskStatus, pagesWithReview > 0 || taskStatus === 'human_review')

  return {
    reviewStatusTone: tone,
    reviewStatusLabel: reviewStatusLabel(reviewStatusValue, taskStatus, pagesWithReview > 0 || taskStatus === 'human_review'),
    reviewDecision: reviewDecisionLabel(reviewStatusValue, taskStatus, pagesWithReview > 0 || taskStatus === 'human_review'),
    reviewReason,
    issues,
    issueSummary: issues.length ? `共发现 ${issues.length} 条问题/提示信息` : '未发现异常问题',
    pageReviewSummary: reportPages.value.length ? `${pagesWithReview} / ${reportPages.value.length} 页带有页级复核标记` : '暂无页级数据',
    pipelineSummary,
    workflow: normalizeReportText(rootMeta.workflow, '未标注工作流'),
    workflowThreadId: normalizeReportText(task.value?.workflow_thread_id || rootMeta.workflow_thread_id || reviewPayload.value.workflow_thread_id, '未生成'),
    ocrBackend: normalizeReportText(rootMeta.ocr_backend, '未标注 OCR 后端'),
    secondaryBackend: normalizeReportText(rootMeta.llm_backend || rootMeta.vl_backend || 'PP-OCR-VL-1.5', '未标注第二路后端'),
    overallConfidence: formatConfidenceLabel(rootMeta.overall_confidence ?? averageMetric(pageConfidenceValues)),
    averageComplexity: formatComplexityLabel(averageMetric(pageComplexities)),
    sourceSummary: pipelineSummary,
    retrySummary: reportPages.value.length ? `${reportPages.value.filter((page) => page.retryCount > 0).length} 页发生过重试` : '暂无重试记录',
    primaryRouteReason: primaryPage?.routeReason || '',
    primaryReasoning: primaryPage?.reasoning || '',
  }
})

const reportOverviewCards = computed(() => [
  {
    label: '任务状态',
    value: statusLabel(task.value?.status),
    hint: recognitionReport.value.reviewDecision,
  },
  {
    label: '复核结论',
    value: recognitionReport.value.reviewStatusLabel,
    hint: recognitionReport.value.reviewReason,
  },
  {
    label: '总体置信度',
    value: recognitionReport.value.overallConfidence,
    hint: recognitionReport.value.sourceSummary,
  },
  {
    label: '平均复杂度',
    value: recognitionReport.value.averageComplexity,
    hint: recognitionReport.value.retrySummary,
  },
])

const FIELD_LABELS = [
  { key: '档号', icon: '#' },
  { key: '文号', icon: '§' },
  { key: '题名', icon: 'T' },
  { key: '责任者', icon: '人' },
  { key: '日期', icon: '日' },
  { key: '页数', icon: '页' },
  { key: '密级', icon: '密' },
  { key: '备注', icon: '注' },
]
const ruleFields = ref({})
const aiFields = ref(null)
const recommendedFields = ref(null)
const fieldConflicts = ref({})
const fieldEvidence = ref({})
const fieldsLoading = ref(false)
const aiLoading = ref(false)
const fieldsError = ref('')
const editingFieldKey = ref('')
const editingFieldValue = ref('')

async function loadRuleFields() {
  if (isMergedMaterialView.value) return
  if (task.value?.status !== 'done') return
  fieldsLoading.value = true
  fieldsError.value = ''
  try {
    const { data } = await getTaskFields(props.id)
    ruleFields.value = data.fields || {}
  } catch (err) {
    fieldsError.value = err.response?.data?.detail || '字段提取失败'
  } finally {
    fieldsLoading.value = false
  }
}

async function runAiExtraction() {
  if (isMergedMaterialView.value) {
    fieldsError.value = '当前为同文件合并视图，请切换到左侧具体页后再执行字段提取。'
    return
  }
  aiLoading.value = true
  fieldsError.value = ''
  try {
    const { data } = await aiExtractFields(props.id)
    ruleFields.value = data.rule_fields || {}
    aiFields.value = data.llm_fields || {}
    recommendedFields.value = data.recommended_fields || {}
    fieldConflicts.value = data.conflicts || {}
    fieldEvidence.value = (data.llm_fields || {}).evidence || {}
    showToast('AI 智能提取完成')
  } catch (err) {
    const detail = err.response?.data?.detail || ''
    fieldsError.value = detail.includes('disabled') || detail.includes('not configured')
      ? '智能提取服务暂未启用，请联系管理员检查本地配置后重试。'
      : detail || 'AI 提取失败'
  } finally {
    aiLoading.value = false
  }
}

function fieldDisplayValue(key) {
  if (recommendedFields.value) return recommendedFields.value[key] || ''
  return ruleFields.value[key] || ''
}

function fieldHasConflict(key) {
  return !!fieldConflicts.value[key]
}

function startFieldEdit(key) {
  editingFieldKey.value = key
  editingFieldValue.value = fieldDisplayValue(key)
}

function cancelFieldEdit() {
  editingFieldKey.value = ''
  editingFieldValue.value = ''
}

function saveFieldEdit(key) {
  if (recommendedFields.value) {
    recommendedFields.value[key] = editingFieldValue.value
  } else {
    ruleFields.value[key] = editingFieldValue.value
  }
  if (fieldConflicts.value[key]) {
    delete fieldConflicts.value[key]
  }
  editingFieldKey.value = ''
  editingFieldValue.value = ''
  showToast('已保存')
}

watch(() => activeTab.value, (tab) => {
  if (tab === 'fields' && !isMergedMaterialView.value && !Object.keys(ruleFields.value).length && task.value?.status === 'done') {
    loadRuleFields()
  }
})

watch(() => props.id, () => {
  ruleFields.value = {}
  aiFields.value = null
  recommendedFields.value = null
  fieldConflicts.value = {}
  fieldEvidence.value = {}
  fieldsError.value = ''
})

function isStructuredTextRegion(type) {
  return !['table', 'seal', 'figure', 'image', 'chart'].includes(String(type || 'text'))
}

function isPlainTextDisplayType(type) {
  return ['text', 'other_text', 'paragraph', 'number'].includes(String(type || 'text'))
}

function displayRegionType(type) {
  return isPlainTextDisplayType(type) ? 'text' : String(type || 'text')
}

function regionSourceIndices(region) {
  if (Array.isArray(region?.__sourceIndices) && region.__sourceIndices.length) {
    return region.__sourceIndices.filter((value) => value !== undefined && value !== null)
  }
  if (region?.__sourceIndex !== undefined && region?.__sourceIndex !== null) {
    return [region.__sourceIndex]
  }
  return []
}

function mergeRects(leftRect, rightRect) {
  if (!Array.isArray(leftRect) || leftRect.length < 4) return Array.isArray(rightRect) ? [...rightRect] : []
  if (!Array.isArray(rightRect) || rightRect.length < 4) return [...leftRect]
  return [
    Math.min(Number(leftRect[0]) || 0, Number(rightRect[0]) || 0),
    Math.min(Number(leftRect[1]) || 0, Number(rightRect[1]) || 0),
    Math.max(Number(leftRect[2]) || 0, Number(rightRect[2]) || 0),
    Math.max(Number(leftRect[3]) || 0, Number(rightRect[3]) || 0),
  ]
}

function regionLinePayloads(region) {
  if (Array.isArray(region?.region_lines) && region.region_lines.length) {
    return region.region_lines.map((line, index) => ({
      line_num: Number(line?.line_num) || index + 1,
      text: String(line?.text || ''),
      confidence: Number(line?.confidence) || 0,
      bbox: Array.isArray(line?.bbox) ? JSON.parse(JSON.stringify(line.bbox)) : [],
      bbox_type: line?.bbox_type || (Array.isArray(line?.bbox?.[0]) ? 'poly' : 'rect'),
    }))
  }

  const rect = regionDisplayRect(region)
  const text = String(region?.content || '').trim()
  if (!text || rect.length < 4) return []
  return [
    {
      line_num: 1,
      text,
      confidence: 0,
      bbox: [...rect],
      bbox_type: 'rect',
    },
  ]
}

function mergeRegionContents(regions) {
  const lines = []
  for (const region of regions) {
    const chunks = String(region?.content || '')
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean)
    for (const chunk of chunks) {
      if (!lines.length || lines[lines.length - 1] !== chunk) {
        lines.push(chunk)
      }
    }
  }
  return lines.join('\n')
}

function shouldMergeTextRegions(previousRegion, currentRegion) {
  if (!previousRegion || !currentRegion) return false
  if (!isPlainTextDisplayType(regionDisplayType(previousRegion)) || !isPlainTextDisplayType(regionDisplayType(currentRegion))) return false

  const previousRect = regionDisplayRect(previousRegion)
  const currentRect = regionDisplayRect(currentRegion)
  if (previousRect.length < 4 || currentRect.length < 4) return false

  const previousHeight = Math.max(1, (previousRect[3] || 0) - (previousRect[1] || 0))
  const currentHeight = Math.max(1, (currentRect[3] || 0) - (currentRect[1] || 0))
  const gap = (currentRect[1] || 0) - (previousRect[3] || 0)
  if (gap < -4 || gap > Math.max(10, Math.min(previousHeight, currentHeight) * 0.6)) return false

  const previousWidth = Math.max(1, (previousRect[2] || 0) - (previousRect[0] || 0))
  const currentWidth = Math.max(1, (currentRect[2] || 0) - (currentRect[0] || 0))
  const overlapWidth = Math.max(0, Math.min(previousRect[2] || 0, currentRect[2] || 0) - Math.max(previousRect[0] || 0, currentRect[0] || 0))
  const horizontalOverlap = overlapWidth / Math.min(previousWidth, currentWidth)
  const leftDiff = Math.abs((previousRect[0] || 0) - (currentRect[0] || 0))
  if (horizontalOverlap < 0.55 && leftDiff > Math.max(previousHeight, currentHeight) * 1.2 + 8) return false

  const previousText = String(previousRegion?.content || '').trim()
  const currentText = String(currentRegion?.content || '').trim()
  if (!previousText || !currentText) return false

  const hasContinuationCue = /[，、：（(]$/.test(previousText) || /^[）).,，、：;；]/.test(currentText)
  const longLine = compactText(previousText).length >= 18 || compactText(currentText).length >= 18
  const narrowGap = gap <= Math.max(6, Math.min(previousHeight, currentHeight) * 0.35)
  const alignedBand = leftDiff <= Math.max(14, Math.min(previousHeight, currentHeight) * 1.1)

  return alignedBand && (hasContinuationCue || (longLine && narrowGap) || (horizontalOverlap >= 0.86 && narrowGap))
}

function mergeDisplayRegions(regions) {
  if (!Array.isArray(regions) || !regions.length) return []

  const merged = []
  for (const region of regions) {
    const normalized = {
      ...region,
      __renderType: renderableRegionType(region),
      __sourceIndices: regionSourceIndices(region),
    }

    const previous = merged[merged.length - 1]
    if (shouldMergeTextRegions(previous, normalized)) {
      const previousLines = regionLinePayloads(previous)
      const currentLines = regionLinePayloads(normalized)
      const nextRects = mergeRects(regionDisplayRect(previous), regionDisplayRect(normalized))
      previous.content = mergeRegionContents([previous, normalized])
      previous.layout_bbox = nextRects
      previous.bbox = nextRects
      previous.bbox_type = 'rect'
      previous.region_lines = [...previousLines, ...currentLines]
      previous.__sourceIndices = [...new Set([...regionSourceIndices(previous), ...regionSourceIndices(normalized)])]
      continue
    }

    merged.push(normalized)
  }

  return merged
}

function buildPageItems(page, pageIndex) {
  if (page?.regions?.length) {
    const indexedRegions = page.regions.map((region, index) => ({ ...region, __sourceIndex: index }))
    return mergeDisplayRegions(filterDisplayRegions(indexedRegions)).map((region, regionIndex) => {
      const { __sourceIndex, __sourceIndices, ...rawRegion } = region
      const sourceIndices = Array.isArray(__sourceIndices) && __sourceIndices.length
        ? __sourceIndices
        : (__sourceIndex !== undefined ? [__sourceIndex] : [])
      const primaryRegionIndex = sourceIndices.length === 1 ? sourceIndices[0] : undefined
      const html = resolveTableHtml(rawRegion)
      const tableData = resolveTableData(rawRegion, html)
      const displayType = renderableRegionType(rawRegion, html, tableData)
      const htmlTextPayload = displayType !== 'table'
        ? resolveHtmlTextPayload(rawRegion, {
          keyPrefix: `page-${pageIndex}-region-${sourceIndices.join('-') || regionIndex}-html`,
        })
        : null
      const regionContent = rawRegion.content || ''
      const displayLines = htmlTextPayload?.lines?.length
        ? htmlTextPayload.lines
        : (isStructuredTextRegion(displayType)
          ? buildFormattedLineItems(rawRegion.region_lines, {
            keyPrefix: `page-${pageIndex}-region-${sourceIndices.join('-') || regionIndex}-line`,
            pageIndex,
            baseRect: regionDisplayRect(rawRegion),
          })
          : [])
      const content = displayType === 'table'
        ? (hasTableContent(tableData) ? tableDataToText(tableData) : regionContent)
        : (htmlTextPayload?.plainText || regionContent)

      return {
        ...rawRegion,
        type: displayType,
        html: html || rawRegion.html || null,
        content,
        table_data: tableData,
        __sourceIndices: sourceIndices,
        _renderMode: displayLines.length ? 'region_formatted_text' : '',
        _displayLines: displayLines,
        _key: `page-${pageIndex}-region-${sourceIndices.join('-') || regionIndex}`,
        _pageIdx: pageIndex,
        _regionIdx: primaryRegionIndex,
        _editable: sourceIndices.length <= 1 && displayType === String(rawRegion.type || 'text'),
      }
    })
  }

  return buildOcrLineItems(page, pageIndex)
}

function buildPreviewItems(page, pageIndex) {
  if (!page?.regions?.length) {
    return buildOcrLineItems(page, pageIndex)
  }

  const displayItems = buildPageItems(page, pageIndex)
  const sourceRegions = (page.regions || []).map((region, index) => ({
    ...region,
    type: renderableRegionType(region),
    _pageIdx: pageIndex,
    _regionIdx: index,
    __sourceIndex: index,
  }))

  return displayItems.flatMap((item) => {
    const sourceIndices = regionSourceIndices(item)
    if (!sourceIndices.length) {
      return [{ ...item, _targetKey: item._key }]
    }

    return sourceIndices
      .map((sourceIndex, index) => {
        const sourceRegion = sourceRegions[sourceIndex]
        if (!sourceRegion) return null
        return {
          ...sourceRegion,
          _key: `${item._key}-preview-${index}`,
          _targetKey: item._key,
        }
      })
      .filter(Boolean)
  })
}

function looksLikeHtmlTable(value) {
  if (typeof value !== 'string') return false
  const lowered = value.toLowerCase()
  return lowered.includes('<table') && lowered.includes('</table>')
}

function resolveTableHtml(region) {
  if (!region) return ''
  if (looksLikeHtmlTable(region.html)) return region.html.trim()
  if (looksLikeHtmlTable(region.content)) return region.content.trim()
  const firstLineHtml = Array.isArray(region?.region_lines)
    ? region.region_lines.find((line) => looksLikeHtmlTable(line?.text))?.text
    : ''
  if (looksLikeHtmlTable(firstLineHtml)) return String(firstLineHtml).trim()
  return ''
}

function parseHtmlTableToData(html) {
  if (!looksLikeHtmlTable(html) || typeof DOMParser === 'undefined') return null
  const documentNode = new DOMParser().parseFromString(html, 'text/html')
  const rows = Array.from(documentNode.querySelectorAll('tr'))
    .map((row) => Array.from(row.querySelectorAll('th, td')).map((cell) => String(cell.textContent || '').replace(/\u00a0/g, ' ').trim()))
    .filter((row) => row.length)
  return rows.length ? rows : null
}

function hasTableContent(tableData) {
  return Array.isArray(tableData) && tableData.some((row) => Array.isArray(row) && row.some((cell) => String(cell || '').trim()))
}

const HTML_IMAGE_TAG_RE = /<img\b[^>]*>/gi
const MARKDOWN_IMAGE_RE = /!\[[^\]]*]\([^)]+\)/g

function sanitizeTableCell(cell) {
  return String(cell || '')
    .replace(HTML_IMAGE_TAG_RE, ' ')
    .replace(MARKDOWN_IMAGE_RE, ' ')
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function normalizeMergedTableRows(tableData) {
  if (!Array.isArray(tableData)) return [['']]
  return tableData.map((row) => {
    const normalizedRow = (Array.isArray(row) ? row : [row]).map((cell) => sanitizeTableCell(cell))
    const nonEmpty = normalizedRow.filter((cell) => cell)
    if (nonEmpty.length >= 3 && new Set(nonEmpty).size === 1) {
      return [nonEmpty[0], ...Array(Math.max(0, normalizedRow.length - 1)).fill('')]
    }
    return normalizedRow
  })
}

function resolveTableData(region, html = '') {
  if (Array.isArray(region?.table_data) && region.table_data.length) {
    return normalizeMergedTableRows(cloneTableData(region.table_data))
  }

  const parsed = parseHtmlTableToData(html || resolveTableHtml(region))
  if (hasTableContent(parsed)) {
    return normalizeMergedTableRows(cloneTableData(parsed))
  }

  return [['']]
}

const HTML_TEXT_TAG_RE = /<(div|p|span|strong|em|b|i|u|h[1-6]|br|section|article|header|footer)\b/i
const HTML_TEXT_END_TAG_RE = /<\/(div|p|span|strong|em|b|i|u|h[1-6]|section|article|header|footer)>|<br\s*\/?>/i
const HTML_TEXT_BLOCK_TAGS = new Set(['div', 'p', 'section', 'article', 'header', 'footer', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
const HTML_TEXT_HEADING_TAGS = new Set(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

function looksLikeHtmlText(value) {
  if (typeof value !== 'string') return false
  if (looksLikeHtmlTable(value)) return false
  return HTML_TEXT_TAG_RE.test(value) && HTML_TEXT_END_TAG_RE.test(value)
}

function normalizeHtmlTextContent(value) {
  return String(value || '')
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n[ \t]+/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function readHtmlTextAlign(element) {
  if (!element || typeof element.getAttribute !== 'function') return ''

  const direct = String(element.style?.textAlign || element.getAttribute('align') || '').trim().toLowerCase()
  if (['left', 'center', 'right', 'justify'].includes(direct)) return direct

  const styleAttr = String(element.getAttribute('style') || '')
  const matched = styleAttr.match(/text-align\s*:\s*(left|center|right|justify)/i)
  return matched?.[1]?.toLowerCase?.() || ''
}

function collectHtmlText(node) {
  if (!node) return ''
  if (node.nodeType === 3) return String(node.textContent || '')
  if (node.nodeType !== 1) return ''
  const tag = String(node.tagName || '').toLowerCase()
  if (tag === 'br') return '\n'
  return Array.from(node.childNodes || []).map((child) => collectHtmlText(child)).join('')
}

function parseHtmlTextDisplayLines(html, options = {}) {
  const { keyPrefix = 'html-text' } = options
  if (!looksLikeHtmlText(html) || typeof DOMParser === 'undefined') return []

  const documentNode = new DOMParser().parseFromString(`<div data-ocr-html-root="1">${html}</div>`, 'text/html')
  const root = documentNode.body.firstElementChild || documentNode.body
  if (!root) return []

  const blockElements = Array.from(root.children || []).filter((element) =>
    HTML_TEXT_BLOCK_TAGS.has(String(element.tagName || '').toLowerCase())
  )
  const sources = blockElements.length ? blockElements : [root]
  let lineIndex = 0

  return sources.flatMap((element) => {
    const tagName = String(element.tagName || '').toLowerCase()
    const textAlign = readHtmlTextAlign(element) || 'left'
    const normalizedText = normalizeHtmlTextContent(collectHtmlText(element))
    if (!normalizedText) return []

    const fontWeight = HTML_TEXT_HEADING_TAGS.has(tagName) || (textAlign === 'center' && compactText(normalizedText).length <= 36) ? 600 : 400
    const fontSizePx = HTML_TEXT_HEADING_TAGS.has(tagName) ? 20 : (fontWeight >= 600 ? 18 : 16)

    return normalizedText
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, index) => {
        const currentIndex = lineIndex
        lineIndex += 1
        return {
          type: 'text',
          content: line,
          bbox: [],
          bbox_type: 'rect',
          _key: `${keyPrefix}-${currentIndex}`,
          _textAlign: textAlign,
          _fontSizePx: fontSizePx,
          _fontWeight: fontWeight,
          _lineHeight: fontWeight >= 600 ? 1.7 : 1.85,
          _paddingLeftPercent: textAlign === 'center' ? 0 : 2,
          _paddingRightPercent: textAlign === 'center' ? 0 : 2,
          _marginTopPx: currentIndex === 0 && index === 0 ? 0 : 4,
        }
      })
  })
}

function resolveHtmlTextPayload(region, options = {}) {
  const sources = [
    String(region?.content || '').trim(),
    ...(Array.isArray(region?.region_lines)
      ? region.region_lines.map((line) => String(line?.text || '').trim()).filter(Boolean)
      : []),
  ]
  const htmlSource = sources.find((value) => looksLikeHtmlText(value))
  if (!htmlSource) return null

  const lines = parseHtmlTextDisplayLines(htmlSource, options)
  if (!lines.length) return null

  return {
    plainText: lines.map((line) => line.content).join('\n'),
    lines,
  }
}

function renderableRegionType(region, html = '', tableData = null) {
  const resolvedHtml = html || resolveTableHtml(region)
  const resolvedTableData = tableData || resolveTableData(region, resolvedHtml)
  if (String(region?.type || '') === 'table' || looksLikeHtmlTable(resolvedHtml) || hasTableContent(resolvedTableData)) {
    return 'table'
  }
  return displayRegionType(region?.type)
}

function regionDisplayType(region) {
  return String(region?.__renderType || renderableRegionType(region) || region?.type || 'text')
}

function compactText(value) {
  return String(value || '').replace(/\s+/g, '')
}

function textSimilarity(leftValue, rightValue) {
  const left = compactText(leftValue)
  const right = compactText(rightValue)
  if (!left || !right) return 0
  if (left === right) return 1
  if (left.includes(right) || right.includes(left)) return 0.92
  if (left.length < 2 || right.length < 2) return 0

  const pairs = new Map()
  for (let index = 0; index < left.length - 1; index += 1) {
    const pair = left.slice(index, index + 2)
    pairs.set(pair, (pairs.get(pair) || 0) + 1)
  }

  let overlap = 0
  for (let index = 0; index < right.length - 1; index += 1) {
    const pair = right.slice(index, index + 2)
    const count = pairs.get(pair) || 0
    if (count > 0) {
      overlap += 1
      pairs.set(pair, count - 1)
    }
  }

  return (2 * overlap) / ((left.length - 1) + (right.length - 1))
}

function rectArea(rect) {
  return Array.isArray(rect) && rect.length >= 4
    ? Math.max(0, (Number(rect[2]) || 0) - (Number(rect[0]) || 0)) * Math.max(0, (Number(rect[3]) || 0) - (Number(rect[1]) || 0))
    : 0
}

function intersectionArea(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length < 4 || b.length < 4) return 0
  const x1 = Math.max(Number(a[0]) || 0, Number(b[0]) || 0)
  const y1 = Math.max(Number(a[1]) || 0, Number(b[1]) || 0)
  const x2 = Math.min(Number(a[2]) || 0, Number(b[2]) || 0)
  const y2 = Math.min(Number(a[3]) || 0, Number(b[3]) || 0)
  return Math.max(0, x2 - x1) * Math.max(0, y2 - y1)
}

function overlapOnSmaller(a, b) {
  const denominator = Math.min(rectArea(a), rectArea(b))
  if (!denominator) return 0
  return intersectionArea(a, b) / denominator
}

function regionDisplayRect(region) {
  if (Array.isArray(region?.layout_bbox) && region.layout_bbox.length >= 4) {
    return region.layout_bbox.slice(0, 4).map((value) => Number(value) || 0)
  }
  return rectFromBBox(region?.bbox || [])
}

function normalizeSealDisplayContent(content) {
  const lines = String(content || '')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (!lines.length) return ''

  const joined = lines.join('\n')
  if (lines.length > 4) return ''
  if (joined.length > 48 && /[，。；、]/.test(joined)) return ''
  return joined
}

function sealDisplayText(item) {
  const direct = normalizeSealDisplayContent(item?.content)
  if (direct) return direct

  return normalizeSealDisplayContent(
    (item?.region_lines || [])
      .map((line) => String(line?.text || '').trim())
      .filter(Boolean)
      .join('\n')
  )
}

function itemBodyText(item) {
  if (item?.type === 'seal') {
    return sealDisplayText(item)
  }
  return String(item?.content || '')
}

function tableTextFromRegion(region) {
  const html = resolveTableHtml(region)
  const tableData = resolveTableData(region, html)
  if (hasTableContent(tableData)) {
    return compactText(tableDataToText(tableData))
  }
  return compactText(region?.content || html)
}

function tableRegionScore(region) {
  const html = resolveTableHtml(region)
  const tableData = resolveTableData(region, html)
  let score = 0
  if (hasTableContent(tableData)) {
    const nonEmpty = tableData.reduce((sum, row) => sum + row.filter((cell) => String(cell || '').trim()).length, 0)
    const maxCols = tableData.reduce((maxValue, row) => Math.max(maxValue, Array.isArray(row) ? row.length : 0), 0)
    score += Math.min(nonEmpty, 60) * 0.12
    score += Math.min(tableData.length, 20) * 0.08
    score += Math.min(maxCols, 12) * 0.14
  }
  if (html) score += 1.5
  score += Math.min(tableTextFromRegion(region).length, 180) / 90
  return score
}

function tableRegionsLookDuplicated(region, other) {
  const overlapRatio = overlapOnSmaller(regionDisplayRect(region), regionDisplayRect(other))
  if (overlapRatio >= 0.92) return true

  const regionText = tableTextFromRegion(region)
  const otherText = tableTextFromRegion(other)
  if (overlapRatio >= 0.72) {
    if (!regionText || !otherText) return true
    if (regionText.includes(otherText) || otherText.includes(regionText)) return true
    if (textSimilarity(regionText, otherText) >= 0.88) return true
  }

  return overlapRatio >= 0.58 && regionText && otherText && textSimilarity(regionText, otherText) >= 0.96
}

function filterDisplayRegions(regions) {
  if (!Array.isArray(regions) || !regions.length) return []

  const kept = []
  const keptTables = []

  for (const region of regions) {
    const type = String(region?.type || 'text')
    const rect = regionDisplayRect(region)
    const regionText = compactText(type === 'seal' ? normalizeSealDisplayContent(region?.content) : region?.content)

    if (type === 'table') {
      const duplicateIndex = keptTables.findIndex((table) => tableRegionsLookDuplicated(region, table.region))
      if (duplicateIndex !== -1) {
        const candidateScore = tableRegionScore(region)
        if (candidateScore > keptTables[duplicateIndex].score) {
          const keptIndex = keptTables[duplicateIndex].index
          kept[keptIndex] = region
          keptTables[duplicateIndex] = {
            region,
            rect,
            text: tableTextFromRegion(region),
            score: candidateScore,
            index: keptIndex,
          }
        }
        continue
      }

      kept.push(region)
      keptTables.push({ region, rect, text: tableTextFromRegion(region), score: tableRegionScore(region), index: kept.length - 1 })
      continue
    }

    if (['text', 'paragraph', 'number'].includes(type) && regionText) {
      const coveredByTable = keptTables.some((table) => {
        if (overlapOnSmaller(rect, table.rect) < 0.88) return false
        return !table.text || table.text.includes(regionText) || regionText.includes(table.text)
      })

      if (coveredByTable) continue
    }

    kept.push(region)
  }

  return kept
}

function rectFromBBox(bbox) {
  if (Array.isArray(bbox) && bbox.length >= 4 && !Array.isArray(bbox[0])) {
    return bbox.slice(0, 4).map((value) => Number(value) || 0)
  }
  if (Array.isArray(bbox) && bbox.length && Array.isArray(bbox[0])) {
    const xs = bbox.map((point) => Number(point?.[0]) || 0)
    const ys = bbox.map((point) => Number(point?.[1]) || 0)
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
  }
  return []
}

function buildFormattedLineItems(rawLines, options = {}) {
  const { keyPrefix = 'line', pageIndex = 0, baseRect = [] } = options
  const baseRectValue = Array.isArray(baseRect) && baseRect.length >= 4
    ? baseRect.slice(0, 4).map((value) => Number(value) || 0)
    : []

  const normalizedLines = (rawLines || []).map((line, lineIndex) => {
    const rect = rectFromBBox(line.bbox || [])
    return {
      type: 'text',
      content: line.text || '',
      bbox: line.bbox || [],
      bbox_type: line.bbox_type || (Array.isArray(line.bbox?.[0]) ? 'poly' : 'rect'),
      _key: `${keyPrefix}-${lineIndex}`,
      _pageIdx: pageIndex,
      _lineIdx: lineIndex,
      _rect: rect,
    }
  })

  const lines = [...normalizedLines].sort((a, b) => {
    const ay = a._rect[1] ?? 0
    const by = b._rect[1] ?? 0
    if (Math.abs(ay - by) > 4) return ay - by
    const ax = a._rect[0] ?? 0
    const bx = b._rect[0] ?? 0
    return ax - bx
  })

  const rects = lines.map((line) => line._rect).filter((rect) => rect.length >= 4)
  if (!rects.length) {
    return lines.map((line) => ({
      ...line,
      _renderMode: 'ocr_line',
      _paddingLeftPercent: 0,
      _paddingRightPercent: 0,
      _marginTopPx: 4,
      _textAlign: 'left',
      _fontSizePx: 16,
      _fontWeight: 400,
      _lineHeight: 1.8,
    }))
  }

  const pageLeft = baseRectValue.length ? baseRectValue[0] : Math.min(...rects.map((rect) => rect[0]))
  const pageTop = baseRectValue.length ? baseRectValue[1] : Math.min(...rects.map((rect) => rect[1]))
  const pageRight = baseRectValue.length ? Math.max(baseRectValue[2], ...rects.map((rect) => rect[2])) : Math.max(...rects.map((rect) => rect[2]))
  const pageWidth = Math.max(1, pageRight - pageLeft)
  const avgHeight = rects.reduce((sum, rect) => sum + Math.max(1, rect[3] - rect[1]), 0) / rects.length

  let prevBottom = baseRectValue.length ? baseRectValue[1] : pageTop
  return lines.map((line, index) => {
    const rect = line._rect
    if (rect.length < 4) {
      return {
        ...line,
        _renderMode: 'ocr_line',
        _paddingLeftPercent: 0,
        _paddingRightPercent: 0,
        _marginTopPx: index === 0 ? 0 : 6,
        _textAlign: 'left',
        _fontSizePx: 16,
        _fontWeight: 400,
        _lineHeight: 1.8,
      }
    }

    const [x1, y1, x2, y2] = rect
    const width = Math.max(1, x2 - x1)
    const height = Math.max(1, y2 - y1)
    const leftRatio = Math.max(0, (x1 - pageLeft) / pageWidth)
    const rightRatio = Math.max(0, (pageRight - x2) / pageWidth)
    const widthRatio = width / pageWidth
    const centerRatio = ((x1 + x2) / 2 - pageLeft) / pageWidth
    const centered = Math.abs(centerRatio - 0.5) < 0.1 && widthRatio < 0.72 && leftRatio > 0.12 && rightRatio > 0.12
    const titleLike = centered || height > avgHeight * 1.18
    const gap = index === 0 ? 0 : Math.max(0, y1 - prevBottom)
    prevBottom = y2

    return {
      ...line,
      _renderMode: 'ocr_line',
      _paddingLeftPercent: centered ? 0 : Math.min(18, leftRatio * 36),
      _paddingRightPercent: centered ? 0 : Math.min(12, rightRatio * 18),
      _marginTopPx: index === 0 ? 0 : Math.min(26, gap * 0.5 + (gap > avgHeight * 0.9 ? 6 : 2)),
      _textAlign: centered ? 'center' : 'left',
      _fontSizePx: Math.max(15, Math.min(titleLike ? 24 : 18, height * (titleLike ? 1.1 : 0.95))),
      _fontWeight: titleLike ? 600 : 400,
      _lineHeight: titleLike ? 1.7 : 1.85,
    }
  })
}

function buildOcrLineItems(page, pageIndex) {
  return buildFormattedLineItems(page?.lines || [], {
    keyPrefix: `page-${pageIndex}-line`,
    pageIndex,
  })
}

function labelName(type) {
  return {
    title: '标题',
    doc_title: '文档标题',
    paragraph_title: '段落标题',
    table: '表格',
    seal: '印章',
    figure: '图片',
    image: '图片',
    chart: '图表',
    text: '文本',
    other_text: '文本',
    paragraph: '文本',
    number: '文本',
    header: '页眉',
    footer: '页脚',
  }[type] || type
}

function labelClass(type) {
  if (type === 'table') return 'bg-orange-100 text-orange-700'
  if (type === 'seal') return 'bg-red-100 text-red-700'
  if (['title', 'doc_title', 'paragraph_title'].includes(type)) return 'bg-blue-600 text-white'
  if (['figure', 'image', 'chart'].includes(type)) return 'bg-pink-100 text-pink-700'
  return 'bg-gray-100 text-gray-600'
}

function showRegionHeader(item) {
  if (!isPlainTextDisplayType(item?.type)) return true
  return activeKey.value === item._key || editingKey.value === item._key || editingTableKey.value === item._key
}

function overlayTargetKey(item) {
  return item?._targetKey || item?._key
}

function regionPalette(type) {
  if (type === 'seal') {
    return {
      fill: 'rgba(239,68,68,0.08)',
      activeFill: 'rgba(239,68,68,0.16)',
      stroke: 'rgba(220,38,38,0.55)',
      activeStroke: '#dc2626',
    }
  }
  if (['figure', 'image', 'chart'].includes(type)) {
    return {
      fill: 'rgba(236,72,153,0.07)',
      activeFill: 'rgba(236,72,153,0.14)',
      stroke: 'rgba(219,39,119,0.45)',
      activeStroke: '#db2777',
    }
  }
  if (['title', 'doc_title', 'paragraph_title'].includes(type)) {
    return {
      fill: 'rgba(59,130,246,0.07)',
      activeFill: 'rgba(59,130,246,0.15)',
      stroke: 'rgba(37,99,235,0.42)',
      activeStroke: '#2563eb',
    }
  }
  return {
    fill: 'rgba(148,163,184,0.04)',
    activeFill: 'rgba(59,130,246,0.12)',
    stroke: 'rgba(100,116,139,0.28)',
    activeStroke: '#2563eb',
  }
}

function regionFill(item) {
  const palette = regionPalette(item.type)
  return activeKey.value === overlayTargetKey(item) ? palette.activeFill : palette.fill
}

function regionStroke(item) {
  const palette = regionPalette(item.type)
  return activeKey.value === overlayTargetKey(item) ? palette.activeStroke : palette.stroke
}

function regionStrokeWidth(item) {
  return activeKey.value === overlayTargetKey(item) ? 2.5 : 1.2
}

function ocrLineContainerStyle(item) {
  return {
    marginTop: `${item._marginTopPx || 0}px`,
    paddingLeft: `${item._paddingLeftPercent || 0}%`,
    paddingRight: `${item._paddingRightPercent || 0}%`,
  }
}

function ocrLineTextStyle(item) {
  return {
    textAlign: item._textAlign || 'left',
    fontSize: `${item._fontSizePx || 16}px`,
    fontWeight: item._fontWeight || 400,
    lineHeight: item._lineHeight || 1.8,
    letterSpacing: item._fontWeight >= 600 ? '0.01em' : '0',
  }
}

function regionRect(item) {
  if (Array.isArray(item?.layout_bbox) && item.layout_bbox.length >= 4) {
    return item.layout_bbox.slice(0, 4).map((value) => Number(value) || 0)
  }
  if (Array.isArray(item?.bbox) && item.bbox.length >= 4 && !Array.isArray(item.bbox[0])) {
    return item.bbox.slice(0, 4).map((value) => Number(value) || 0)
  }
  if (Array.isArray(item?.bbox) && item.bbox.length && Array.isArray(item.bbox[0])) {
    const xs = item.bbox.map((point) => Number(point?.[0]) || 0)
    const ys = item.bbox.map((point) => Number(point?.[1]) || 0)
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)]
  }
  return []
}

function showRegionPreview(item) {
  return ['seal', 'figure', 'image', 'chart'].includes(item.type) && regionRect(item).length >= 4 && natW.value && natH.value
}

function cropPreviewMetrics(item) {
  const rect = regionRect(item)
  if (rect.length < 4 || !natW.value || !natH.value) return null

  let [x1, y1, x2, y2] = rect
  x1 = Math.max(0, Math.min(natW.value, x1))
  y1 = Math.max(0, Math.min(natH.value, y1))
  x2 = Math.max(x1 + 1, Math.min(natW.value, x2))
  y2 = Math.max(y1 + 1, Math.min(natH.value, y2))

  const width = Math.max(1, x2 - x1)
  const height = Math.max(1, y2 - y1)
  const maxWidth = 360
  const maxHeight = 220
  const minWidth = 180
  const minHeight = 100
  const scale = Math.min(maxWidth / width, maxHeight / height)
  const safeScale = Number.isFinite(scale) && scale > 0 ? scale : 1
  const frameWidth = Math.max(minWidth, Math.min(maxWidth, width * safeScale))
  const frameHeight = Math.max(minHeight, Math.min(maxHeight, height * safeScale))

  return {
    x1,
    y1,
    scale: safeScale,
    frameWidth,
    frameHeight,
  }
}

function cropFrameStyle(item) {
  const metrics = cropPreviewMetrics(item)
  if (!metrics) return {}
  return {
    width: `${metrics.frameWidth}px`,
    height: `${metrics.frameHeight}px`,
  }
}

function cropImageStyle(item) {
  const metrics = cropPreviewMetrics(item)
  if (!metrics) return {}
  return {
    width: `${natW.value * metrics.scale}px`,
    height: `${natH.value * metrics.scale}px`,
    transform: `translate(${-metrics.x1 * metrics.scale}px, ${-metrics.y1 * metrics.scale}px)`,
    transformOrigin: 'top left',
  }
}

function onImgLoad() {
  const image = previewImg.value
  if (!image) return
  natW.value = image.naturalWidth
  natH.value = image.naturalHeight
  imgW.value = image.clientWidth
  imgH.value = image.clientHeight
}

function selectItem(item) {
  const targetKey = overlayTargetKey(item)
  if (item._pageIdx !== undefined && item._pageIdx + 1 !== pageNum.value) {
    pendingActiveKey.value = targetKey
    pageNum.value = item._pageIdx + 1
    return
  }
  pendingActiveKey.value = ''
  activeKey.value = targetKey
}

watch(activeKey, async (key) => {
  await nextTick()
  regionRefs.value[key]?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' })
})

watch(previewImageUrl, () => {
  imgW.value = 0
  imgH.value = 0
  natW.value = 0
  natH.value = 0
  pdfImgFailed.value = false
})

watch(pageNum, async () => {
  await nextTick()
  if (isMergedMaterialView.value) {
    mergedPreviewPageRefs.value[pageNum.value]?.scrollIntoView?.({
      behavior: 'smooth',
      block: 'nearest',
    })
  }
  if (pendingActiveKey.value) {
    activeKey.value = pendingActiveKey.value
    pendingActiveKey.value = ''
    return
  }
  activeKey.value = ''
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.table-html-preview :deep(table) {
  width: 100%;
  min-width: 640px;
  border-collapse: collapse;
  font-size: 13px;
  color: rgb(55 65 81);
}

.table-html-preview :deep(th),
.table-html-preview :deep(td) {
  border: 1px solid rgb(229 231 235);
  padding: 8px 10px;
  vertical-align: top;
  white-space: pre-wrap;
}

.table-html-preview :deep(th) {
  background: rgb(248 250 252);
  font-weight: 600;
}
</style>
