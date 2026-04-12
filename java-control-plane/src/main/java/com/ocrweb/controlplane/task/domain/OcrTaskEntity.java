package com.ocrweb.controlplane.task.domain;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UpdateTimestamp;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;

@Entity
@Table(name = "ocr_tasks")
public class OcrTaskEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 255)
    private String filename;

    @Column(name = "file_path", nullable = false, length = 500)
    private String filePath;

    @Column(name = "file_type", nullable = false, length = 20)
    private String fileType;

    @Column(name = "storage_provider", length = 32)
    private String storageProvider = "s3";

    @Column(name = "storage_bucket", length = 255)
    private String storageBucket;

    @Column(name = "storage_object_key", length = 700)
    private String storageObjectKey;

    @Column(name = "file_sha256", length = 64)
    private String fileSha256;

    @Column(name = "file_size_bytes")
    private Long fileSizeBytes = 0L;

    @Column(nullable = false, length = 20)
    private String mode;

    @Column(nullable = false, length = 32)
    private String status = "pending";

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "result_json", columnDefinition = "jsonb")
    private JsonNode resultJson;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "agent_meta", columnDefinition = "jsonb")
    private JsonNode agentMeta;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "human_review_payload", columnDefinition = "jsonb")
    private JsonNode humanReviewPayload;

    @Column(name = "full_text", columnDefinition = "TEXT")
    private String fullText;

    @Column(name = "page_count")
    private Integer pageCount = 0;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "batch_id", length = 120)
    private String batchId;

    @Column(name = "submitter_username", length = 120)
    private String submitterUsername;

    @Column(name = "submission_name", length = 255)
    private String submissionName;

    @Column(name = "trace_id", length = 120)
    private String traceId;

    @Column(name = "progress_percent")
    private Double progressPercent = 0.0;

    @Column(name = "processed_pages")
    private Integer processedPages = 0;

    @Column(name = "total_pages")
    private Integer totalPages = 0;

    @Column(name = "review_status", length = 50)
    private String reviewStatus;

    @Column(name = "review_reason", columnDefinition = "TEXT")
    private String reviewReason;

    @Column(name = "workflow_thread_id", length = 160)
    private String workflowThreadId;

    @Column(name = "assignee_username", length = 120)
    private String assigneeUsername;

    @CreationTimestamp
    @Column(name = "created_at", updatable = false)
    private OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at")
    private OffsetDateTime updatedAt;

    public Long getId() {
        return id;
    }

    public String getFilename() {
        return filename;
    }

    public void setFilename(String filename) {
        this.filename = filename;
    }

    public String getFilePath() {
        return filePath;
    }

    public void setFilePath(String filePath) {
        this.filePath = filePath;
    }

    public String getFileType() {
        return fileType;
    }

    public void setFileType(String fileType) {
        this.fileType = fileType;
    }

    public String getStorageProvider() {
        return storageProvider;
    }

    public void setStorageProvider(String storageProvider) {
        this.storageProvider = storageProvider;
    }

    public String getStorageBucket() {
        return storageBucket;
    }

    public void setStorageBucket(String storageBucket) {
        this.storageBucket = storageBucket;
    }

    public String getStorageObjectKey() {
        return storageObjectKey;
    }

    public void setStorageObjectKey(String storageObjectKey) {
        this.storageObjectKey = storageObjectKey;
    }

    public String getFileSha256() {
        return fileSha256;
    }

    public void setFileSha256(String fileSha256) {
        this.fileSha256 = fileSha256;
    }

    public Long getFileSizeBytes() {
        return fileSizeBytes;
    }

    public void setFileSizeBytes(Long fileSizeBytes) {
        this.fileSizeBytes = fileSizeBytes;
    }

    public String getMode() {
        return mode;
    }

    public void setMode(String mode) {
        this.mode = mode;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public JsonNode getResultJson() {
        return resultJson;
    }

    public void setResultJson(JsonNode resultJson) {
        this.resultJson = resultJson;
    }

    public JsonNode getAgentMeta() {
        return agentMeta;
    }

    public void setAgentMeta(JsonNode agentMeta) {
        this.agentMeta = agentMeta;
    }

    public JsonNode getHumanReviewPayload() {
        return humanReviewPayload;
    }

    public void setHumanReviewPayload(JsonNode humanReviewPayload) {
        this.humanReviewPayload = humanReviewPayload;
    }

    public String getFullText() {
        return fullText;
    }

    public void setFullText(String fullText) {
        this.fullText = fullText;
    }

    public Integer getPageCount() {
        return pageCount;
    }

    public void setPageCount(Integer pageCount) {
        this.pageCount = pageCount;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    public String getBatchId() {
        return batchId;
    }

    public void setBatchId(String batchId) {
        this.batchId = batchId;
    }

    public String getTraceId() {
        return traceId;
    }

    public String getSubmitterUsername() {
        return submitterUsername;
    }

    public void setSubmitterUsername(String submitterUsername) {
        this.submitterUsername = submitterUsername;
    }

    public String getSubmissionName() {
        return submissionName;
    }

    public void setSubmissionName(String submissionName) {
        this.submissionName = submissionName;
    }

    public void setTraceId(String traceId) {
        this.traceId = traceId;
    }

    public Double getProgressPercent() {
        return progressPercent;
    }

    public void setProgressPercent(Double progressPercent) {
        this.progressPercent = progressPercent;
    }

    public Integer getProcessedPages() {
        return processedPages;
    }

    public void setProcessedPages(Integer processedPages) {
        this.processedPages = processedPages;
    }

    public Integer getTotalPages() {
        return totalPages;
    }

    public void setTotalPages(Integer totalPages) {
        this.totalPages = totalPages;
    }

    public String getReviewStatus() {
        return reviewStatus;
    }

    public void setReviewStatus(String reviewStatus) {
        this.reviewStatus = reviewStatus;
    }

    public String getReviewReason() {
        return reviewReason;
    }

    public void setReviewReason(String reviewReason) {
        this.reviewReason = reviewReason;
    }

    public String getWorkflowThreadId() {
        return workflowThreadId;
    }

    public void setWorkflowThreadId(String workflowThreadId) {
        this.workflowThreadId = workflowThreadId;
    }

    public String getAssigneeUsername() {
        return assigneeUsername;
    }

    public void setAssigneeUsername(String assigneeUsername) {
        this.assigneeUsername = assigneeUsername;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getUpdatedAt() {
        return updatedAt;
    }
}
