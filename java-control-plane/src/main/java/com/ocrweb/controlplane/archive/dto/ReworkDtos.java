package com.ocrweb.controlplane.archive.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

import java.time.OffsetDateTime;
import java.util.List;

public final class ReworkDtos {
    private ReworkDtos() {
    }

    public record ReworkTaskResponse(
            String id,
            @JsonProperty("rework_task_id") String reworkTaskId,
            @JsonProperty("record_id") String recordId,
            @JsonProperty("batch_id") String batchId,
            @JsonProperty("issue_type") String issueType,
            String priority,
            String status,
            @JsonProperty("created_at") OffsetDateTime createdAt,
            String description,
            @JsonProperty("reported_by") String reportedBy,
            @JsonProperty("affected_scope") JsonNode affectedScope
    ) {
    }

    public record ReworkTaskListResponse(long total, List<ReworkTaskResponse> items) {
    }

    public record ReworkCreateRequest(
            @JsonAlias("record_id") String recordId,
            @JsonAlias("batch_id") String batchId,
            @JsonAlias("record_version") Integer recordVersion,
            @JsonAlias("issue_type") String issueType,
            String description,
            String priority,
            @JsonAlias("rework_level") String reworkLevel,
            @JsonAlias("affected_scope") JsonNode affectedScope
    ) {
    }

    public record ReworkStatusResponse(
            String id,
            String status,
            @JsonProperty("batch_id") String batchId
    ) {
    }

    public record RejectReasonRequest(String reason) {
    }
}