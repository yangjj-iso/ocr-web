package com.ocrweb.controlplane.auth.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.OffsetDateTime;

@Entity
@Table(name = "app_users")
public class AppUserEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 120)
    private String username;

    @Column(name = "password_hash", nullable = false, length = 500)
    private String passwordHash;

    @Column(nullable = false, length = 20)
    private String status = "pending";

    @Column(name = "is_admin", nullable = false)
    private boolean isAdmin = false;

    @Column(nullable = false, length = 20)
    private String role = "member";

    /** 岗位能力标签，逗号分隔，如 'operator'/'searcher'/'operator,searcher'.仅对 member 角色有意义。 */
    @Column(nullable = true, length = 100)
    private String capabilities;

    @Column(name = "display_name", length = 120)
    private String displayName;

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId = "default";

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    public Long getId() {
        return id;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public boolean isAdmin() {
        return isAdmin;
    }

    public void setAdmin(boolean admin) {
        isAdmin = admin;
    }

    public String getRole() {
        return role == null || role.isBlank() ? "member" : role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public String getCapabilities() {
        return capabilities == null ? "" : capabilities;
    }

    public void setCapabilities(String capabilities) {
        this.capabilities = (capabilities == null || capabilities.isBlank()) ? null : capabilities.strip();
    }

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = displayName;
    }

    public String getTenantId() {
        return tenantId == null || tenantId.isBlank() ? "default" : tenantId;
    }

    public void setTenantId(String tenantId) {
        this.tenantId = tenantId == null || tenantId.isBlank() ? "default" : tenantId;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}
