package com.ocrweb.controlplane.archive.domain;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UpdateTimestamp;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;

@Entity
@Table(name = "rework_tasks")
public class ReworkTaskEntity {

    @Id
    @Column(name = "rework_task_id", length = 160)
    private String reworkTaskId;

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId = "default";

    @Column(name = "batch_id", nullable = false, length = 120)
    private String batchId;

    @Column(name = "record_id", length = 160)
    private String recordId;

    @Column(name = "record_version")
    private Integer recordVersion = 1;

    @Column(name = "issue_type", nullable = false, length = 40)
    private String issueType = "other";

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "priority", length = 20)
    private String priority = "normal";

    @Column(name = "status", nullable = false, length = 20)
    private String status = "pending";

    @Column(name = "rework_level", length = 20)
    private String reworkLevel = "partial";

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "affected_scope_json", columnDefinition = "jsonb")
    private JsonNode affectedScopeJson;

    @Column(name = "reported_by_user_id")
    private Long reportedByUserId;

    @Column(name = "reported_by_username", length = 120)
    private String reportedByUsername;

    @Column(name = "accepted_by_user_id")
    private Long acceptedByUserId;

    @Column(name = "accepted_by_username", length = 120)
    private String acceptedByUsername;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    public String getReworkTaskId() {
        return reworkTaskId;
    }

    public void setReworkTaskId(String reworkTaskId) {
        this.reworkTaskId = reworkTaskId;
    }

    public String getTenantId() {
        return tenantId;
    }

    public void setTenantId(String tenantId) {
        this.tenantId = tenantId;
    }

    public String getBatchId() {
        return batchId;
    }

    public void setBatchId(String batchId) {
        this.batchId = batchId;
    }

    public String getRecordId() {
        return recordId;
    }

    public void setRecordId(String recordId) {
        this.recordId = recordId;
    }

    public Integer getRecordVersion() {
        return recordVersion;
    }

    public void setRecordVersion(Integer recordVersion) {
        this.recordVersion = recordVersion;
    }

    public String getIssueType() {
        return issueType;
    }

    public void setIssueType(String issueType) {
        this.issueType = issueType;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getPriority() {
        return priority;
    }

    public void setPriority(String priority) {
        this.priority = priority;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getReworkLevel() {
        return reworkLevel;
    }

    public void setReworkLevel(String reworkLevel) {
        this.reworkLevel = reworkLevel;
    }

    public JsonNode getAffectedScopeJson() {
        return affectedScopeJson;
    }

    public void setAffectedScopeJson(JsonNode affectedScopeJson) {
        this.affectedScopeJson = affectedScopeJson;
    }

    public Long getReportedByUserId() {
        return reportedByUserId;
    }

    public void setReportedByUserId(Long reportedByUserId) {
        this.reportedByUserId = reportedByUserId;
    }

    public String getReportedByUsername() {
        return reportedByUsername;
    }

    public void setReportedByUsername(String reportedByUsername) {
        this.reportedByUsername = reportedByUsername;
    }

    public Long getAcceptedByUserId() {
        return acceptedByUserId;
    }

    public void setAcceptedByUserId(Long acceptedByUserId) {
        this.acceptedByUserId = acceptedByUserId;
    }

    public String getAcceptedByUsername() {
        return acceptedByUsername;
    }

    public void setAcceptedByUsername(String acceptedByUsername) {
        this.acceptedByUsername = acceptedByUsername;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}