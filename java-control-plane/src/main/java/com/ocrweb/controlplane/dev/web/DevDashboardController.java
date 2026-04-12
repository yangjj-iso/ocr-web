package com.ocrweb.controlplane.dev.web;

import com.ocrweb.controlplane.dev.dto.DevDashboardDtos;
import com.ocrweb.controlplane.dev.service.DevDashboardAuthService;
import com.ocrweb.controlplane.dev.service.DevDashboardService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/dev/dashboard")
public class DevDashboardController {
    private final DevDashboardAuthService authService;
    private final DevDashboardService dashboardService;

    public DevDashboardController(DevDashboardAuthService authService, DevDashboardService dashboardService) {
        this.authService = authService;
        this.dashboardService = dashboardService;
    }

    @GetMapping("/me")
    public DevDashboardDtos.AuthStatus me(HttpServletRequest request) {
        String username = authService.resolveUsername(request);
        return new DevDashboardDtos.AuthStatus(authService.isConfigured(), !username.isBlank(), username);
    }

    @PostMapping("/login")
    public ResponseEntity<DevDashboardDtos.AuthStatus> login(@RequestBody DevDashboardDtos.LoginRequest request) {
        String setCookie = authService.authenticate(request.username(), request.password());
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, setCookie)
                .body(new DevDashboardDtos.AuthStatus(true, true, request.username()));
    }

    @PostMapping("/logout")
    public ResponseEntity<DevDashboardDtos.AuthStatus> logout() {
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, authService.buildLogoutCookie())
                .body(new DevDashboardDtos.AuthStatus(authService.isConfigured(), false, ""));
    }

    @GetMapping("/metrics")
    public DevDashboardDtos.DashboardSnapshot metrics(HttpServletRequest request) {
        authService.requireAuthenticated(request);
        return dashboardService.snapshot();
    }
}
