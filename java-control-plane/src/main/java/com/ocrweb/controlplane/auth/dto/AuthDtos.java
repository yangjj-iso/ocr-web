package com.ocrweb.controlplane.auth.dto;

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
            @NotBlank String currentPassword,
            @NotBlank @Size(min = 6, max = 200) String newPassword
    ) {
    }

    public record UpdateDisplayNameRequest(String displayName) {
    }

    public record RegisterRequest(
            @NotBlank @Size(min = 2, max = 60) String realName,
            @NotBlank @Size(min = 2, max = 60) String username,
            @NotBlank @Size(min = 6, max = 200) String password,
            String requestedRole
    ) {
    }

    public record ResetPasswordRequest(
            @NotBlank @Size(min = 6, max = 200) String newPassword
    ) {
    }

    public record AuthStatusResponse(
            boolean enabled,
            boolean authenticated,
            String username,
            boolean isAdmin,
            String userStatus,
            String defaultUsername,
            String role,
            String displayName
    ) {
    }

    public record LoginResponse(
            boolean authenticated,
            String username,
            boolean isAdmin,
            String userStatus,
            String role
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
            String displayName,
            String role,
            String status,
            OffsetDateTime createdAt
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
