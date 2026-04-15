package com.ocrweb.controlplane.archive.web;

import com.ocrweb.controlplane.archive.dto.ReworkDtos;
import com.ocrweb.controlplane.archive.service.ReworkTaskService;
import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.auth.service.CurrentUser;
import com.ocrweb.controlplane.auth.service.OperationLogService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.springframework.http.HttpStatus.CREATED;

@RestController
@RequestMapping("/api/ocr/rework-tasks")
public class ReworkTaskController {
    private final ReworkTaskService reworkTaskService;
    private final AuthService authService;
    private final OperationLogService operationLogService;

    public ReworkTaskController(ReworkTaskService reworkTaskService, AuthService authService, OperationLogService operationLogService) {
        this.reworkTaskService = reworkTaskService;
        this.authService = authService;
        this.operationLogService = operationLogService;
    }

    @GetMapping
    public ReworkDtos.ReworkTaskListResponse listReworkTasks(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(name = "page_size", defaultValue = "20") int pageSize,
            @RequestParam(name = "status", required = false) String status,
            @RequestParam(name = "q", required = false) String keyword,
            @RequestParam(name = "mine", required = false) Boolean mine,
            @RequestParam(name = "reporter", required = false) String reporter,
            HttpServletRequest request
    ) {
        CurrentUser currentUser = authService.requireAuthenticatedUser(request);
        return reworkTaskService.listTasks(currentUser, status, keyword, mine, reporter, page, pageSize);
    }

    @PostMapping
    @ResponseStatus(CREATED)
    public ReworkDtos.ReworkStatusResponse createReworkTask(
            @RequestBody ReworkDtos.ReworkCreateRequest body,
            HttpServletRequest request
    ) {
        CurrentUser currentUser = authService.requireAuthenticatedUser(request);
        ReworkDtos.ReworkStatusResponse response = reworkTaskService.create(currentUser, body);
        Map<String, Object> detail = new LinkedHashMap<>();
        detail.put("batch_id", response.batchId());
        detail.put("record_id", body == null ? "" : body.recordId());
        detail.put("issue_type", body == null ? "" : body.issueType());
        detail.put("message", "返工任务已创建");
        operationLogService.writeLog(currentUser, request, "rework_request", "rework_task", response.id(), detail);
        return response;
    }

    @GetMapping("/{taskId}")
    public ReworkDtos.ReworkTaskResponse getReworkTask(@PathVariable String taskId, HttpServletRequest request) {
        CurrentUser currentUser = authService.requireAuthenticatedUser(request);
        return reworkTaskService.get(currentUser, taskId);
    }

    @PostMapping("/{taskId}/accept")
    public ReworkDtos.ReworkStatusResponse acceptReworkTask(@PathVariable String taskId, HttpServletRequest request) {
        CurrentUser currentUser = authService.requireAuthenticatedUser(request);
        ReworkDtos.ReworkStatusResponse response = reworkTaskService.accept(currentUser, taskId);
        operationLogService.writeLog(currentUser, request, "rework_accept", "rework_task", taskId, Map.of(
                "batch_id", response.batchId(),
                "message", "返工任务已受理"
        ));
        return response;
    }

    @PostMapping("/{taskId}/reject")
    public ReworkDtos.ReworkStatusResponse rejectReworkTask(
            @PathVariable String taskId,
            @RequestBody(required = false) ReworkDtos.RejectReasonRequest body,
            HttpServletRequest request
    ) {
        CurrentUser currentUser = authService.requireAuthenticatedUser(request);
        String reason = body == null ? "" : body.reason();
        ReworkDtos.ReworkStatusResponse response = reworkTaskService.reject(currentUser, taskId, reason);
        operationLogService.writeLog(currentUser, request, "rework_reject", "rework_task", taskId, Map.of(
                "batch_id", response.batchId(),
                "reason", reason == null ? "" : reason,
                "message", "返工任务已驳回"
        ));
        return response;
    }
}