package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.archive.service.ArchiveRecordService;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.domain.OcrTaskStatus;
import com.ocrweb.controlplane.task.domain.TaskCallbackEventEntity;
import com.ocrweb.controlplane.task.dto.TaskDtos;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import com.ocrweb.controlplane.task.repository.TaskCallbackEventRepository;
import com.ocrweb.controlplane.trace.RequestTraceContext;
import jakarta.transaction.Transactional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

import static org.springframework.http.HttpStatus.BAD_REQUEST;

@Service
public class OcrTaskService {
    private static final Logger logger = LoggerFactory.getLogger(OcrTaskService.class);
    private static final String DEFAULT_SUBMITTER_USERNAME = "匿名用户";
    private static final String SUBMISSION_BATCH_PREFIX = "batch:";
    private static final String SINGLE_TASK_PREFIX = "single:";
    private static final ZoneId SUBMISSION_ZONE_ID = ZoneId.of("Asia/Shanghai");
    private static final DateTimeFormatter SUBMISSION_DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMdd");
    private final OcrTaskRepository taskRepository;
    private final TaskCallbackEventRepository callbackEventRepository;
    private final TaskStorageService storageService;
    private final TaskCommandProducer taskCommandProducer;
    private final ArchiveRecordService archiveRecordService;
    private final ObjectMapper objectMapper;

