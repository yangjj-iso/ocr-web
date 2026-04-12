package com.ocrweb.controlplane.auth.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.OffsetDateTime;

@Entity
@Table(name = "user_quotas")
public class UserQuotaEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, unique = true)
    private Long userId;

    @Column(name = "quota_per_import", nullable = false)
    private Integer quotaPerImport = 200;

    @Column(name = "quota_total", nullable = false)
    private Integer quotaTotal = 2000;

    @Column(name = "quota_used", nullable = false)
    private Integer quotaUsed = 0;

    @Column(name = "reset_at")
    private OffsetDateTime resetAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    public Long getId() {
        return id;
    }

    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public Integer getQuotaPerImport() {
        return quotaPerImport == null ? 200 : quotaPerImport;
    }

    public void setQuotaPerImport(Integer quotaPerImport) {
        this.quotaPerImport = quotaPerImport;
    }

    public Integer getQuotaTotal() {
        return quotaTotal == null ? 2000 : quotaTotal;
    }

    public void setQuotaTotal(Integer quotaTotal) {
        this.quotaTotal = quotaTotal;
    }

    public Integer getQuotaUsed() {
        return quotaUsed == null ? 0 : quotaUsed;
    }

    public void setQuotaUsed(Integer quotaUsed) {
        this.quotaUsed = quotaUsed;
    }

    public OffsetDateTime getResetAt() {
        return resetAt;
    }

    public void setResetAt(OffsetDateTime resetAt) {
        this.resetAt = resetAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}
