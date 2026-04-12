package com.ocrweb.controlplane.dev.web;

import com.ocrweb.controlplane.dev.dto.DevDashboardDtos;
import com.ocrweb.controlplane.dev.service.DevDashboardAuthService;
import com.ocrweb.controlplane.dev.service.DevDashboardService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/dev/dashboard")
public class DevDashboardController {
    private final DevDashboardAuthService authService;
    private final DevDashboardService dashboardService;

    public DevDashboardController(DevDashboardAuthService authService, DevDashboardService dashboardService) {
        this.authService = authService;
        this.dashboardService = dashboardService;
    }

    @GetMapping("/auth/status")
    public DevDashboardDtos.AuthStatusResponse status(HttpServletRequest request) {
        return authService.status(request);
    }

    @PostMapping("/auth/login")
    public ResponseEntity<DevDashboardDtos.LoginResponse> login(@RequestBody(required = false) DevDashboardDtos.LoginRequest request) {
        DevDashboardDtos.LoginRequest body = request == null ? new DevDashboardDtos.LoginRequest("", "", "") : request;
        DevDashboardAuthService.LoginResult result = authService.login(body.username(), body.password(), body.twoFactorCode());
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, result.setCookieHeader())
                .body(result.payload());
    }

    @PostMapping("/auth/logout")
    public ResponseEntity<Map<String, Object>> logout() {
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, authService.buildLogoutCookie())
                .body(Map.of("authenticated", false));
    }

    @GetMapping("/snapshot")
    public DevDashboardDtos.SnapshotResponse snapshot(HttpServletRequest request) {
        authService.requireSession(request);
        return dashboardService.snapshot();
    }

    @GetMapping("/tasks")
    public DevDashboardDtos.SnapshotResponse tasks(HttpServletRequest request) {
        authService.requireSession(request);
        return dashboardService.snapshot();
    }

    @PostMapping("/tasks/{taskId}/retry")
    public DevDashboardDtos.RetryResponse retry(@PathVariable Long taskId, HttpServletRequest request) {
        authService.requireSession(request);
        return dashboardService.retry(taskId);
    }
}
