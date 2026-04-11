package com.ocrweb.controlplane.auth.service;

public record CurrentUser(
        String username,
        boolean isAdmin,
        String userStatus,
        Long userId,
        String role
) {
    public static final String REQUEST_ATTRIBUTE = CurrentUser.class.getName();

    public String effectiveRole() {
        return role == null || role.isBlank() ? (isAdmin ? "admin" : "operator") : role;
    }
}
