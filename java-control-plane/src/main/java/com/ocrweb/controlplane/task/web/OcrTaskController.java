package com.ocrweb.controlplane.task.web;

import com.ocrweb.controlplane.task.dto.TaskDtos;
import com.ocrweb.controlplane.task.service.AiProxyService;
import com.ocrweb.controlplane.task.service.OcrTaskService;
import com.ocrweb.controlplane.auth.service.CurrentUser;
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

    public OcrTaskController(OcrTaskService taskService, AiProxyService aiProxyService) {
        this.taskService = taskService;
        this.aiProxyService = aiProxyService;
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
        return taskService.getTask(taskService.submitUpload(file, relativePath, mode, batchId, currentUsername(request)).getId());
    }

    @PostMapping("/upload-from-path")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public TaskDtos.TaskDetailResponse uploadFromPath(
            @Valid @RequestBody TaskDtos.UploadFromPathRequest request,
            @RequestParam(defaultValue = "vl") String mode,
            @RequestParam(name = "batch_id", defaultValue = "") String batchId,
            HttpServletRequest servletRequest
    ) throws IOException {
        return taskService.getTask(taskService.submitExistingPath(request.filePath(), mode, batchId, currentUsername(servletRequest)).getId());
    }

    @GetMapping("/tasks")
    public TaskDtos.TaskListResponse listTasks(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(name = "submission_id", defaultValue = "") String submissionId,
            @RequestParam(name = "batch_id", defaultValue = "") String batchId
    ) {
        return taskService.listTasks(page, pageSize, folder, submissionId, batchId);
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

    @org.springframework.web.bind.annotation.PutMapping("/tasks/{taskId}")
    public TaskDtos.TaskDetailResponse updateTask(
            @PathVariable Long taskId,
            @RequestBody TaskDtos.TaskUpdateRequest request
    ) {
        return taskService.updateTask(taskId, request);
    }

    @PostMapping("/tasks/{taskId}/human-review/resume")
    public TaskDtos.TaskDetailResponse resumeHumanReview(
            @PathVariable Long taskId,
            @RequestBody TaskDtos.HumanReviewResumeRequest request
    ) {
        return taskService.resumeFromHumanReview(taskId, request);
    }

    @GetMapping("/tasks/search")
    public TaskDtos.TaskListResponse searchTasks(
            @RequestParam String q,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize
    ) {
        return taskService.searchTasks(q, page, pageSize);
    }

    @PostMapping("/tasks/progress")
    public TaskDtos.TaskProgressResponse progress(@Valid @RequestBody TaskDtos.TaskProgressRequest request) {
        return taskService.getProgress(request.taskIds());
    }

    @DeleteMapping("/tasks/{taskId}")
    public java.util.Map<String, Object> deleteTask(@PathVariable Long taskId) {
        boolean deleted = taskService.deleteTask(taskId);
        return java.util.Map.of("deleted", deleted, "taskId", taskId);
    }

    @DeleteMapping("/tasks/by-folder")
    public java.util.Map<String, Object> deleteByFolder(@RequestParam String folder) {
        long deleted = taskService.deleteTasksByFolder(folder);
        return java.util.Map.of("deleted", deleted, "folder", folder);
    }

    @DeleteMapping("/tasks/by-submission")
    public java.util.Map<String, Object> deleteBySubmission(@RequestParam("submission_id") String submissionId) {
        long deleted = taskService.deleteTasksBySubmission(submissionId);
        return java.util.Map.of("deleted", deleted, "submission_id", submissionId);
    }

    @GetMapping("/tasks/{taskId}/export")
    public ResponseEntity<?> exportTask(
            @PathVariable Long taskId,
            @RequestParam(defaultValue = "txt") String fmt
    ) {
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
        return aiProxyService.proxyJsonPost(aiProxyService.taskAiExtractFieldsPath(taskId), requestBody, request);
    }

    private static String currentUsername(HttpServletRequest request) {
        Object currentUser = request.getAttribute(CurrentUser.REQUEST_ATTRIBUTE);
        if (currentUser instanceof CurrentUser user && user.username() != null && !user.username().isBlank()) {
            return user.username().trim();
        }
        return "";
    }
}
