package com.ocrweb.controlplane.auth.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.time.OffsetDateTime;
import java.util.List;

public final class AuthDtos {
    private AuthDtos() {
    }

    public record LoginRequest(String username, String password) {
    }

    public record ChangePasswordRequest(
            @JsonProperty("current_password") @NotBlank String currentPassword,
            @JsonProperty("new_password") @NotBlank @Size(min = 6, max = 200) String newPassword
    ) {
    }

    public record UpdateDisplayNameRequest(@JsonProperty("display_name") String displayName) {
    }

    public record RegisterRequest(
            @JsonProperty("real_name") @NotBlank @Size(min = 2, max = 60) String realName,
            @NotBlank @Size(min = 2, max = 60) String username,
            @NotBlank @Size(min = 6, max = 200) String password,
            @JsonProperty("requested_role") String requestedRole,
            @JsonProperty("requested_capabilities") String requestedCapabilities,
            @JsonProperty("tenant_id") String tenantId
    ) {
    }

    public record ResetPasswordRequest(
            @JsonProperty("new_password") @NotBlank @Size(min = 6, max = 200) String newPassword
    ) {
    }

    public record AuthStatusResponse(
            boolean enabled,
            boolean authenticated,
            String username,
            @JsonProperty("is_admin") boolean isAdmin,
            @JsonProperty("user_status") String userStatus,
            @JsonProperty("default_username") String defaultUsername,
            String role,
            @JsonProperty("display_name") String displayName,
            String capabilities
    ) {
    }

    public record LoginResponse(
            boolean authenticated,
            String username,
            @JsonProperty("is_admin") boolean isAdmin,
            @JsonProperty("user_status") String userStatus,
            String role,
            String capabilities
    ) {
    }

    public record RegisterResponse(
            boolean registered,
            String status,
            String message
    ) {
    }

    public record PendingUserItem(
            Long id,
            String username,
            @JsonProperty("display_name") String displayName,
            String role,
            String capabilities,
            String status,
            @JsonProperty("created_at") OffsetDateTime createdAt
    ) {
    }

    public record PendingUsersResponse(List<PendingUserItem> items) {
    }

    public record UserStatusResponse(
            Long id,
            String username,
            String status
    ) {
    }
}
