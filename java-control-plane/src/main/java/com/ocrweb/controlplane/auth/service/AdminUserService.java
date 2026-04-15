package com.ocrweb.controlplane.auth.service;

import com.ocrweb.controlplane.auth.domain.AppUserEntity;
import com.ocrweb.controlplane.auth.domain.UserQuotaEntity;
import com.ocrweb.controlplane.auth.dto.AdminUserDtos;
import com.ocrweb.controlplane.auth.repository.AppUserRepository;
import com.ocrweb.controlplane.auth.repository.UserQuotaRepository;
import jakarta.transaction.Transactional;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.OffsetDateTime;
import java.util.List;

@Service
public class AdminUserService {
    private final AppUserRepository appUserRepository;
    private final UserQuotaRepository userQuotaRepository;
    private final OperationLogService operationLogService;

    public AdminUserService(AppUserRepository appUserRepository, UserQuotaRepository userQuotaRepository, OperationLogService operationLogService) {
        this.appUserRepository = appUserRepository;
        this.userQuotaRepository = userQuotaRepository;
        this.operationLogService = operationLogService;
    }

    public AdminUserDtos.UserListResponse listUsers(CurrentUser caller, String role, String status) {
        List<AppUserEntity> users = caller != null && "tenant_admin".equals(caller.effectiveRole())
                ? appUserRepository.findByTenantIdOrderByCreatedAtDesc(caller.effectiveTenantId())
                : appUserRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"));

        List<AdminUserDtos.UserItem> items = users.stream()
                .filter(user -> role == null || role.isBlank() || role.equals(user.getRole()))
                .filter(user -> status == null || status.isBlank() || status.equals(user.getStatus()))
                .map(this::toUserItem)
                .toList();
        return new AdminUserDtos.UserListResponse(items, items.size());
    }

    @Transactional
    public AdminUserDtos.UserRoleResponse setUserRole(CurrentUser caller, Long userId, AdminUserDtos.RoleUpdateRequest body, jakarta.servlet.http.HttpServletRequest request) {
        AppUserEntity user = requireUser(userId);
        ensureCallerCanManageUser(caller, user);

        String role = body.role() == null ? "member" : body.role().strip();
        if ("tenant_admin".equals(caller.effectiveRole()) && "admin".equals(role)) {
            throw forbidden("租户管理员无权指派超级管理员角色。");
        }

        user.setRole(role);
        user.setAdmin("admin".equals(role));
        if (body.capabilities() != null) {
            user.setCapabilities(body.capabilities().strip());
        } else if (!"member".equals(role)) {
            user.setCapabilities(null);
        }
        appUserRepository.save(user);
        operationLogService.writeLog(caller, request, "set_role", "user", String.valueOf(userId), java.util.Map.of(
                "new_role", user.getRole(),
                "capabilities", user.getCapabilities(),
                "target_user", user.getUsername()
        ));
        return new AdminUserDtos.UserRoleResponse(user.getId(), user.getRole());
    }

    @Transactional
    public AdminUserDtos.UserDisplayNameResponse setDisplayName(CurrentUser caller, Long userId, String displayName, jakarta.servlet.http.HttpServletRequest request) {
        AppUserEntity user = requireUser(userId);
        ensureCallerCanManageUser(caller, user);

        String normalized = displayName == null ? null : displayName.strip();
        user.setDisplayName(normalized == null || normalized.isEmpty() ? null : normalized);
        appUserRepository.save(user);
        operationLogService.writeLog(caller, request, "update_display_name", "user", String.valueOf(userId), java.util.Map.of(
            "display_name", user.getDisplayName() == null ? "" : user.getDisplayName(),
            "target_user", user.getUsername()
        ));
        return new AdminUserDtos.UserDisplayNameResponse(user.getId(), user.getDisplayName());
    }

    public AdminUserDtos.QuotaResponse getQuota(CurrentUser caller, Long userId) {
        AppUserEntity user = requireUser(userId);
        ensureCallerCanManageUser(caller, user);
        return toQuotaResponse(loadOrCreateQuota(userId));
    }

    @Transactional
    public AdminUserDtos.QuotaResponse updateQuota(CurrentUser caller, Long userId, AdminUserDtos.QuotaUpdateRequest body, jakarta.servlet.http.HttpServletRequest request) {
        AppUserEntity user = requireUser(userId);
        ensureCallerCanManageUser(caller, user);

        UserQuotaEntity quota = loadOrCreateQuota(userId);
        quota.setQuotaPerImport(body.quotaPerImport());
        quota.setQuotaTotal(body.quotaTotal());
        userQuotaRepository.save(quota);
        operationLogService.writeLog(caller, request, "update_quota", "user", String.valueOf(userId), java.util.Map.of(
                "quota_per_import", quota.getQuotaPerImport(),
                "quota_total", quota.getQuotaTotal(),
                "target_user", user.getUsername()
        ));
        return toQuotaResponse(quota);
    }

