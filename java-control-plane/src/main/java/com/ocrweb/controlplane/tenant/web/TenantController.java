package com.ocrweb.controlplane.tenant.web;

import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.tenant.dto.TenantDtos;
import com.ocrweb.controlplane.tenant.service.TenantService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class TenantController {
    private final TenantService tenantService;
    private final AuthService authService;

    public TenantController(TenantService tenantService, AuthService authService) {
        this.tenantService = tenantService;
        this.authService = authService;
    }

    @GetMapping("/api/admin/tenants")
    public TenantDtos.TenantListResponse listTenants(HttpServletRequest request) {
        authService.requirePlatformAdmin(request);
        return tenantService.listTenants();
    }

    @PostMapping("/api/admin/tenants")
    @ResponseStatus(HttpStatus.CREATED)
    public TenantDtos.TenantResponse createTenant(
            @Valid @RequestBody TenantDtos.TenantCreateRequest body,
            HttpServletRequest request
    ) {
        var currentUser = authService.requirePlatformAdmin(request);
        return tenantService.createTenant(body, currentUser, request);
    }

    @GetMapping("/api/admin/tenants/{tenantId}")
    public TenantDtos.TenantItem getTenant(@PathVariable String tenantId, HttpServletRequest request) {
        authService.requirePlatformAdmin(request);
        return tenantService.getTenant(tenantId);
    }

    @PatchMapping("/api/admin/tenants/{tenantId}")
    public TenantDtos.TenantResponse updateTenant(
            @PathVariable String tenantId,
            @Valid @RequestBody TenantDtos.TenantUpdateRequest body,
            HttpServletRequest request
    ) {
        var currentUser = authService.requirePlatformAdmin(request);
        return tenantService.updateTenant(tenantId, body, currentUser, request);
    }

    @PostMapping("/api/admin/tenants/{tenantId}/assign-user")
    public TenantDtos.AssignUserResponse assignUserToTenant(
            @PathVariable String tenantId,
            @Valid @RequestBody TenantDtos.AssignUserRequest body,
            HttpServletRequest request
    ) {
        var currentUser = authService.requirePlatformAdmin(request);
        return tenantService.assignUserToTenant(tenantId, body.userId(), currentUser, request);
    }

    @GetMapping("/api/tenants")
    public TenantDtos.PublicTenantListResponse listPublicTenants() {
        return tenantService.listPublicTenants();
    }
}