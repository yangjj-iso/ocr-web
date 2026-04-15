package com.ocrweb.controlplane.auth.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;
import java.util.List;

public final class AdminUserDtos {
    private AdminUserDtos() {
    }

    public record QuotaResponse(
            @JsonProperty("user_id") Long userId,
            @JsonProperty("quota_per_import") int quotaPerImport,
            @JsonProperty("quota_total") int quotaTotal,
            @JsonProperty("quota_used") int quotaUsed,
            @JsonProperty("quota_remaining") int quotaRemaining,
            @JsonProperty("reset_at") OffsetDateTime resetAt
    ) {
    }

    public record UserItem(
            Long id,
            String username,
            @JsonProperty("display_name") String displayName,
            String role,
            String capabilities,
            String status,
            @JsonProperty("is_admin") boolean isAdmin,
            @JsonProperty("tenant_id") String tenantId,
            @JsonProperty("created_at") OffsetDateTime createdAt,
            QuotaResponse quota
    ) {
    }

    public record UserListResponse(
            List<UserItem> items,
            long total
    ) {
    }

    public record RoleUpdateRequest(
            @Pattern(regexp = "^(admin|tenant_admin|member)$", message = "role 仅支持 admin、tenant_admin、member")
            String role,
            String capabilities
    ) {
    }

    public record DisplayNameUpdateRequest(
            @JsonProperty("display_name")
            @Size(max = 120)
            String displayName
    ) {
    }

    public record QuotaUpdateRequest(
            @JsonProperty("quota_per_import")
            @Min(1)
            @Max(10000)
            Integer quotaPerImport,
            @JsonProperty("quota_total")
            @Min(1)
            @Max(1000000)
            Integer quotaTotal
    ) {
    }

    public record UserRoleResponse(
            Long id,
            String role
    ) {
    }

    public record UserDisplayNameResponse(
            Long id,
            @JsonProperty("display_name") String displayName
    ) {
    }
}