    @Transactional
    public AdminUserDtos.QuotaResponse resetQuota(CurrentUser caller, Long userId, jakarta.servlet.http.HttpServletRequest request) {
        AppUserEntity user = requireUser(userId);
        ensureCallerCanManageUser(caller, user);

        UserQuotaEntity quota = loadOrCreateQuota(userId);
        quota.setQuotaUsed(0);
        quota.setResetAt(OffsetDateTime.now());
        userQuotaRepository.save(quota);
        operationLogService.writeLog(caller, request, "reset_quota", "user", String.valueOf(userId), java.util.Map.of(
                "target_user", user.getUsername()
        ));
        return toQuotaResponse(quota);
    }

    public AdminUserDtos.QuotaResponse getMyQuota(CurrentUser caller) {
        if (caller == null || caller.userId() == null) {
            return new AdminUserDtos.QuotaResponse(null, 9999, 9999, 0, 9999, null);
        }
        return toQuotaResponse(loadOrCreateQuota(caller.userId()));
    }

    @Transactional
    public AdminUserDtos.QuotaResponse consumeQuota(CurrentUser caller, int count, String batchId, jakarta.servlet.http.HttpServletRequest request) {
        if (caller == null || caller.userId() == null || count <= 0) {
            return getMyQuota(caller);
        }
        UserQuotaEntity quota = loadOrCreateQuota(caller.userId());
        int nextUsed = quota.getQuotaUsed() + count;
        if (nextUsed > quota.getQuotaTotal()) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.TOO_MANY_REQUESTS,
                    "超出总配额限制（已用 " + quota.getQuotaUsed() + "，总额 " + quota.getQuotaTotal() + "）");
        }
        quota.setQuotaUsed(nextUsed);
        userQuotaRepository.save(quota);
        operationLogService.writeLog(caller, request, "import_files", "batch", batchId, java.util.Map.of("file_count", count));
        return toQuotaResponse(quota);
    }

    private AdminUserDtos.UserItem toUserItem(AppUserEntity user) {
        UserQuotaEntity quota = userQuotaRepository.findByUserId(user.getId()).orElse(null);
        return new AdminUserDtos.UserItem(
                user.getId(),
                user.getUsername(),
                user.getDisplayName(),
                user.getRole(),
                user.getCapabilities(),
                user.getStatus(),
                user.isAdmin(),
                user.getTenantId(),
                user.getCreatedAt(),
                quota == null ? null : toQuotaResponse(quota)
        );
    }

    private AdminUserDtos.QuotaResponse toQuotaResponse(UserQuotaEntity quota) {
        int total = quota.getQuotaTotal();
        int used = quota.getQuotaUsed();
        return new AdminUserDtos.QuotaResponse(
                quota.getUserId(),
                quota.getQuotaPerImport(),
                total,
                used,
                Math.max(0, total - used),
                quota.getResetAt()
        );
    }

    private AppUserEntity requireUser(Long userId) {
        return appUserRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在。"));
    }

    private void ensureCallerCanManageUser(CurrentUser caller, AppUserEntity user) {
        if (caller == null) {
            throw forbidden("权限不足。");
        }
        if (caller.isAdmin() || "admin".equals(caller.effectiveRole())) {
            return;
        }
        if ("tenant_admin".equals(caller.effectiveRole()) && caller.effectiveTenantId().equals(user.getTenantId())) {
            return;
        }
        throw forbidden("无权操作其他租户的用户。");
    }

    private UserQuotaEntity loadOrCreateQuota(Long userId) {
        UserQuotaEntity existing = userQuotaRepository.findByUserIdForUpdate(userId).orElse(null);
        if (existing != null) {
            return existing;
        }

        try {
            UserQuotaEntity created = new UserQuotaEntity();
            created.setUserId(userId);
            return userQuotaRepository.saveAndFlush(created);
        } catch (DataIntegrityViolationException ignored) {
            return userQuotaRepository.findByUserIdForUpdate(userId)
                    .orElseThrow(() -> new IllegalStateException("Failed to resolve quota row for user " + userId));
        }
    }

    private ResponseStatusException forbidden(String detail) {
        return new ResponseStatusException(HttpStatus.FORBIDDEN, detail);
    }
}