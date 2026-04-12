package com.ocrweb.controlplane.dev.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.config.AiServiceProperties;
import com.ocrweb.controlplane.config.DevDashboardProperties;
import com.ocrweb.controlplane.config.InternalApiProperties;
import com.ocrweb.controlplane.config.RabbitMqProperties;
import com.ocrweb.controlplane.dev.dto.DevDashboardDtos;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.domain.TaskCallbackEventEntity;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import com.ocrweb.controlplane.task.repository.TaskCallbackEventRepository;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Properties;

@Service
public class DevDashboardService {
    private static final List<String> DONE_STATUSES = List.of("done", "completed");
    private static final List<String> TERMINAL_STATUSES = List.of("done", "completed", "failed", "human_review");
    private static final List<String> PENDING_STATUSES = List.of("pending", "queued");
    private static final List<String> PROCESSING_STATUSES = List.of("processing", "running", "worker_accepted");

    private final OcrTaskRepository taskRepository;
    private final TaskCallbackEventRepository callbackEventRepository;
    private final RabbitMqProperties rabbitMqProperties;
    private final DevDashboardProperties devDashboardProperties;
    private final AiServiceProperties aiServiceProperties;
    private final InternalApiProperties internalApiProperties;
    private final RabbitAdmin rabbitAdmin;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;

