package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

import static org.springframework.http.HttpStatus.BAD_REQUEST;

@Service
public class OcrTaskService {
    private static final Logger logger = LoggerFactory.getLogger(OcrTaskService.class);
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
    public OcrTaskEntity submitUpload(MultipartFile file, String relativePath, String mode, String batchId) throws IOException {
        logger.info(
                "Submitting uploaded OCR task: filename={}, relativePath={}, mode={}, batchId={}",
                file.getOriginalFilename(),
                relativePath,
                mode,
                batchId
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
        task.setBatchId(batchId);
        task.setTraceId(RequestTraceContext.getTraceId());
        task.setStatus(normalizeStatus(OcrTaskStatus.QUEUED));
        OcrTaskEntity saved = taskRepository.save(task);
        taskCommandProducer.publish(saved);
        logger.info(
                "OCR task queued: taskId={}, filename={}, mode={}, batchId={}, traceId={}",
                saved.getId(),
                saved.getFilename(),
                saved.getMode(),
                saved.getBatchId(),
                saved.getTraceId()
        );
        return saved;
    }

    @Transactional
    public OcrTaskEntity submitExistingPath(String filePath, String mode, String batchId) throws IOException {
        logger.info(
                "Submitting existing-path OCR task: filePath={}, mode={}, batchId={}",
                filePath,
                mode,
                batchId
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
        task.setBatchId(batchId);
        task.setTraceId(RequestTraceContext.getTraceId());
        task.setStatus(normalizeStatus(OcrTaskStatus.QUEUED));
        OcrTaskEntity saved = taskRepository.save(task);
        taskCommandProducer.publish(saved);
        logger.info(
                "OCR task queued from existing path: taskId={}, filename={}, mode={}, batchId={}, traceId={}",
                saved.getId(),
                saved.getFilename(),
                saved.getMode(),
                saved.getBatchId(),
                saved.getTraceId()
        );
        return saved;
    }

    public TaskDtos.TaskListResponse listTasks(int page, int pageSize, String folder) {
        var tasks = taskRepository.findByFolder(folder == null ? "" : folder, PageRequest.of(Math.max(0, page - 1), pageSize));
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

    public TaskDtos.TaskDetailResponse getTask(Long taskId) {
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        return toDetail(task);
    }

    public TaskStorageService.StoredFileResource getTaskFileResource(Long taskId) throws IOException {
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        return storageService.loadTaskResource(task);
    }

    @Transactional
    public TaskDtos.TaskDetailResponse updateTask(Long taskId, TaskDtos.TaskUpdateRequest request) {
        OcrTaskEntity task = taskRepository.findById(taskId).orElseThrow();
        if (request.resultJson() != null) {
            task.setResultJson(request.resultJson());
            task.setPageCount(request.resultJson().isArray() ? request.resultJson().size() : task.getPageCount());
        }
        if (request.fullText() != null) {
            task.setFullText(request.fullText());
        } else if (request.resultJson() != null) {
            task.setFullText(request.resultJson().toString());
        }
        taskRepository.save(task);
        return toDetail(task);
    }

    @Transactional
    public boolean deleteTask(Long taskId) {
        if (!taskRepository.existsById(taskId)) {
            return false;
        }
        taskRepository.deleteById(taskId);
        return true;
    }

    @Transactional
    public long deleteTasksByFolder(String folder) {
        return taskRepository.deleteByFilePathStartingWith(folder);
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
        task.setResultJson(request.result());
        task.setAgentMeta(request.agentMeta());
        if (task.getTraceId() == null || task.getTraceId().isBlank()) {
            task.setTraceId(request.traceId());
        }
        task.setFullText(request.fullText() == null || request.fullText().isBlank()
                ? (request.result() == null ? null : request.result().toString())
                : request.fullText());
        task.setErrorMessage(null);
        task.setPageCount(request.summary() != null && request.summary().has("total_pages") ? request.summary().get("total_pages").asInt() : 0);
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
        task.setResultJson(request.result());
        task.setFullText(request.fullText() == null || request.fullText().isBlank()
                ? (request.result() == null ? null : request.result().toString())
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

    private void saveCallbackEvent(Long taskId, String eventId, String eventType, com.fasterxml.jackson.databind.JsonNode payload) {
        TaskCallbackEventEntity entity = new TaskCallbackEventEntity();
        entity.setTaskId(taskId);
        entity.setEventId(eventId);
        entity.setEventType(eventType);
        entity.setPayloadJson(payload);
        callbackEventRepository.save(entity);
    }

    private TaskDtos.TaskResponse toSummary(OcrTaskEntity task) {
        return toSummary(task, null);
    }

    private TaskDtos.TaskResponse toSummary(OcrTaskEntity task, String snippet) {
        return new TaskDtos.TaskResponse(
                task.getId(),
                task.getFilename(),
                task.getFilePath(),
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
        return new TaskDtos.TaskDetailResponse(
                task.getId(),
                task.getFilename(),
                task.getFilePath(),
                task.getFileType(),
                task.getMode(),
                effectiveStatus(task),
                task.getTraceId(),
                task.getPageCount(),
                task.getErrorMessage(),
                task.getProgressPercent(),
                task.getFullText(),
                task.getResultJson(),
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
        if (task.getResultJson() != null) {
            payload.set("pages", task.getResultJson());
        } else {
            payload.putArray("pages");
        }
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

    private static String folderFromFilePath(String filePath) {
        if (filePath == null || filePath.isBlank()) {
            return "";
        }
        Path parent = Path.of(filePath).getParent();
        return parent == null ? "" : parent.toString();
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
}
