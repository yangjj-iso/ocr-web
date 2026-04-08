package com.ocrweb.controlplane.task.dto;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.time.OffsetDateTime;
import java.util.List;

public final class TaskDtos {
    private TaskDtos() {
    }

    public record UploadFromPathRequest(@NotBlank String filePath) {
    }

    public record TaskResponse(
            Long id,
            String filename,
            String filePath,
            String fileType,
            String mode,
            String status,
            String traceId,
            Integer pageCount,
            String snippet,
            String errorMessage,
            Double progressPercent,
            OffsetDateTime createdAt,
            OffsetDateTime updatedAt
    ) {
    }

    public record TaskDetailResponse(
            Long id,
            String filename,
            String filePath,
            String fileType,
            String mode,
            String status,
            String traceId,
            Integer pageCount,
            String errorMessage,
            Double progressPercent,
            String fullText,
            JsonNode resultJson,
            JsonNode resultData,
            JsonNode agentMeta,
            JsonNode humanReviewPayload,
            String workflowThreadId,
            String reviewStatus,
            String reviewReason,
            OffsetDateTime createdAt,
            OffsetDateTime updatedAt
    ) {
    }

    public record TaskListResponse(long total, List<TaskResponse> tasks) {
    }

    public record FolderSummaryResponse(String folder, long count, OffsetDateTime lastTime, Long latestTaskId) {
    }

    public record TaskProgressRequest(@NotEmpty List<Long> taskIds) {
    }

    public record TaskProgressItem(Long id, String status, String errorMessage) {
    }

    public record TaskProgressResponse(
            int total,
            int doneCount,
            int failedCount,
            int processingCount,
            int pendingCount,
            List<TaskProgressItem> tasks
    ) {
    }

    public record CallbackWorker(String workerId, String hostname, String queue, Integer retryCount) {
    }

    public record CallbackProgress(Integer currentPage, Integer totalPages, Double percent) {
    }

    public record TaskEventRequest(
            @NotBlank String schemaVersion,
            @NotBlank String eventId,
            @NotBlank String traceId,
            @NotNull Long taskId,
            String batchId,
            @NotBlank String eventType,
            String occurredAt,
            CallbackWorker worker,
            CallbackProgress progress,
            JsonNode payload
    ) {
    }

    public record TaskCompletionRequest(
            @NotBlank String schemaVersion,
            @NotBlank String eventId,
            @NotBlank String traceId,
            @NotNull Long taskId,
            String batchId,
            String completedAt,
            CallbackWorker worker,
            JsonNode summary,
            JsonNode archiveFields,
            JsonNode qualityMetrics,
            JsonNode agentMeta,
            String fullText,
            JsonNode result,
            JsonNode resultArtifact
    ) {
    }

    public record TaskFailureRequest(
            @NotBlank String schemaVersion,
            @NotBlank String eventId,
            @NotBlank String traceId,
            @NotNull Long taskId,
            String batchId,
            String failedAt,
            CallbackWorker worker,
            CallbackProgress progress,
            JsonNode error,
            JsonNode partialResultArtifact
    ) {
    }

    public record TaskPauseRequest(
            @NotBlank String schemaVersion,
            @NotBlank String eventId,
            @NotBlank String traceId,
            @NotNull Long taskId,
            String batchId,
            String pausedAt,
            CallbackWorker worker,
            CallbackProgress progress,
            JsonNode summary,
            @NotBlank String workflowThreadId,
            String reviewStatus,
            String reviewReason,
            JsonNode interruptPayload,
            JsonNode qualityMetrics,
            JsonNode agentMeta,
            String fullText,
            JsonNode result,
            JsonNode resultArtifact
    ) {
    }

    public record HumanReviewResumeRequest(JsonNode resumePayload) {
    }

    public record TaskUpdateRequest(
            JsonNode resultJson,
            String fullText
    ) {
    }

    public record InternalCallbackResponse(boolean accepted, boolean persisted, Long taskId, String status, String serverTime) {
    }
}
