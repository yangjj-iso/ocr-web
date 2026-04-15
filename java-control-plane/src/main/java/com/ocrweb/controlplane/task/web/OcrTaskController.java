package com.ocrweb.controlplane.task.web;

import com.ocrweb.controlplane.task.dto.TaskDtos;
import com.ocrweb.controlplane.task.service.AiProxyService;
import com.ocrweb.controlplane.task.service.OcrTaskService;
import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.auth.service.CurrentUser;
import com.ocrweb.controlplane.auth.service.OperationLogService;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;

@RestController
@RequestMapping("/api/ocr")
public class OcrTaskController {
    private final OcrTaskService taskService;
    private final AiProxyService aiProxyService;
    private final AuthService authService;
    private final OperationLogService operationLogService;

    public OcrTaskController(OcrTaskService taskService, AiProxyService aiProxyService, AuthService authService, OperationLogService operationLogService) {
        this.taskService = taskService;
        this.aiProxyService = aiProxyService;
        this.authService = authService;
        this.operationLogService = operationLogService;
    }

    @PostMapping("/upload")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public TaskDtos.TaskDetailResponse upload(
            @RequestPart("file") MultipartFile file,
            @RequestParam(name = "relative_path", defaultValue = "") String relativePath,
            @RequestParam(defaultValue = "vl") String mode,
            @RequestParam(name = "batch_id", defaultValue = "") String batchId,
            HttpServletRequest request
    ) throws IOException {
        CurrentUser currentUser = authService.requireOperatorOrAdmin(request);
        return taskService.getTask(taskService.submitUpload(file, relativePath, mode, batchId, currentUser).getId());
    }

    @PostMapping("/upload-from-path")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public TaskDtos.TaskDetailResponse uploadFromPath(
            @Valid @RequestBody TaskDtos.UploadFromPathRequest request,
            @RequestParam(defaultValue = "vl") String mode,
            @RequestParam(name = "batch_id", defaultValue = "") String batchId,
            HttpServletRequest servletRequest
    ) throws IOException {
        CurrentUser currentUser = authService.requireOperatorOrAdmin(servletRequest);
        return taskService.getTask(taskService.submitExistingPath(request.filePath(), mode, batchId, currentUser).getId());
    }

    @PostMapping("/upload-only")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public TaskDtos.TaskDetailResponse uploadOnly(
            @RequestPart("file") MultipartFile file,
            @RequestParam(name = "relative_path", defaultValue = "") String relativePath,
            @RequestParam(name = "batch_id", defaultValue = "") String batchId,
            HttpServletRequest request
    ) throws IOException {
        CurrentUser currentUser = authService.requireAdmin(request);
        return taskService.getTask(taskService.uploadOnly(file, relativePath, batchId, currentUser).getId());
    }

    @PostMapping("/tasks/assign")
    public TaskDtos.BatchOperationResponse assignTasks(
            @Valid @RequestBody TaskDtos.AssignTasksRequest request,
            HttpServletRequest servletRequest
    ) {
        CurrentUser currentUser = authService.requireAdmin(servletRequest);
        int affected = taskService.assignTasks(request.taskIds(), request.assigneeUsername());
        String resourceId = request.taskIds().isEmpty() ? "" : String.valueOf(request.taskIds().get(0));
        operationLogService.writeLog(currentUser, servletRequest, "claim", "task", resourceId, java.util.Map.of(
            "task_ids", request.taskIds(),
            "assignee_username", request.assigneeUsername(),
            "message", "任务已分配"
        ));
        return new TaskDtos.BatchOperationResponse(affected, "已分配 " + affected + " 个任务");
    }

    @PostMapping("/tasks/submit-batch")
    public TaskDtos.BatchOperationResponse submitBatch(
            @Valid @RequestBody TaskDtos.SubmitBatchRequest request,
            HttpServletRequest servletRequest
    ) {
        CurrentUser currentUser = authService.requireOperatorOrAdmin(servletRequest);
        int affected = taskService.submitBatchForProcessing(request.taskIds());
        String resourceId = request.taskIds().isEmpty() ? "" : String.valueOf(request.taskIds().get(0));
        operationLogService.writeLog(currentUser, servletRequest, "submit", "task", resourceId, java.util.Map.of(
            "task_ids", request.taskIds(),
            "message", "任务已提交处理"
        ));
        return new TaskDtos.BatchOperationResponse(affected, "已提交 " + affected + " 个任务进行识别");
    }

