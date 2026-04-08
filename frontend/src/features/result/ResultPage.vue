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
        <span class="rounded px-1.5 py-0.5 text-xs font-medium" :class="modeClass">{{ modeLabel }}</span>
        <span class="rounded px-1.5 py-0.5 text-xs font-medium" :class="statusClass(task?.status)">
          {{ statusLabel(task?.status) }}
        </span>
      </div>
      <div class="flex items-center space-x-2 text-xs text-gray-500">
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
      <aside v-if="folderPath" class="flex w-72 flex-shrink-0 flex-col border-r border-gray-200 bg-slate-50">
        <div class="border-b border-gray-200 bg-white px-4 py-3">
          <p class="truncate text-sm font-semibold text-slate-800">{{ folderLabel }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ folderTasks.length }} 份同目录材料</p>
        </div>
        <div v-if="folderLoading" class="flex flex-1 items-center justify-center text-xs text-slate-500">
          目录加载中...
        </div>
        <div v-else-if="!folderTasks.length" class="flex flex-1 items-center justify-center px-4 text-center text-xs leading-6 text-slate-400">
          当前目录暂无可展示材料
        </div>
        <div v-else class="flex-1 space-y-2 overflow-y-auto p-2">
          <button
            v-for="folderTask in folderTasks"
            :key="folderTask.id"
            class="flex w-full items-start gap-3 rounded-xl border px-3 py-3 text-left transition"
            :class="String(folderTask.id) === String(props.id) ? 'border-blue-200 bg-blue-50 shadow-sm' : 'border-transparent bg-white hover:border-slate-200 hover:bg-slate-50'"
            @click="switchTask(folderTask.id)"
          >
            <img :src="getTaskThumbnailUrl(folderTask.id)" class="h-14 w-11 flex-shrink-0 rounded border border-slate-200 bg-white object-cover" />
            <div class="min-w-0 flex-1">
              <div class="line-clamp-2 text-xs font-medium text-slate-700">{{ folderTask.filename }}</div>
              <div class="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                <span class="rounded px-1.5 py-0.5" :class="statusClass(folderTask.status)">
                  {{ statusLabel(folderTask.status) }}
                </span>
                <span>{{ formatTime(folderTask.updated_at || folderTask.created_at) }}</span>
              </div>
            </div>
          </button>
        </div>
      </aside>

      <section class="flex w-[42%] flex-shrink-0 flex-col border-r border-gray-200 bg-white">
        <div class="border-b border-gray-100 px-3 py-2 text-xs font-medium text-gray-500">原始文件预览</div>
        <div class="preview-container relative flex flex-1 items-start justify-center overflow-auto bg-gray-50 p-3">
          <iframe v-if="isPdf && pdfImgFailed" :src="fileUrl" class="h-full w-full rounded border-0" />
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

        <div v-if="totalPages > 1" class="flex items-center justify-center space-x-3 border-t border-gray-100 bg-white px-3 py-2">
          <button class="flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30" :disabled="pageNum <= 1" @click="pageNum -= 1">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7" /></svg>
          </button>
          <div class="text-xs text-gray-500">第 {{ pageNum }} / {{ totalPages }} 页</div>
          <button class="flex h-7 w-7 items-center justify-center rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30" :disabled="pageNum >= totalPages" @click="pageNum += 1">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" /></svg>
          </button>
        </div>
      </section>

      <section class="flex min-w-0 flex-1 flex-col bg-white">
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
          </div>
          <div class="flex items-center space-x-1">
            <button class="rounded p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600" title="复制全文" @click="copyAll">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
            </button>
            <button class="rounded p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600" title="下载文本" @click="downloadTxt">
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
                      v-if="task?.status === 'done' && item.type !== 'table' && item.type !== 'seal' && item._editable !== false"
                      class="rounded px-2 py-0.5 text-xs text-gray-500 transition hover:bg-white hover:text-blue-600"
                      @click.stop="startTextEdit(item)"
                    >
                      编辑
                    </button>
                    <button
                      v-if="task?.status === 'done' && item.type === 'table'"
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
              :class="aiLoading ? 'bg-indigo-50 text-indigo-400' : 'bg-indigo-600 text-white hover:bg-indigo-700'"
              :disabled="aiLoading || task?.status !== 'done'"
              @click="runAiExtraction"
            >
              <svg v-if="aiLoading" class="h-3.5 w-3.5 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
              <svg v-else class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
              {{ aiLoading ? '提取中…' : 'AI 智能提取' }}
            </button>
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
                        v-if="editingFieldKey !== field.key && task?.status === 'done'"
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

import { aiExtractFields, getTaskFields, getTaskPageImageUrl, getTaskThumbnailUrl } from '@/api/ocr.js'
import EditableTable from '@/components/EditableTable.vue'
import { useResultViewState } from '@/composables/useResultViewState.js'

const props = defineProps({
  id: {
    type: [String, Number],
    required: true,
  },
})

const router = useRouter()
const route = useRoute()

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/')
  }
}

const taskIdRef = computed(() => props.id)
const {
  task,
  resultData,
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
  fileUrl,
  folderPath,
  folderLabel,
  pages,
  totalPages,
  isPdf,
  jsonText,
  modeLabel,
  modeClass,
  currentPage,
  polling,
  formatTime,
  showToast,
  statusLabel,
  statusClass,
  switchTask,
  copyRegion,
  copyAll,
  downloadTxt,
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

const pendingActiveKey = ref('')
const pdfImgFailed = ref(false)
const previewImageUrl = computed(() => (isPdf.value ? getTaskPageImageUrl(props.id, pageNum.value) : fileUrl.value))

function onImgError() {
  if (isPdf.value) pdfImgFailed.value = true
}


const currentPreviewItems = computed(() => buildPreviewItems(currentPage.value, pageNum.value - 1))
const allItems = computed(() =>
  pages.value.flatMap((page, pageIndex) => {
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
  if (tab === 'fields' && !Object.keys(ruleFields.value).length && task.value?.status === 'done') {
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
  if (!isPlainTextDisplayType(previousRegion.type) || !isPlainTextDisplayType(currentRegion.type)) return false

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
      type: displayRegionType(region?.type),
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
      const tableData = rawRegion.type === 'table' ? resolveTableData(rawRegion, html) : (Array.isArray(rawRegion.table_data) ? rawRegion.table_data : [['']])
      const regionContent = rawRegion.content || ''
      const displayLines = isStructuredTextRegion(rawRegion.type)
        ? buildFormattedLineItems(rawRegion.region_lines, {
          keyPrefix: `page-${pageIndex}-region-${sourceIndices.join('-') || regionIndex}-line`,
          pageIndex,
          baseRect: regionDisplayRect(rawRegion),
        })
        : []
      const content = rawRegion.type === 'table'
        ? (hasTableContent(tableData) ? tableDataToText(tableData) : regionContent)
        : regionContent

      return {
        ...rawRegion,
        html: html || rawRegion.html || null,
        content,
        table_data: tableData,
        __sourceIndices: sourceIndices,
        _renderMode: displayLines.length ? 'region_formatted_text' : '',
        _displayLines: displayLines,
        _key: `page-${pageIndex}-region-${sourceIndices.join('-') || regionIndex}`,
        _pageIdx: pageIndex,
        _regionIdx: primaryRegionIndex,
        _editable: sourceIndices.length <= 1,
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
    type: displayRegionType(region?.type),
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
  if (!region || region.type !== 'table') return ''
  if (looksLikeHtmlTable(region.html)) return region.html.trim()
  if (looksLikeHtmlTable(region.content)) return region.content.trim()
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
