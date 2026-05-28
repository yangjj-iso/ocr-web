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

    public record RegisterRequest(
            @NotBlank @Size(min = 3, max = 120) String username,
            @NotBlank @Size(min = 6, max = 200) String password
    ) {
    }

    public record AuthStatusResponse(
            boolean enabled,
            boolean authenticated,
            String username,
            boolean isAdmin,
            String userStatus,
            String defaultUsername
    ) {
    }

    public record LoginResponse(
            boolean authenticated,
            String username,
            boolean isAdmin,
            String userStatus
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

    public record UserItem(
            Long id,
            String username,
            String status,
            boolean isAdmin,
            OffsetDateTime createdAt
    ) {
    }

    public record AllUsersResponse(List<UserItem> items) {
    }

    public record SetAdminRequest(boolean admin) {
    }
}