    @GetMapping("/tasks")
    public TaskDtos.TaskListResponse listTasks(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(name = "submission_id", defaultValue = "") String submissionId,
            @RequestParam(name = "batch_id", defaultValue = "") String batchId,
            @RequestParam(defaultValue = "") String status
    ) {
        return taskService.listTasks(page, pageSize, folder, submissionId, batchId, status);
    }

    @GetMapping("/tasks/my-assigned")
    public TaskDtos.TaskListResponse listMyAssignedTasks(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(defaultValue = "") String status,
            HttpServletRequest request
    ) {
        CurrentUser currentUser = authService.requireAuthenticatedUser(request);
        return taskService.listMyAssignedTasks(currentUser.username(), status, page, pageSize);
    }

    @GetMapping("/tasks/folders")
    public List<TaskDtos.FolderSummaryResponse> listFolders() {
        return taskService.listFolders();
    }

    @GetMapping("/tasks/submissions")
    public List<TaskDtos.SubmissionSummaryResponse> listSubmissions() {
        return taskService.listSubmissions();
    }

    @GetMapping("/tasks/{taskId}")
    public TaskDtos.TaskDetailResponse getTask(@PathVariable Long taskId) {
        return taskService.getTask(taskId);
    }

    @GetMapping("/tasks/{taskId}/workflow-events")
    public TaskDtos.WorkflowEventsResponse getWorkflowEvents(@PathVariable Long taskId) {
        return taskService.getWorkflowEvents(taskId);
    }

    @org.springframework.web.bind.annotation.PutMapping("/tasks/{taskId}")
    public TaskDtos.TaskDetailResponse updateTask(
            @PathVariable Long taskId,
            @RequestBody TaskDtos.TaskUpdateRequest request,
            HttpServletRequest servletRequest
    ) {
        authService.requireOperatorOrAdmin(servletRequest);
        return taskService.updateTask(taskId, request);
    }

    @PostMapping("/tasks/{taskId}/release-decision")
    public TaskDtos.ReleaseDecisionResponse submitReleaseDecision(
            @PathVariable Long taskId,
            @RequestBody TaskDtos.ReleaseDecisionRequest request,
            HttpServletRequest servletRequest
    ) {
        CurrentUser currentUser = authService.requireOperatorOrAdmin(servletRequest);
        TaskDtos.ReleaseDecisionResponse response = taskService.submitReleaseDecision(taskId, request, currentUser);
        TaskDtos.TaskDetailResponse task = taskService.getTask(taskId);
        String actionType = "reject".equalsIgnoreCase(request == null ? null : request.decision())
                ? "rework_request"
                : "archive".equalsIgnoreCase(request == null ? null : request.action())
                    ? "archive_store"
                    : "final_release";
        java.util.Map<String, Object> detail = new java.util.LinkedHashMap<>();
        detail.put("batch_id", task.batchId());
        detail.put("decision", request == null ? "" : request.decision());
        detail.put("action", request == null ? "" : request.action());
        detail.put("rework_id", response.reworkId() == null ? "" : response.reworkId());
        detail.put("message", "reject".equalsIgnoreCase(request == null ? null : request.decision()) ? "已创建返工任务" : "已完成放行决策");
        operationLogService.writeLog(currentUser, servletRequest, actionType, "task", String.valueOf(taskId), detail);
        return response;
    }

    @PostMapping("/tasks/{taskId}/human-review/resume")
    public TaskDtos.TaskDetailResponse resumeHumanReview(
            @PathVariable Long taskId,
            @RequestBody TaskDtos.HumanReviewResumeRequest request,
            HttpServletRequest servletRequest
    ) {
        authService.requireOperatorOrAdmin(servletRequest);
        return taskService.resumeFromHumanReview(taskId, request);
    }

    @GetMapping("/tasks/search")
    public TaskDtos.SearchResponse searchTasks(
            @RequestParam String q,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize
    ) {
        return taskService.searchTasks(q, page, pageSize);
    }

