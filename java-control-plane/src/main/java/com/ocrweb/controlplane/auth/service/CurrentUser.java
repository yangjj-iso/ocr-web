package com.ocrweb.controlplane.auth.service;

public record CurrentUser(
        String username,
        boolean isAdmin,
        String userStatus,
        Long userId,
        String role,
        String tenantId,
        String capabilities
) {
    public static final String REQUEST_ATTRIBUTE = CurrentUser.class.getName();

    /** Backwards-compatible constructor without capabilities (defaults to ""). */
    public CurrentUser(String username, boolean isAdmin, String userStatus, Long userId, String role, String tenantId) {
        this(username, isAdmin, userStatus, userId, role, tenantId, "");
    }

    /** Backwards-compatible constructor without tenantId or capabilities. */
    public CurrentUser(String username, boolean isAdmin, String userStatus, Long userId, String role) {
        this(username, isAdmin, userStatus, userId, role, "default", "");
    }

    public String effectiveRole() {
        return role == null || role.isBlank() ? (isAdmin ? "admin" : "member") : role;
    }

    public String effectiveTenantId() {
        return tenantId == null || tenantId.isBlank() ? "default" : tenantId;
    }

    public String effectiveCapabilities() {
        return capabilities == null ? "" : capabilities;
    }

    /** Returns true if this user has the given capability tag, or is admin/tenant_admin. */
    public boolean hasCapability(String cap) {
        String r = effectiveRole();
        if ("admin".equals(r) || "tenant_admin".equals(r)) {
            return true;
        }
        String caps = effectiveCapabilities();
        for (String c : caps.split(",")) {
            if (cap.equalsIgnoreCase(c.strip())) {
                return true;
            }
        }
        return false;
    }
}
