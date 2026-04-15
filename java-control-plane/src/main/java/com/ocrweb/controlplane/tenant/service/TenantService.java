package com.ocrweb.controlplane.tenant.service;

import com.ocrweb.controlplane.auth.domain.AppUserEntity;
import com.ocrweb.controlplane.auth.repository.AppUserRepository;
import com.ocrweb.controlplane.auth.service.CurrentUser;
import com.ocrweb.controlplane.auth.service.OperationLogService;
import com.ocrweb.controlplane.tenant.domain.TenantEntity;
import com.ocrweb.controlplane.tenant.dto.TenantDtos;
import com.ocrweb.controlplane.tenant.repository.TenantRepository;
import jakarta.transaction.Transactional;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@Service
public class TenantService {
    private static final String DEFAULT_TENANT_ID = "default";
    private static final String DEFAULT_TENANT_NAME = "默认机构";

    private final TenantRepository tenantRepository;
    private final AppUserRepository appUserRepository;
    private final OperationLogService operationLogService;

    public TenantService(TenantRepository tenantRepository, AppUserRepository appUserRepository, OperationLogService operationLogService) {
        this.tenantRepository = tenantRepository;
        this.appUserRepository = appUserRepository;
        this.operationLogService = operationLogService;
    }

    public TenantDtos.TenantListResponse listTenants() {
        ensureDefaultTenantExists();
        List<TenantDtos.TenantItem> items = tenantRepository.findAllByOrderByCreatedAtAsc().stream()
                .map(this::toTenantItem)
                .toList();
        return new TenantDtos.TenantListResponse(items, items.size());
    }

    public TenantDtos.TenantItem getTenant(String tenantId) {
        ensureDefaultTenantExists();
        return toTenantItem(requireTenant(tenantId));
    }

    @Transactional
    public TenantDtos.TenantResponse createTenant(TenantDtos.TenantCreateRequest body, CurrentUser currentUser, jakarta.servlet.http.HttpServletRequest request) {
        ensureDefaultTenantExists();
        String tenantId = sanitizeExplicitTenantId(body.id());
        if (tenantRepository.existsById(tenantId)) {
            throw conflict("租户 '" + tenantId + "' 已存在。");
        }

        TenantEntity tenant = new TenantEntity();
        tenant.setId(tenantId);
        tenant.setName(normalizeTenantName(body.name()));
        tenant.setStatus("active");
        tenantRepository.save(tenant);
        operationLogService.writeLog(currentUser, request, "create_tenant", "tenant", tenant.getId(), java.util.Map.of("name", tenant.getName()));
        return toTenantResponse(tenant);
    }

    @Transactional
    public TenantDtos.TenantResponse updateTenant(String tenantId, TenantDtos.TenantUpdateRequest body, CurrentUser currentUser, jakarta.servlet.http.HttpServletRequest request) {
        ensureDefaultTenantExists();
        TenantEntity tenant = requireTenant(tenantId);
        if (body.name() != null) {
            tenant.setName(normalizeTenantName(body.name()));
        }
        if (body.status() != null) {
            tenant.setStatus(body.status().strip());
        }
        tenantRepository.save(tenant);
        operationLogService.writeLog(currentUser, request, "update_tenant", "tenant", tenant.getId(), java.util.Map.of(
                "name", tenant.getName(),
                "status", tenant.getStatus()
        ));
        return toTenantResponse(tenant);
    }

    @Transactional
    public TenantDtos.AssignUserResponse assignUserToTenant(String tenantId, Long userId, CurrentUser currentUser, jakarta.servlet.http.HttpServletRequest request) {
        ensureDefaultTenantExists();
        TenantEntity tenant = requireTenant(tenantId);
        AppUserEntity user = appUserRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在。"));
        user.setTenantId(tenant.getId());
        appUserRepository.save(user);
        operationLogService.writeLog(currentUser, request, "assign_user_to_tenant", "user", String.valueOf(userId), java.util.Map.of(
            "tenant_id", tenant.getId(),
            "target_user", user.getUsername()
        ));
        return new TenantDtos.AssignUserResponse(true, user.getId(), tenant.getId());
    }

    public TenantDtos.PublicTenantListResponse listPublicTenants() {
        ensureDefaultTenantExists();
        List<TenantDtos.PublicTenantItem> items = tenantRepository.findByStatusOrderByNameAsc("active").stream()
                .map(tenant -> new TenantDtos.PublicTenantItem(tenant.getId(), tenant.getName()))
                .toList();
        return new TenantDtos.PublicTenantListResponse(items);
    }

    public String resolveActiveTenantId(String tenantId) {
        ensureDefaultTenantExists();
        String resolvedTenantId = tenantId == null || tenantId.isBlank() ? DEFAULT_TENANT_ID : tenantId.strip();
        TenantEntity tenant = tenantRepository.findById(resolvedTenantId)
                .orElseThrow(() -> badRequest("所选租户不存在。"));
        if (!"active".equalsIgnoreCase(tenant.getStatus())) {
            throw badRequest("所选租户已停用。");
        }
        return tenant.getId();
    }

    private TenantEntity requireTenant(String tenantId) {
        String normalizedTenantId = sanitizeExplicitTenantId(tenantId);
        return tenantRepository.findById(normalizedTenantId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "租户不存在。"));
    }

    private String sanitizeExplicitTenantId(String tenantId) {
        String normalizedTenantId = tenantId == null ? "" : tenantId.strip();
        if (normalizedTenantId.isBlank()) {
            throw badRequest("租户标识不能为空。");
        }
        return normalizedTenantId;
    }

    private String normalizeTenantName(String name) {
        String normalizedName = name == null ? "" : name.strip();
        if (normalizedName.isBlank()) {
            throw badRequest("租户名称不能为空。");
        }
        return normalizedName;
    }

    private TenantDtos.TenantItem toTenantItem(TenantEntity tenant) {
        return new TenantDtos.TenantItem(
                tenant.getId(),
                tenant.getName(),
                tenant.getStatus(),
                tenant.getCreatedAt(),
                appUserRepository.countByTenantId(tenant.getId())
        );
    }

    private TenantDtos.TenantResponse toTenantResponse(TenantEntity tenant) {
        return new TenantDtos.TenantResponse(tenant.getId(), tenant.getName(), tenant.getStatus());
    }

    private void ensureDefaultTenantExists() {
        if (tenantRepository.existsById(DEFAULT_TENANT_ID)) {
            return;
        }
        try {
            TenantEntity tenant = new TenantEntity();
            tenant.setId(DEFAULT_TENANT_ID);
            tenant.setName(DEFAULT_TENANT_NAME);
            tenant.setStatus("active");
            tenantRepository.saveAndFlush(tenant);
        } catch (DataIntegrityViolationException ignored) {
            // 并发初始化时允许其他请求先创建默认租户。
        }
    }

    private ResponseStatusException badRequest(String detail) {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, detail);
    }

    private ResponseStatusException conflict(String detail) {
        return new ResponseStatusException(HttpStatus.CONFLICT, detail);
    }
}