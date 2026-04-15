package com.ocrweb.controlplane.auth.web;

import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.auth.service.OperationLogService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class OperationLogController {
    private final AuthService authService;
    private final OperationLogService operationLogService;

    public OperationLogController(AuthService authService, OperationLogService operationLogService) {
        this.authService = authService;
        this.operationLogService = operationLogService;
    }

    @GetMapping("/api/admin/operation-logs")
    public Map<String, Object> listOperationLogs(
            @RequestParam(required = false, name = "user_id") Long userId,
            @RequestParam(required = false, name = "action_type") String actionType,
            @RequestParam(defaultValue = "100") int limit,
            @RequestParam(defaultValue = "0") int offset,
            HttpServletRequest request
    ) {
        authService.requireAdmin(request);
        return operationLogService.listLogs(userId, actionType, limit, offset);
    }
}