    public OcrTaskService(
            OcrTaskRepository taskRepository,
            TaskCallbackEventRepository callbackEventRepository,
            TaskStorageService storageService,
            TaskCommandProducer taskCommandProducer,
            ArchiveRecordService archiveRecordService,
            ObjectMapper objectMapper
    ) {
        this.taskRepository = taskRepository;
        this.callbackEventRepository = callbackEventRepository;
        this.storageService = storageService;
        this.taskCommandProducer = taskCommandProducer;
        this.archiveRecordService = archiveRecordService;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public OcrTaskEntity submitUpload(
            MultipartFile file,
            String relativePath,
            String mode,
            String batchId,
            String submitterUsername
    ) throws IOException {
        String resolvedBatchId = resolveBatchId(batchId);
        SubmissionMetadata submissionMetadata = resolveSubmissionMetadata(resolvedBatchId, submitterUsername);
        logger.info(
                "Submitting uploaded OCR task: filename={}, relativePath={}, mode={}, batchId={}, submitterUsername={}",
                file.getOriginalFilename(),
                relativePath,
                mode,
                resolvedBatchId,
                submissionMetadata.submitterUsername()
        );
        TaskStorageService.StoredFileHandle storedFile = storageService.saveUpload(file, relativePath);
        OcrTaskEntity task = new OcrTaskEntity();
        task.setFilename(file.getOriginalFilename());
        task.setFilePath(storedFile.logicalPath());
        task.setFileType(extension(file.getOriginalFilename()));
        task.setStorageProvider(storedFile.storageProvider());
        task.setStorageBucket(storedFile.bucket());
        task.setStorageObjectKey(storedFile.objectKey());
        task.setFileSha256(storedFile.sha256());
        task.setFileSizeBytes(storedFile.sizeBytes());
        task.setMode(mode);
        task.setBatchId(resolvedBatchId);
        task.setSubmitterUsername(submissionMetadata.submitterUsername());
        task.setSubmissionName(submissionMetadata.submissionName());
        task.setTraceId(RequestTraceContext.getTraceId());
        task.setStatus(normalizeStatus(OcrTaskStatus.QUEUED));
        OcrTaskEntity saved = taskRepository.save(task);
        taskCommandProducer.publish(saved);
        logger.info(
                "OCR task queued: taskId={}, filename={}, mode={}, batchId={}, traceId={}, submissionName={}",
                saved.getId(),
                saved.getFilename(),
                saved.getMode(),
                saved.getBatchId(),
                saved.getTraceId(),
                saved.getSubmissionName()
        );
        return saved;
    }

    @Transactional
    public OcrTaskEntity submitExistingPath(
            String filePath,
            String mode,
            String batchId,
            String submitterUsername
    ) throws IOException {
        String resolvedBatchId = resolveBatchId(batchId);
        SubmissionMetadata submissionMetadata = resolveSubmissionMetadata(resolvedBatchId, submitterUsername);
        logger.info(
                "Submitting existing-path OCR task: filePath={}, mode={}, batchId={}, submitterUsername={}",
                filePath,
                mode,
                resolvedBatchId,
                submissionMetadata.submitterUsername()
        );
        TaskStorageService.StoredFileHandle storedFile = storageService.saveExistingPath(filePath);
        OcrTaskEntity task = new OcrTaskEntity();
        task.setFilename(Path.of(filePath).getFileName().toString());
        task.setFilePath(storedFile.logicalPath());
        task.setFileType(extension(task.getFilename()));
        task.setStorageProvider(storedFile.storageProvider());
        task.setStorageBucket(storedFile.bucket());
        task.setStorageObjectKey(storedFile.objectKey());
        task.setFileSha256(storedFile.sha256());
        task.setFileSizeBytes(storedFile.sizeBytes());
        task.setMode(mode);
        task.setBatchId(resolvedBatchId);
        task.setSubmitterUsername(submissionMetadata.submitterUsername());
        task.setSubmissionName(submissionMetadata.submissionName());
        task.setTraceId(RequestTraceContext.getTraceId());
        task.setStatus(normalizeStatus(OcrTaskStatus.QUEUED));
        OcrTaskEntity saved = taskRepository.save(task);
        taskCommandProducer.publish(saved);
        logger.info(
                "OCR task queued from existing path: taskId={}, filename={}, mode={}, batchId={}, traceId={}, submissionName={}",
                saved.getId(),
                saved.getFilename(),
                saved.getMode(),
                saved.getBatchId(),
                saved.getTraceId(),
                saved.getSubmissionName()
        );
        return saved;
    }

    public TaskDtos.TaskListResponse listTasks(int page, int pageSize, String folder, String submissionId, String batchId) {
        String safeSubmissionId = safe(submissionId);
        if (StringUtils.hasText(safeSubmissionId)) {
            List<OcrTaskEntity> tasks = findTasksBySubmissionId(safeSubmissionId);
            return paginateTasks(tasks, page, pageSize);
        }

        var tasks = taskRepository.findByFolderAndBatchId(
                safe(folder),
                safe(batchId),
                PageRequest.of(Math.max(0, page - 1), pageSize)
        );
        return new TaskDtos.TaskListResponse(tasks.getTotalElements(), tasks.getContent().stream().map(this::toSummary).toList());
    }

    public TaskDtos.TaskListResponse searchTasks(String keyword, int page, int pageSize) {
        var tasks = taskRepository.search(keyword == null ? "" : keyword, PageRequest.of(Math.max(0, page - 1), pageSize));
        String safeKeyword = keyword == null ? "" : keyword.trim();
        return new TaskDtos.TaskListResponse(
                tasks.getTotalElements(),
                tasks.getContent().stream().map(task -> toSummary(task, buildSearchSnippet(task, safeKeyword))).toList()
        );
    }

    public List<TaskDtos.FolderSummaryResponse> listFolders() {
        return taskRepository.findAll().stream()
                .filter(task -> task.getFilePath() != null)
                .collect(Collectors.groupingBy(task -> folderFromFilePath(task.getFilePath())))
                .entrySet()
                .stream()
                .map(entry -> {
                    OcrTaskEntity latest = entry.getValue().stream().max(Comparator.comparing(OcrTaskEntity::getUpdatedAt)).orElse(null);
                    return new TaskDtos.FolderSummaryResponse(
                            entry.getKey(),
                            entry.getValue().size(),
                            latest == null ? null : latest.getUpdatedAt(),
                            latest == null ? null : latest.getId()
                    );
                })
                .sorted(Comparator.comparing(TaskDtos.FolderSummaryResponse::lastTime, Comparator.nullsLast(Comparator.reverseOrder())))
                .toList();
    }

    public List<TaskDtos.SubmissionSummaryResponse> listSubmissions() {
        Map<String, SubmissionAccumulator> submissions = new LinkedHashMap<>();
        for (OcrTaskEntity task : taskRepository.findAll()) {
            if (task.getId() == null) {
                continue;
            }
            String submissionId = submissionIdOf(task);
            submissions.computeIfAbsent(submissionId, key -> new SubmissionAccumulator(submissionId)).accept(task);
        }
        return submissions.values().stream()
                .map(SubmissionAccumulator::toResponse)
                .sorted(Comparator.comparing(TaskDtos.SubmissionSummaryResponse::lastTime, Comparator.nullsLast(Comparator.reverseOrder())))
                .toList();
    }

    public TaskDtos.TaskDetailResponse getTask(Long taskId) {
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        return toDetail(task);
    }

    public TaskDtos.WorkflowEventsResponse getWorkflowEvents(Long taskId) {
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        List<TaskDtos.WorkflowEventResponse> events = callbackEventRepository
                .findByTaskIdOrderByCreatedAtAscIdAsc(taskId)
                .stream()
                .map(this::toWorkflowEvent)
                .toList();
        String workflowThreadId = safe(task.getWorkflowThreadId());
        if (!StringUtils.hasText(workflowThreadId)) {
            workflowThreadId = events.stream()
                    .map(TaskDtos.WorkflowEventResponse::payload)
                    .map(this::extractWorkflowThreadId)
                    .filter(StringUtils::hasText)
                    .findFirst()
                    .orElse("");
        }
        return new TaskDtos.WorkflowEventsResponse(
                task.getId(),
                workflowThreadId,
                effectiveStatus(task),
                task.getMode(),
                task.getFilename(),
                events
        );
    }

    public TaskStorageService.StoredFileResource getTaskFileResource(Long taskId) throws IOException {
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        return storageService.loadTaskResource(task);
    }

    @Transactional
    public TaskDtos.TaskDetailResponse updateTask(Long taskId, TaskDtos.TaskUpdateRequest request) {
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        if (request.resultJson() != null) {
            JsonNode normalizedResultJson = normalizeResultJson(request.resultJson());
            task.setResultJson(normalizedResultJson);
            task.setPageCount(normalizedResultJson.isArray() ? normalizedResultJson.size() : task.getPageCount());
        }
        if (request.fullText() != null) {
            task.setFullText(request.fullText());
        } else if (request.resultJson() != null) {
            task.setFullText(normalizeResultJson(request.resultJson()).toString());
        }
        taskRepository.save(task);
        return toDetail(task);
    }

    @Transactional
    public boolean deleteTask(Long taskId) {
        if (!taskRepository.existsById(taskId)) {
            return false;
        }
        archiveRecordService.deleteRecordsByTaskId(taskId);
        taskRepository.deleteById(taskId);
        return true;
    }

    @Transactional
    public long deleteTasksByFolder(String folder) {
        return taskRepository.deleteByFilePathStartingWith(folder);
    }

    @Transactional
    public long deleteTasksBySubmission(String submissionId) {
        String safeSubmissionId = safe(submissionId);
        if (!StringUtils.hasText(safeSubmissionId)) {
            return 0;
        }
        if (safeSubmissionId.startsWith(SUBMISSION_BATCH_PREFIX)) {
            String batchId = safeSubmissionId.substring(SUBMISSION_BATCH_PREFIX.length());
            if (!StringUtils.hasText(batchId)) {
                return 0;
            }
            archiveRecordService.deleteRecords("", batchId);
            return taskRepository.deleteByBatchId(batchId);
        }
        if (safeSubmissionId.startsWith(SINGLE_TASK_PREFIX)) {
            Long taskId = parseLongSilently(safeSubmissionId.substring(SINGLE_TASK_PREFIX.length()));
            if (taskId == null || !taskRepository.existsById(taskId)) {
                return 0;
            }
            archiveRecordService.deleteRecordsByTaskId(taskId);
            taskRepository.deleteById(taskId);
            return 1;
        }
        return 0;
    }

    public TaskDtos.TaskProgressResponse getProgress(List<Long> taskIds) {
        List<TaskDtos.TaskProgressItem> items = new ArrayList<>();
        int done = 0;
        int failed = 0;
        int processing = 0;
        int pending = 0;
        for (Long taskId : taskIds) {
            OcrTaskEntity task = taskRepository.findById(taskId).orElse(null);
            String status = task == null ? normalizeStatus(OcrTaskStatus.FAILED) : effectiveStatus(task);
            String errorMessage = task == null ? "Task not found." : task.getErrorMessage();
            switch (status) {
                case "done" -> done++;
                case "failed" -> failed++;
                case "human_review" -> failed++;
                case "queued", "pending" -> pending++;
                default -> processing++;
            }
            items.add(new TaskDtos.TaskProgressItem(taskId, status, errorMessage));
        }
        return new TaskDtos.TaskProgressResponse(taskIds.size(), done, failed, processing, pending, items);
    }

    @Transactional
    public TaskDtos.InternalCallbackResponse handleEvent(Long taskId, TaskDtos.TaskEventRequest request) {
        if (callbackEventRepository.existsByEventId(request.eventId())) {
            return accepted(taskId, "DUPLICATE_EVENT");
        }
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        saveCallbackEvent(taskId, request.eventId(), request.eventType(), objectMapper.valueToTree(request));
        if ("WORKER_ACCEPTED".equals(request.eventType())) {
            task.setStatus(normalizeStatus(OcrTaskStatus.WORKER_ACCEPTED));
        } else if ("HUMAN_REVIEW_REQUIRED".equals(request.eventType())) {
            task.setStatus(normalizeStatus(OcrTaskStatus.HUMAN_REVIEW));
        } else {
            task.setStatus(normalizeStatus(OcrTaskStatus.RUNNING));
        }
        if (task.getTraceId() == null || task.getTraceId().isBlank()) {
            task.setTraceId(request.traceId());
        }
        updateWorkflowThreadId(task, request.payload());
        if (request.progress() != null) {
            task.setProcessedPages(request.progress().currentPage());
            task.setTotalPages(request.progress().totalPages());
            task.setProgressPercent(request.progress().percent());
        }
        taskRepository.save(task);
        return accepted(taskId, task.getStatus());
    }

    @Transactional
    public TaskDtos.InternalCallbackResponse handleCompletion(Long taskId, TaskDtos.TaskCompletionRequest request) {
        if (callbackEventRepository.existsByEventId(request.eventId())) {
            return accepted(taskId, "DUPLICATE_COMPLETION");
        }
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        saveCallbackEvent(taskId, request.eventId(), "COMPLETION", objectMapper.valueToTree(request));
        task.setStatus(normalizeStatus(OcrTaskStatus.COMPLETED));
        JsonNode normalizedResultJson = normalizeResultJson(request.result());
        task.setResultJson(normalizedResultJson);
        task.setAgentMeta(request.agentMeta());
        if (task.getTraceId() == null || task.getTraceId().isBlank()) {
            task.setTraceId(request.traceId());
        }
        task.setFullText(request.fullText() == null || request.fullText().isBlank()
                ? (normalizedResultJson.isEmpty() ? null : normalizedResultJson.toString())
                : request.fullText());
        task.setErrorMessage(null);
        task.setPageCount(request.summary() != null && request.summary().has("total_pages") ? request.summary().get("total_pages").asInt() : normalizedResultJson.size());
        task.setProgressPercent(100.0);
        task.setProcessedPages(task.getPageCount());
        task.setTotalPages(task.getPageCount());
        task.setHumanReviewPayload(null);
        task.setReviewStatus(request.agentMeta() != null && request.agentMeta().has("review_status") ? request.agentMeta().get("review_status").asText() : null);
        task.setReviewReason(request.agentMeta() != null && request.agentMeta().has("review_reason") ? request.agentMeta().get("review_reason").asText() : null);
        if (request.agentMeta() != null && request.agentMeta().has("workflow_thread_id")) {
            task.setWorkflowThreadId(request.agentMeta().get("workflow_thread_id").asText());
        }
        taskRepository.save(task);
        archiveRecordService.saveArchiveRecordFromTaskCompletion(
                task.getId(),
                task.getBatchId() == null ? request.batchId() : task.getBatchId(),
                folderFromFilePath(task.getFilePath()),
                request.archiveFields()
        );
        return accepted(taskId, task.getStatus());
    }

    @Transactional
    public TaskDtos.InternalCallbackResponse handleFailure(Long taskId, TaskDtos.TaskFailureRequest request) {
        if (callbackEventRepository.existsByEventId(request.eventId())) {
            return accepted(taskId, "DUPLICATE_FAILURE");
        }
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        saveCallbackEvent(taskId, request.eventId(), "FAILURE", objectMapper.valueToTree(request));
        task.setStatus(normalizeStatus(OcrTaskStatus.FAILED));
        if (task.getTraceId() == null || task.getTraceId().isBlank()) {
            task.setTraceId(request.traceId());
        }
        task.setErrorMessage(request.error() == null ? "Compute worker failed." : request.error().toString());
        if (request.progress() != null) {
            task.setProcessedPages(request.progress().currentPage());
            task.setTotalPages(request.progress().totalPages());
            task.setProgressPercent(request.progress().percent());
        }
        taskRepository.save(task);
        return accepted(taskId, task.getStatus());
    }

    @Transactional
    public TaskDtos.InternalCallbackResponse handlePause(Long taskId, TaskDtos.TaskPauseRequest request) {
        if (callbackEventRepository.existsByEventId(request.eventId())) {
            return accepted(taskId, "DUPLICATE_PAUSE");
        }
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        saveCallbackEvent(taskId, request.eventId(), "PAUSE", objectMapper.valueToTree(request));
        task.setStatus(normalizeStatus(OcrTaskStatus.HUMAN_REVIEW));
        if (task.getTraceId() == null || task.getTraceId().isBlank()) {
            task.setTraceId(request.traceId());
        }
        task.setWorkflowThreadId(request.workflowThreadId());
        task.setHumanReviewPayload(request.interruptPayload());
        task.setAgentMeta(request.agentMeta());
        JsonNode normalizedResultJson = normalizeResultJson(request.result());
        task.setResultJson(normalizedResultJson);
        task.setFullText(request.fullText() == null || request.fullText().isBlank()
                ? (normalizedResultJson.isEmpty() ? null : normalizedResultJson.toString())
                : request.fullText());
        task.setReviewStatus(request.reviewStatus() == null || request.reviewStatus().isBlank()
                ? "pending_human_review"
                : request.reviewStatus());
        task.setReviewReason(request.reviewReason());
        if (request.progress() != null) {
            task.setProcessedPages(request.progress().currentPage());
            task.setTotalPages(request.progress().totalPages());
            task.setProgressPercent(request.progress().percent());
        }
        if (request.summary() != null) {
            if (request.summary().has("total_pages")) {
                task.setPageCount(request.summary().path("total_pages").asInt(task.getPageCount() == null ? 0 : task.getPageCount()));
            } else if (request.summary().has("processed_pages")) {
                task.setPageCount(request.summary().path("processed_pages").asInt(task.getPageCount() == null ? 0 : task.getPageCount()));
            }
        } else if (task.getPageCount() == null || task.getPageCount() == 0) {
            task.setPageCount(normalizedResultJson.size());
        }
        taskRepository.save(task);
        return accepted(taskId, task.getStatus());
    }

    @Transactional
    public TaskDtos.TaskDetailResponse resumeFromHumanReview(Long taskId, TaskDtos.HumanReviewResumeRequest request) {
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        if (task.getWorkflowThreadId() == null || task.getWorkflowThreadId().isBlank()) {
            throw new ResponseStatusException(BAD_REQUEST, "Task does not have a resumable workflow checkpoint.");
        }
        taskCommandProducer.publishResume(task, request.resumePayload() == null ? objectMapper.createObjectNode() : request.resumePayload());
        task.setStatus(normalizeStatus(OcrTaskStatus.QUEUED));
        task.setReviewStatus("resume_requested");
        task.setReviewReason("人工复核结果已提交，等待工作流恢复执行。");
        taskRepository.save(task);
        return toDetail(task);
    }

    private TaskDtos.TaskListResponse paginateTasks(List<OcrTaskEntity> tasks, int page, int pageSize) {
        int safePage = Math.max(1, page);
        int safePageSize = Math.max(1, pageSize);
        int fromIndex = Math.min(tasks.size(), (safePage - 1) * safePageSize);
        int toIndex = Math.min(tasks.size(), fromIndex + safePageSize);
        return new TaskDtos.TaskListResponse(
                tasks.size(),
                tasks.subList(fromIndex, toIndex).stream().map(this::toSummary).toList()
        );
    }

    private List<OcrTaskEntity> findTasksBySubmissionId(String submissionId) {
        if (submissionId.startsWith(SUBMISSION_BATCH_PREFIX)) {
            String batchId = submissionId.substring(SUBMISSION_BATCH_PREFIX.length());
            if (!StringUtils.hasText(batchId)) {
                return List.of();
            }
            return taskRepository.findByBatchIdOrderByCreatedAtDesc(batchId);
        }
        if (submissionId.startsWith(SINGLE_TASK_PREFIX)) {
            Long taskId = parseLongSilently(submissionId.substring(SINGLE_TASK_PREFIX.length()));
            if (taskId == null) {
                return List.of();
            }
            return taskRepository.findById(taskId).map(List::of).orElseGet(List::of);
        }
        return List.of();
    }

    private String resolveBatchId(String batchId) {
        String safeBatchId = safe(batchId);
        if (StringUtils.hasText(safeBatchId)) {
            return safeBatchId;
        }
        return "batch_" + OffsetDateTime.now(SUBMISSION_ZONE_ID).toEpochSecond() + "_" + UUID.randomUUID().toString().substring(0, 6);
    }

    private SubmissionMetadata resolveSubmissionMetadata(String batchId, String submitterUsername) {
        OcrTaskEntity existingTask = taskRepository.findFirstByBatchIdOrderByCreatedAtAsc(batchId).orElse(null);
        if (existingTask != null && StringUtils.hasText(existingTask.getSubmissionName())) {
            return new SubmissionMetadata(
                    normalizeSubmitterUsername(existingTask.getSubmitterUsername()),
                    existingTask.getSubmissionName()
            );
        }

        String normalizedUsername = normalizeSubmitterUsername(
                existingTask != null ? existingTask.getSubmitterUsername() : submitterUsername
        );
        OffsetDateTime now = OffsetDateTime.now(SUBMISSION_ZONE_ID);
        int submissionIndex = countUserDailySubmissions(normalizedUsername, now) + 1;
        return new SubmissionMetadata(normalizedUsername, buildSubmissionName(normalizedUsername, now.toLocalDate(), submissionIndex));
    }

    private int countUserDailySubmissions(String submitterUsername, OffsetDateTime now) {
        LocalDate today = now.atZoneSameInstant(SUBMISSION_ZONE_ID).toLocalDate();
        OffsetDateTime startOfDay = today.atStartOfDay(SUBMISSION_ZONE_ID).toOffsetDateTime();
        OffsetDateTime startOfNextDay = today.plusDays(1).atStartOfDay(SUBMISSION_ZONE_ID).toOffsetDateTime();
        return (int) taskRepository
                .findBySubmitterUsernameAndCreatedAtBetweenOrderByCreatedAtAsc(submitterUsername, startOfDay, startOfNextDay)
                .stream()
                .map(OcrTaskService::submissionIdOf)
                .distinct()
                .count();
    }

    private String buildSubmissionName(String submitterUsername, LocalDate submissionDate, int submissionIndex) {
        return truncate("%s-%s-第%d次提交".formatted(
                submitterUsername,
                SUBMISSION_DATE_FORMATTER.format(submissionDate),
                Math.max(1, submissionIndex)
        ), 255);
    }

    private String normalizeSubmitterUsername(String submitterUsername) {
        String safeUsername = safe(submitterUsername);
        return truncate(StringUtils.hasText(safeUsername) ? safeUsername : DEFAULT_SUBMITTER_USERNAME, 120);
    }

    private String buildFallbackSubmissionName(OcrTaskEntity task) {
        String filename = safe(task.getFilename());
        if (StringUtils.hasText(filename)) {
            return filename;
        }
        OffsetDateTime createdAt = task.getCreatedAt() == null ? OffsetDateTime.now(SUBMISSION_ZONE_ID) : task.getCreatedAt();
        String normalizedUsername = normalizeSubmitterUsername(task.getSubmitterUsername());
        return normalizedUsername + "-" + SUBMISSION_DATE_FORMATTER.format(createdAt.atZoneSameInstant(SUBMISSION_ZONE_ID).toLocalDate()) + "-历史任务";
    }

    private void saveCallbackEvent(Long taskId, String eventId, String eventType, com.fasterxml.jackson.databind.JsonNode payload) {
        TaskCallbackEventEntity entity = new TaskCallbackEventEntity();
        entity.setTaskId(taskId);
        entity.setEventId(eventId);
        entity.setEventType(eventType);
        entity.setPayloadJson(payload);
        callbackEventRepository.save(entity);
    }

    private TaskDtos.WorkflowEventResponse toWorkflowEvent(TaskCallbackEventEntity entity) {
        JsonNode callbackPayload = entity.getPayloadJson();
        JsonNode payload = callbackPayload != null && callbackPayload.has("payload")
                ? callbackPayload.get("payload")
                : objectMapper.createObjectNode();
        JsonNode progress = callbackPayload != null && callbackPayload.has("progress")
                ? callbackPayload.get("progress")
                : objectMapper.createObjectNode();
        String occurredAt = callbackPayload != null && callbackPayload.has("occurredAt")
                ? callbackPayload.path("occurredAt").asText("")
                : "";
        String eventId = callbackPayload != null && callbackPayload.has("eventId")
                ? callbackPayload.path("eventId").asText("")
                : entity.getEventId();
        return new TaskDtos.WorkflowEventResponse(
                eventId,
                entity.getEventType(),
                entity.getCreatedAt(),
                occurredAt,
                payload,
                progress
        );
    }

    private void updateWorkflowThreadId(OcrTaskEntity task, JsonNode payload) {
        if (payload == null || payload.isNull()) {
            return;
        }
        String workflowThreadId = extractWorkflowThreadId(payload);
        if (StringUtils.hasText(workflowThreadId)) {
            task.setWorkflowThreadId(workflowThreadId);
        }
    }

    private String extractWorkflowThreadId(JsonNode payload) {
        if (payload == null || payload.isNull()) {
            return "";
        }
        return safe(payload.path("workflow_thread_id").asText(""));
    }

    private TaskDtos.TaskResponse toSummary(OcrTaskEntity task) {
        return toSummary(task, null);
    }

    private TaskDtos.TaskResponse toSummary(OcrTaskEntity task, String snippet) {
        return new TaskDtos.TaskResponse(
                task.getId(),
                task.getFilename(),
                task.getFilePath(),
                task.getBatchId(),
                task.getFileType(),
                task.getMode(),
                effectiveStatus(task),
                task.getTraceId(),
                task.getPageCount(),
                snippet,
                task.getErrorMessage(),
                task.getProgressPercent(),
                task.getCreatedAt(),
                task.getUpdatedAt()
        );
    }

    private TaskDtos.TaskDetailResponse toDetail(OcrTaskEntity task) {
        JsonNode normalizedResultJson = normalizeResultJson(task.getResultJson());
        return new TaskDtos.TaskDetailResponse(
                task.getId(),
                task.getFilename(),
                task.getFilePath(),
                task.getBatchId(),
                task.getFileType(),
                task.getMode(),
                effectiveStatus(task),
                task.getTraceId(),
                task.getPageCount(),
                task.getErrorMessage(),
                task.getProgressPercent(),
                task.getFullText(),
                normalizedResultJson,
                buildResultData(task),
                task.getAgentMeta(),
                task.getHumanReviewPayload(),
                task.getWorkflowThreadId(),
                task.getReviewStatus(),
                task.getReviewReason(),
                task.getCreatedAt(),
                task.getUpdatedAt()
        );
    }

    private JsonNode buildResultData(OcrTaskEntity task) {
        ObjectNode payload = objectMapper.createObjectNode();
        payload.set("pages", normalizeResultJson(task.getResultJson()));
        if (task.getAgentMeta() != null) {
            payload.set("agent_meta", task.getAgentMeta());
        }
        if (task.getHumanReviewPayload() != null) {
            payload.set("human_review_payload", task.getHumanReviewPayload());
        }
        if (task.getWorkflowThreadId() != null) {
            payload.put("workflow_thread_id", task.getWorkflowThreadId());
        }
        return payload;
    }

    private JsonNode normalizeResultJson(JsonNode rawResultJson) {
        if (rawResultJson == null || rawResultJson.isNull()) {
            return objectMapper.createArrayNode();
        }
        if (rawResultJson.isArray()) {
            return rawResultJson;
        }

        JsonNode pagesNode = rawResultJson.path("pages");
        if (pagesNode.isArray()) {
            return pagesNode;
        }

        if (rawResultJson.isObject() && rawResultJson.has("page_num")) {
            ArrayNode singlePageArray = objectMapper.createArrayNode();
            singlePageArray.add(rawResultJson);
            return singlePageArray;
        }

        return objectMapper.createArrayNode();
    }

    private static TaskDtos.InternalCallbackResponse accepted(Long taskId, String status) {
        return new TaskDtos.InternalCallbackResponse(true, true, taskId, status, OffsetDateTime.now().toString());
    }

    private static String effectiveStatus(OcrTaskEntity task) {
        String normalized = normalizeStatus(task.getStatus());
        if ("processing".equals(normalized)) {
            String reviewStatus = task.getReviewStatus() == null ? "" : task.getReviewStatus().trim().toLowerCase();
            boolean hasHumanReviewPayload = task.getHumanReviewPayload() != null;
            if (hasHumanReviewPayload || "pending_human_review".equals(reviewStatus) || "required".equals(reviewStatus)) {
                return "human_review";
            }
        }
        return normalized;
    }

    private static String normalizeStatus(OcrTaskStatus status) {
        if (status == null) {
            return "pending";
        }
        return switch (status) {
            case PENDING -> "pending";
            case QUEUED -> "pending";
            case WORKER_ACCEPTED, RUNNING -> "processing";
            case HUMAN_REVIEW -> "human_review";
            case COMPLETED -> "done";
            case FAILED -> "failed";
        };
    }

    private static String normalizeStatus(String rawStatus) {
        if (rawStatus == null || rawStatus.isBlank()) {
            return "pending";
        }
        return switch (rawStatus.trim().toLowerCase()) {
            case "pending", "queued" -> "pending";
            case "worker_accepted", "running", "processing" -> "processing";
            case "human_review" -> "human_review";
            case "completed", "done" -> "done";
            case "failed" -> "failed";
            default -> rawStatus.trim().toLowerCase();
        };
    }

    private static String extension(String filename) {
        int index = filename == null ? -1 : filename.lastIndexOf('.');
        return index >= 0 ? filename.substring(index).toLowerCase() : "";
    }

    private static String submissionIdOf(OcrTaskEntity task) {
        String batchId = safe(task.getBatchId());
        if (StringUtils.hasText(batchId)) {
            return SUBMISSION_BATCH_PREFIX + batchId;
        }
        return SINGLE_TASK_PREFIX + task.getId();
    }

    private static String folderFromFilePath(String filePath) {
        if (filePath == null || filePath.isBlank()) {
            return "";
        }
        Path parent = Path.of(filePath).getParent();
        return parent == null ? "" : parent.toString();
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private static Long parseLongSilently(String value) {
        try {
            return Long.parseLong(safe(value));
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private static String truncate(String value, int maxLength) {
        String safeValue = safe(value);
        if (safeValue.length() <= maxLength) {
            return safeValue;
        }
        return safeValue.substring(0, maxLength);
    }

    private static String buildSearchSnippet(OcrTaskEntity task, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return null;
        }
        String loweredKeyword = keyword.toLowerCase();
        String fullText = task.getFullText();
        if (fullText != null && fullText.toLowerCase().contains(loweredKeyword)) {
            return cutAround(fullText, loweredKeyword, 50);
        }
        String filename = task.getFilename();
        if (filename != null && filename.toLowerCase().contains(loweredKeyword)) {
            return filename;
        }
        return null;
    }

    private static String cutAround(String text, String loweredKeyword, int context) {
        String safeText = text == null ? "" : text;
        String loweredText = safeText.toLowerCase();
        int index = loweredText.indexOf(loweredKeyword);
        if (index < 0) {
            return safeText.length() <= context * 2 ? safeText : safeText.substring(0, Math.min(safeText.length(), context * 2));
        }
        int start = Math.max(0, index - context);
        int end = Math.min(safeText.length(), index + loweredKeyword.length() + context);
        String snippet = safeText.substring(start, end).replaceAll("\\s+", " ").trim();
        if (start > 0) {
            snippet = "..." + snippet;
        }
        if (end < safeText.length()) {
            snippet = snippet + "...";
        }
        return snippet;
    }

    private record SubmissionMetadata(String submitterUsername, String submissionName) {
    }

    private final class SubmissionAccumulator {
        private final String submissionId;
        private String batchId = "";
        private String submissionName = "";
        private String submitterUsername = "";
        private long count = 0;
        private OffsetDateTime lastTime;
        private Long latestTaskId;

        private SubmissionAccumulator(String submissionId) {
            this.submissionId = submissionId;
        }

        private void accept(OcrTaskEntity task) {
            count++;
            if (!StringUtils.hasText(batchId) && StringUtils.hasText(task.getBatchId())) {
                batchId = safe(task.getBatchId());
            }
            if (!StringUtils.hasText(submissionName) && StringUtils.hasText(task.getSubmissionName())) {
                submissionName = task.getSubmissionName();
            }
            if (!StringUtils.hasText(submitterUsername) && StringUtils.hasText(task.getSubmitterUsername())) {
                submitterUsername = task.getSubmitterUsername();
            }
            OffsetDateTime candidateTime = task.getUpdatedAt() != null ? task.getUpdatedAt() : task.getCreatedAt();
            if (lastTime == null || (candidateTime != null && candidateTime.isAfter(lastTime))) {
                lastTime = candidateTime;
                latestTaskId = task.getId();
            }
            if (!StringUtils.hasText(submissionName)) {
                submissionName = buildFallbackSubmissionName(task);
            }
            if (!StringUtils.hasText(submitterUsername)) {
                submitterUsername = normalizeSubmitterUsername(task.getSubmitterUsername());
            }
        }

        private TaskDtos.SubmissionSummaryResponse toResponse() {
            return new TaskDtos.SubmissionSummaryResponse(
                    submissionId,
                    batchId,
                    submissionName,
                    normalizeSubmitterUsername(submitterUsername),
                    count,
                    lastTime,
                    latestTaskId
            );
        }
    }
}
