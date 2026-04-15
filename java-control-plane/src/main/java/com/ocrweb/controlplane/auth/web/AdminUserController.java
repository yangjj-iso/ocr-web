package com.ocrweb.controlplane.auth.web;

import com.ocrweb.controlplane.auth.dto.AdminUserDtos;
import com.ocrweb.controlplane.auth.service.AdminUserService;
import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.auth.service.CurrentUser;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AdminUserController {
    private final AuthService authService;
    private final AdminUserService adminUserService;

    public AdminUserController(AuthService authService, AdminUserService adminUserService) {
        this.authService = authService;
        this.adminUserService = adminUserService;
    }

    @GetMapping("/api/admin/users")
    public AdminUserDtos.UserListResponse listUsers(
            @RequestParam(required = false) String role,
            @RequestParam(required = false, name = "status") String status,
            HttpServletRequest request
    ) {
        CurrentUser caller = authService.requireAdmin(request);
        return adminUserService.listUsers(caller, role, status);
    }

    @PutMapping("/api/admin/users/{userId}/role")
    public AdminUserDtos.UserRoleResponse setUserRole(
            @PathVariable Long userId,
            @Valid @RequestBody AdminUserDtos.RoleUpdateRequest body,
            HttpServletRequest request
    ) {
        CurrentUser caller = authService.requireAdmin(request);
        return adminUserService.setUserRole(caller, userId, body, request);
    }

    @PutMapping("/api/admin/users/{userId}/display-name")
    public AdminUserDtos.UserDisplayNameResponse setDisplayName(
            @PathVariable Long userId,
            @Valid @RequestBody AdminUserDtos.DisplayNameUpdateRequest body,
            HttpServletRequest request
    ) {
        CurrentUser caller = authService.requireAdmin(request);
        return adminUserService.setDisplayName(caller, userId, body.displayName(), request);
    }

    @GetMapping("/api/admin/users/{userId}/quota")
    public AdminUserDtos.QuotaResponse getUserQuota(@PathVariable Long userId, HttpServletRequest request) {
        CurrentUser caller = authService.requireAdmin(request);
        return adminUserService.getQuota(caller, userId);
    }

    @PutMapping("/api/admin/users/{userId}/quota")
    public AdminUserDtos.QuotaResponse updateUserQuota(
            @PathVariable Long userId,
            @Valid @RequestBody AdminUserDtos.QuotaUpdateRequest body,
            HttpServletRequest request
    ) {
        CurrentUser caller = authService.requireAdmin(request);
        return adminUserService.updateQuota(caller, userId, body, request);
    }

    @PostMapping("/api/admin/users/{userId}/quota/reset")
    public AdminUserDtos.QuotaResponse resetUserQuota(@PathVariable Long userId, HttpServletRequest request) {
        CurrentUser caller = authService.requireAdmin(request);
        return adminUserService.resetQuota(caller, userId, request);
    }

    @GetMapping("/api/operator/my-quota")
    public AdminUserDtos.QuotaResponse getMyQuota(HttpServletRequest request) {
        CurrentUser caller = authService.requireAuthenticatedUser(request);
        return adminUserService.getMyQuota(caller);
    }

    @PostMapping("/api/operator/my-quota/consume")
    public AdminUserDtos.QuotaResponse consumeMyQuota(
            @RequestBody(required = false) java.util.Map<String, Object> body,
            HttpServletRequest request
    ) {
        CurrentUser caller = authService.requireAuthenticatedUser(request);
        int count = 0;
        if (body != null && body.get("count") != null) {
            count = Integer.parseInt(String.valueOf(body.get("count")));
        }
        String batchId = body == null ? null : String.valueOf(body.getOrDefault("batch_id", ""));
        return adminUserService.consumeQuota(caller, count, batchId, request);
    }
}