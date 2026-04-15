package com.ocrweb.controlplane.tenant.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;
import java.util.List;

public final class TenantDtos {
    private TenantDtos() {
    }

    public record TenantCreateRequest(
            @NotBlank
            @Size(min = 2, max = 64)
            @Pattern(regexp = "^[a-z0-9_-]{2,64}$", message = "tenant id 只允许小写字母、数字、下划线和横线，长度 2-64")
            String id,
            @NotBlank
            @Size(min = 1, max = 120)
            String name
    ) {
    }

    public record TenantUpdateRequest(
            @Size(min = 1, max = 120)
            String name,
            @Pattern(regexp = "^(active|disabled)$", message = "status 仅支持 active 或 disabled")
            String status
    ) {
    }

    public record AssignUserRequest(
            @NotNull
            Long userId
    ) {
    }

    public record TenantItem(
            String id,
            String name,
            String status,
            OffsetDateTime createdAt,
            long userCount
    ) {
    }

    public record TenantListResponse(
            List<TenantItem> items,
            long total
    ) {
    }

    public record TenantResponse(
            String id,
            String name,
            String status
    ) {
    }

    public record PublicTenantItem(
            String id,
            String name
    ) {
    }

    public record PublicTenantListResponse(
            List<PublicTenantItem> items
    ) {
    }

    public record AssignUserResponse(
            boolean ok,
            Long userId,
            String tenantId
    ) {
    }
}