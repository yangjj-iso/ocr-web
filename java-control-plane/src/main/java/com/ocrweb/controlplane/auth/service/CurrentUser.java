package com.ocrweb.controlplane.auth.service;

public record CurrentUser(
        String username,
        boolean isAdmin,
        String userStatus,
        Long userId
) {
    public static final String REQUEST_ATTRIBUTE = CurrentUser.class.getName();
}