    public DevDashboardService(
            OcrTaskRepository taskRepository,
            TaskCallbackEventRepository callbackEventRepository,
            RabbitMqProperties rabbitMqProperties,
            DevDashboardProperties devDashboardProperties,
            AiServiceProperties aiServiceProperties,
            InternalApiProperties internalApiProperties,
            ConnectionFactory connectionFactory,
            ObjectMapper objectMapper
    ) {
        this.taskRepository = taskRepository;
        this.callbackEventRepository = callbackEventRepository;
        this.rabbitMqProperties = rabbitMqProperties;
        this.devDashboardProperties = devDashboardProperties;
        this.aiServiceProperties = aiServiceProperties;
        this.internalApiProperties = internalApiProperties;
        this.rabbitAdmin = new RabbitAdmin(connectionFactory);
        this.objectMapper = objectMapper;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(Math.max(1, aiServiceProperties.getConnectTimeoutSeconds())))
                .build();
    }

    public DevDashboardDtos.DashboardSnapshot snapshot() {
        List<OcrTaskEntity> tasks = taskRepository.findAll();
        TaskAggregation aggregation = aggregateTasks(tasks);
        return new DevDashboardDtos.DashboardSnapshot(
                OffsetDateTime.now(ZoneOffset.UTC),
                aggregation.taskSummary(),
                aggregation.workflowSummary(),
                inspectQueues(),
                aggregation.queuedTasks(),
                aggregation.processingTasks(),
                fetchPythonMetrics()
        );
    }

    private TaskAggregation aggregateTasks(List<OcrTaskEntity> tasks) {
        Map<String, Long> statusCounts = new LinkedHashMap<>();
        Map<String, Long> modeStatusCounts = new LinkedHashMap<>();
        Map<String, List<Long>> modeDurations = new LinkedHashMap<>();
        List<Long> completedDurations = new ArrayList<>();
        List<Long> terminalDurations = new ArrayList<>();
        List<DevDashboardDtos.TaskItem> queuedTasks = new ArrayList<>();
        List<DevDashboardDtos.TaskItem> processingTasks = new ArrayList<>();
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);

        for (OcrTaskEntity task : tasks) {
            String status = normalizeStatus(task.getStatus());
            String mode = normalizeValue(task.getMode(), "unknown");
            statusCounts.merge(status, 1L, Long::sum);
            modeStatusCounts.merge(mode + "\u0000" + status, 1L, Long::sum);

            Long durationMs = taskDurationMs(task);
            if (durationMs != null && DONE_STATUSES.contains(status)) {
                completedDurations.add(durationMs);
                modeDurations.computeIfAbsent(mode, key -> new ArrayList<>()).add(durationMs);
            }
            if (durationMs != null && TERMINAL_STATUSES.contains(status)) {
                terminalDurations.add(durationMs);
            }

            if (PENDING_STATUSES.contains(status)) {
                queuedTasks.add(toTaskItem(task, status, secondsSince(task.getCreatedAt(), now)));
            } else if (PROCESSING_STATUSES.contains(status)) {
                processingTasks.add(toTaskItem(task, status, secondsSince(
                        task.getUpdatedAt() == null ? task.getCreatedAt() : task.getUpdatedAt(),
                        now
                )));
            }
        }

        queuedTasks.sort(Comparator.comparing(DevDashboardDtos.TaskItem::createdAt, Comparator.nullsLast(Comparator.naturalOrder())));
        processingTasks.sort(Comparator.comparing(DevDashboardDtos.TaskItem::updatedAt, Comparator.nullsLast(Comparator.reverseOrder())));
        List<Long> eventDurations = callbackEventRepository.findAll()
                .stream()
                .map(this::eventDurationMs)
                .filter(value -> value != null && value >= 0)
                .toList();

        List<DevDashboardDtos.StatusCount> byStatus = statusCounts.entrySet()
                .stream()
                .sorted(Map.Entry.comparingByKey())
                .map(entry -> new DevDashboardDtos.StatusCount(entry.getKey(), entry.getValue()))
                .toList();
        List<DevDashboardDtos.ModeStatusCount> byMode = modeStatusCounts.entrySet()
                .stream()
                .sorted(Map.Entry.comparingByKey())
                .map(entry -> {
                    String[] parts = entry.getKey().split("\u0000", 2);
                    return new DevDashboardDtos.ModeStatusCount(parts[0], parts.length > 1 ? parts[1] : "", entry.getValue());
                })
                .toList();

        DevDashboardDtos.TaskSummary taskSummary = new DevDashboardDtos.TaskSummary(
                tasks.size(),
                sumStatuses(statusCounts, DONE_STATUSES),
                sumStatuses(statusCounts, PROCESSING_STATUSES),
                statusCounts.getOrDefault("failed", 0L),
                sumStatuses(statusCounts, PENDING_STATUSES),
                statusCounts.getOrDefault("human_review", 0L),
                byStatus,
                byMode
        );
        DevDashboardDtos.WorkflowSummary workflowSummary = new DevDashboardDtos.WorkflowSummary(
                average(completedDurations),
                average(terminalDurations),
                percentile(completedDurations, 50),
                percentile(completedDurations, 95),
                completedDurations.size(),
                terminalDurations.size(),
                average(eventDurations),
                eventDurations.size(),
                modeDurations.entrySet()
                        .stream()
                        .sorted(Map.Entry.comparingByKey())
                        .map(entry -> new DevDashboardDtos.ModeDuration(entry.getKey(), average(entry.getValue()), entry.getValue().size()))
                        .toList()
        );
        return new TaskAggregation(
                taskSummary,
                workflowSummary,
                queuedTasks.stream().limit(50).toList(),
                processingTasks.stream().limit(50).toList()
        );
    }

    private List<DevDashboardDtos.QueueInfo> inspectQueues() {
        List<String> queues = distinctQueues(
                rabbitMqProperties.getQueue(),
                rabbitMqProperties.getDeadLetterQueue(),
                devDashboardProperties.getCeleryQueue()
        );
        List<DevDashboardDtos.QueueInfo> results = new ArrayList<>();
        for (String queue : queues) {
            try {
                Properties properties = rabbitAdmin.getQueueProperties(queue);
                if (properties == null) {
                    results.add(new DevDashboardDtos.QueueInfo(queue, 0, 0, false, "Queue not found."));
                    continue;
                }
                long messageCount = asLong(properties.get(RabbitAdmin.QUEUE_MESSAGE_COUNT));
                long consumerCount = asLong(properties.get(RabbitAdmin.QUEUE_CONSUMER_COUNT));
                results.add(new DevDashboardDtos.QueueInfo(queue, messageCount, consumerCount, true, "ok"));
            } catch (Exception error) {
                results.add(new DevDashboardDtos.QueueInfo(queue, 0, 0, false, error.getMessage()));
            }
        }
        return results;
    }

    private DevDashboardDtos.PythonMetrics fetchPythonMetrics() {
        if (!StringUtils.hasText(aiServiceProperties.getBaseUrl())) {
            return new DevDashboardDtos.PythonMetrics(false, "Python AI base URL is not configured.", objectMapper.createObjectNode());
        }
        if (!StringUtils.hasText(internalApiProperties.getToken())) {
            return new DevDashboardDtos.PythonMetrics(false, "Internal API token is not configured.", objectMapper.createObjectNode());
        }
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(joinUrl(aiServiceProperties.getBaseUrl(), devDashboardProperties.getPythonMetricsPath())))
                    .timeout(Duration.ofSeconds(Math.max(1, Math.min(aiServiceProperties.getReadTimeoutSeconds(), 5))))
                    .header("Authorization", "Bearer " + internalApiProperties.getToken())
                    .GET()
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                return new DevDashboardDtos.PythonMetrics(
                        false,
                        "Python metrics returned HTTP " + response.statusCode(),
                        objectMapper.createObjectNode()
                );
            }
            JsonNode payload = objectMapper.readTree(response.body());
            return new DevDashboardDtos.PythonMetrics(true, "ok", payload);
        } catch (Exception error) {
            return new DevDashboardDtos.PythonMetrics(false, error.getMessage(), objectMapper.createObjectNode());
        }
    }

    private Long eventDurationMs(TaskCallbackEventEntity event) {
        if (event == null || event.getPayloadJson() == null) {
            return null;
        }
        JsonNode summary = event.getPayloadJson().path("summary");
        if (summary.isMissingNode() || summary.isNull()) {
            return null;
        }
        JsonNode duration = summary.has("duration_ms") ? summary.get("duration_ms") : summary.get("durationMs");
        return duration == null || !duration.canConvertToLong() ? null : duration.asLong();
    }

    private DevDashboardDtos.TaskItem toTaskItem(OcrTaskEntity task, String status, long ageSeconds) {
        return new DevDashboardDtos.TaskItem(
                task.getId(),
                normalizeValue(task.getFilename(), ""),
                normalizeValue(task.getMode(), ""),
                status,
                normalizeValue(task.getBatchId(), ""),
                normalizeValue(task.getTraceId(), ""),
                task.getProgressPercent() == null ? 0.0 : task.getProgressPercent(),
                normalizeValue(task.getSubmitterUsername(), ""),
                ageSeconds,
                task.getCreatedAt(),
                task.getUpdatedAt()
        );
    }

    private Long taskDurationMs(OcrTaskEntity task) {
        if (task.getCreatedAt() == null || task.getUpdatedAt() == null || task.getUpdatedAt().isBefore(task.getCreatedAt())) {
            return null;
        }
        return Duration.between(task.getCreatedAt(), task.getUpdatedAt()).toMillis();
    }

    private static long sumStatuses(Map<String, Long> statusCounts, List<String> statuses) {
        long total = 0;
        for (String status : statuses) {
            total += statusCounts.getOrDefault(status, 0L);
        }
        return total;
    }

    private static String normalizeStatus(String rawStatus) {
        String status = normalizeValue(rawStatus, "pending").toLowerCase(Locale.ROOT);
        return switch (status) {
            case "queued" -> "pending";
            case "worker_accepted", "running" -> "processing";
            case "completed" -> "done";
            default -> status;
        };
    }

    private static String normalizeValue(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private static long secondsSince(OffsetDateTime startedAt, OffsetDateTime now) {
        if (startedAt == null || startedAt.isAfter(now)) {
            return 0;
        }
        return Duration.between(startedAt, now).toSeconds();
    }

    private static long average(List<Long> values) {
        if (values == null || values.isEmpty()) {
            return 0;
        }
        long total = 0;
        for (Long value : values) {
            total += value;
        }
        return Math.round((double) total / values.size());
    }

    private static long percentile(List<Long> values, int percentile) {
        if (values == null || values.isEmpty()) {
            return 0;
        }
        List<Long> sorted = values.stream().sorted().toList();
        if (sorted.size() == 1) {
            return sorted.get(0);
        }
        int index = Math.round((percentile / 100.0f) * (sorted.size() - 1));
        return sorted.get(Math.max(0, Math.min(index, sorted.size() - 1)));
    }

    private static List<String> distinctQueues(String... values) {
        List<String> result = new ArrayList<>();
        for (String value : values) {
            if (!StringUtils.hasText(value) || result.contains(value.trim())) {
                continue;
            }
            result.add(value.trim());
        }
        return result;
    }

    private static long asLong(Object value) {
        if (value instanceof Number number) {
            return number.longValue();
        }
        if (value == null) {
            return 0;
        }
        try {
            return Long.parseLong(String.valueOf(value));
        } catch (NumberFormatException error) {
            return 0;
        }
    }

    private static String joinUrl(String baseUrl, String path) {
        String normalizedBase = baseUrl == null ? "" : baseUrl.replaceAll("/+$", "");
        String normalizedPath = path == null ? "" : path.trim();
        if (!normalizedPath.startsWith("/")) {
            normalizedPath = "/" + normalizedPath;
        }
        return normalizedBase + normalizedPath;
    }

    private record TaskAggregation(
            DevDashboardDtos.TaskSummary taskSummary,
            DevDashboardDtos.WorkflowSummary workflowSummary,
            List<DevDashboardDtos.TaskItem> queuedTasks,
            List<DevDashboardDtos.TaskItem> processingTasks
    ) {
    }
}
