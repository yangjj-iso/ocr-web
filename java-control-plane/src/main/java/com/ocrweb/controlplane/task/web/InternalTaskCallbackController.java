package com.ocrweb.controlplane.task.web;

import com.ocrweb.controlplane.config.InternalApiProperties;
import com.ocrweb.controlplane.task.dto.TaskDtos;
import com.ocrweb.controlplane.task.service.OcrTaskService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import static org.springframework.http.HttpStatus.UNAUTHORIZED;

@RestController
@RequestMapping("/internal/api/v1/ocr/tasks")
public class InternalTaskCallbackController {
    private final OcrTaskService taskService;
    private final InternalApiProperties internalApiProperties;

    public InternalTaskCallbackController(OcrTaskService taskService, InternalApiProperties internalApiProperties) {
        this.taskService = taskService;
        this.internalApiProperties = internalApiProperties;
    }

    @PostMapping("/{taskId}/events")
    public TaskDtos.InternalCallbackResponse event(
            @PathVariable Long taskId,
            @Valid @RequestBody TaskDtos.TaskEventRequest request,
            HttpServletRequest servletRequest
    ) {
        verifyInternalToken(servletRequest);
        return taskService.handleEvent(taskId, request);
    }

    @PostMapping("/{taskId}/completion")
    public TaskDtos.InternalCallbackResponse completion(
            @PathVariable Long taskId,
            @Valid @RequestBody TaskDtos.TaskCompletionRequest request,
            HttpServletRequest servletRequest
    ) {
        verifyInternalToken(servletRequest);
        return taskService.handleCompletion(taskId, request);
    }

    @PostMapping("/{taskId}/failure")
    public TaskDtos.InternalCallbackResponse failure(
            @PathVariable Long taskId,
            @Valid @RequestBody TaskDtos.TaskFailureRequest request,
            HttpServletRequest servletRequest
    ) {
        verifyInternalToken(servletRequest);
        return taskService.handleFailure(taskId, request);
    }

    @PostMapping("/{taskId}/pause")
    public TaskDtos.InternalCallbackResponse pause(
            @PathVariable Long taskId,
            @Valid @RequestBody TaskDtos.TaskPauseRequest request,
            HttpServletRequest servletRequest
    ) {
        verifyInternalToken(servletRequest);
        return taskService.handlePause(taskId, request);
    }

    @GetMapping("/{taskId}/source-file")
    public ResponseEntity<Resource> sourceFile(@PathVariable Long taskId, HttpServletRequest servletRequest) throws java.io.IOException {
        verifyInternalToken(servletRequest);
        var resource = taskService.getTaskFileResource(taskId);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(resource.contentType()))
                .body(new ByteArrayResource(resource.content()));
    }

    private void verifyInternalToken(HttpServletRequest request) {
        if (!StringUtils.hasText(internalApiProperties.getToken())) {
            return;
        }
        String expected = "Bearer " + internalApiProperties.getToken();
        String actual = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (!expected.equals(actual)) {
            throw new ResponseStatusException(UNAUTHORIZED, "Invalid internal token.");
        }
    }
}
