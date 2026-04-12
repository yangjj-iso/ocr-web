package com.ocrweb.controlplane.dev.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.ocrweb.controlplane.task.dto.TaskDtos;

import java.time.OffsetDateTime;
import java.util.List;

public final class DevDashboardDtos {
    private DevDashboardDtos() {
    }

    public record LoginRequest(String username, String password) {
    }

    public record AuthStatus(boolean configured, boolean authenticated, String username) {
    }

    public record DashboardSnapshot(
            OffsetDateTime generatedAt,
            TaskSummary tasks,
            WorkflowSummary workflow,
            List<QueueInfo> queues,
            List<TaskItem> queuedTasks,
            List<TaskItem> processingTasks,
            List<TaskItem> recentTasks,
            PythonMetrics pythonMetrics
    ) {
    }

    public record TaskSummary(
            long total,
            long done,
            long processing,
            long failed,
            long pending,
            long humanReview,
            List<StatusCount> byStatus,
            List<ModeStatusCount> byMode
    ) {
    }

    public record StatusCount(String status, long count) {
    }

    public record ModeStatusCount(String mode, String status, long count) {
    }

    public record WorkflowSummary(
            long averageCompletedDurationMs,
            long averageTerminalDurationMs,
            long p50CompletedDurationMs,
            long p95CompletedDurationMs,
            int completedSampleCount,
            int terminalSampleCount,
            long averageEventDurationMs,
            int eventSampleCount,
            List<ModeDuration> byMode
    ) {
    }

    public record ModeDuration(String mode, long averageCompletedDurationMs, int sampleCount) {
    }

    public record QueueInfo(
            String name,
            long messageCount,
            long consumerCount,
            boolean available,
            String detail
    ) {
    }

    public record TaskItem(
            Long id,
            String filename,
            String filePath,
            String mode,
            String status,
            String batchId,
            String traceId,
            Double progressPercent,
            String submitterUsername,
            Integer pageCount,
            String errorMessage,
            String workflowThreadId,
            long ageSeconds,
            OffsetDateTime createdAt,
            OffsetDateTime updatedAt
    ) {
    }

    public record PythonMetrics(boolean available, String detail, JsonNode payload) {
    }

    public record TaskInspector(
            TaskDtos.TaskDetailResponse task,
            TaskDtos.WorkflowEventsResponse workflowEvents
    ) {
    }

    public record RuntimeEnvironmentSnapshot(
            String envFilePath,
            OffsetDateTime generatedAt,
            List<EnvironmentGroup> groups
    ) {
    }

    public record EnvironmentGroup(
            String key,
            String label,
            String description,
            List<EnvironmentField> fields
    ) {
    }

    public record EnvironmentField(
            String key,
            String label,
            String description,
            String type,
            boolean sensitive,
            boolean configured,
            boolean runtimeApplied,
            String value,
            String placeholder
    ) {
    }

    public record EnvironmentUpdateRequest(List<EnvironmentValueUpdate> values) {
    }

    public record EnvironmentValueUpdate(String key, String value) {
    }
}