    @GetMapping("/dashboard/stats")
    public TaskDtos.DashboardStatsResponse dashboardStats(
            @RequestParam(defaultValue = "7") int days,
            HttpServletRequest request
    ) {
        authService.requireAdmin(request);
        return taskService.getDashboardStats(Math.min(days, 90));
    }

    @PostMapping("/tasks/progress")
    public TaskDtos.TaskProgressResponse progress(@Valid @RequestBody TaskDtos.TaskProgressRequest request) {
        return taskService.getProgress(request.taskIds());
    }

    @DeleteMapping("/tasks/{taskId}")
    public java.util.Map<String, Object> deleteTask(@PathVariable Long taskId, HttpServletRequest request) {
        authService.requireAdmin(request);
        boolean deleted = taskService.deleteTask(taskId);
        return java.util.Map.of("deleted", deleted, "taskId", taskId);
    }

    @DeleteMapping("/tasks/by-folder")
    public java.util.Map<String, Object> deleteByFolder(@RequestParam String folder, HttpServletRequest request) {
        authService.requireAdmin(request);
        long deleted = taskService.deleteTasksByFolder(folder);
        return java.util.Map.of("deleted", deleted, "folder", folder);
    }

    @DeleteMapping("/tasks/by-submission")
    public java.util.Map<String, Object> deleteBySubmission(
            @RequestParam("submission_id") String submissionId,
            HttpServletRequest request
    ) {
        authService.requireAdmin(request);
        long deleted = taskService.deleteTasksBySubmission(submissionId);
        return java.util.Map.of("deleted", deleted, "submission_id", submissionId);
    }

    @GetMapping("/tasks/{taskId}/export")
    public ResponseEntity<?> exportTask(
            @PathVariable Long taskId,
            @RequestParam(defaultValue = "txt") String fmt,
            HttpServletRequest request
    ) {
        authService.requireOperatorOrAdmin(request);
        TaskDtos.TaskDetailResponse task = taskService.getTask(taskId);
        if ("json".equalsIgnoreCase(fmt)) {
            LinkedHashMap<String, Object> payload = new LinkedHashMap<>();
            payload.put("filename", task.filename());
            payload.put("page_count", task.pageCount());
            payload.put("full_text", task.fullText());
            payload.put("result_json", task.resultJson());
            return ResponseEntity.ok()
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload);
        }
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_PLAIN)
                .body(task.fullText() == null ? "" : task.fullText());
    }

    @GetMapping("/tasks/{taskId}/file")
    public ResponseEntity<Resource> getTaskFile(@PathVariable Long taskId) throws IOException {
        var resource = taskService.getTaskFileResource(taskId);
        MediaType mediaType = MediaType.parseMediaType(resource.contentType());
        return ResponseEntity.ok()
                .contentType(mediaType)
                .body(new ByteArrayResource(resource.content()));
    }

    @GetMapping("/tasks/{taskId}/thumbnail")
    public ResponseEntity<byte[]> getTaskThumbnail(@PathVariable Long taskId, HttpServletRequest request) {
        return aiProxyService.proxyBinaryGet(aiProxyService.taskThumbnailPath(taskId), request);
    }

    @GetMapping("/tasks/{taskId}/pages/{pageNum}/image")
    public ResponseEntity<byte[]> getTaskPageImage(
            @PathVariable Long taskId,
            @PathVariable Integer pageNum,
            HttpServletRequest request
    ) {
        return aiProxyService.proxyBinaryGet(aiProxyService.taskPageImagePath(taskId, pageNum), request);
    }

    @GetMapping("/tasks/{taskId}/extract-fields")
    public ResponseEntity<JsonNode> getTaskExtractFields(@PathVariable Long taskId, HttpServletRequest request) {
        return aiProxyService.proxyJsonGet(aiProxyService.taskExtractFieldsPath(taskId), request);
    }

    @PostMapping("/tasks/{taskId}/ai-extract-fields")
    public ResponseEntity<JsonNode> aiExtractFields(
            @PathVariable Long taskId,
            @RequestBody(required = false) JsonNode requestBody,
            HttpServletRequest request
    ) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonPost(aiProxyService.taskAiExtractFieldsPath(taskId), requestBody, request);
    }
}
