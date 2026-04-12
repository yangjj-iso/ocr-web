package com.ocrweb.controlplane.dev.dto;

import com.fasterxml.jackson.annotation.JsonAlias;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

public final class DevDashboardDtos {
    private DevDashboardDtos() {
    }

    public record LoginRequest(String username, String password, @JsonAlias({"two_factor_code", "twoFactorCode"}) String twoFactorCode) {
    }

    public record LoginResponse(boolean authenticated, String username, Instant expiresAt) {
    }

    public record AuthStatusResponse(boolean enabled, boolean authenticated, String username, Instant expiresAt) {
    }

    public record SnapshotResponse(
            Instant generatedAt,
            InfraMetrics infra,
            List<QueueMetric> queues,
            List<MiddlewareMetric> middleware,
            List<ModelMetric> models,
            List<TaskItem> tasks
    ) {
    }

    public record InfraMetrics(
            double qps,
            long recentRequests,
            long mqBacklog,
            int mqConsumers,
            double ackRate,
            long activeTasks,
            long totalUsers,
            int cpuPercent,
            int gpuPercent,
            int memoryPercent,
            int gpuMemoryPercent,
            String workerStatus,
            String cleanupNote
    ) {
    }

    public record QueueMetric(String name, long messages, long ready, long unacked, double ackRate, int consumers) {
    }

    public record MiddlewareMetric(
            String id,
            String name,
            String status,
            String summary,
            List<MetricPair> metrics,
            String detail
    ) {
    }

    public record MetricPair(String label, String value) {
    }

    public record ModelMetric(String name, long avgMs, long p95Ms, String gpuMemory) {
    }

    public record TaskItem(
            String id,
            String status,
            String mode,
            long durationMs,
            int retries,
            String worker,
            String fileName,
            String previewUrl,
            String errorMessage,
            List<StageMetric> stages,
            List<TaskEvent> events,
            Map<String, Object> raw
    ) {
    }

    public record StageMetric(String key, String label, long durationMs, String color) {
    }

    public record TaskEvent(String at, String name, String detail) {
    }

    public record RetryResponse(boolean ok, Long taskId, String status, String message) {
    }

    public record Session(String username, Instant expiresAt) {
    }

    public record TaskRuntimeView(
            Long id,
            String status,
            String mode,
            OffsetDateTime createdAt,
            OffsetDateTime updatedAt
    ) {
    }
}
