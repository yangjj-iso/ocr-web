package com.ocrweb.controlplane.dev.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.config.AiServiceProperties;
import com.ocrweb.controlplane.config.DevDashboardProperties;
import com.ocrweb.controlplane.config.InternalApiProperties;
import com.ocrweb.controlplane.config.RabbitMqProperties;
import com.ocrweb.controlplane.config.StorageProperties;
import com.ocrweb.controlplane.dev.dto.DevDashboardDtos;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.domain.TaskCallbackEventEntity;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import com.ocrweb.controlplane.task.repository.TaskCallbackEventRepository;
import com.ocrweb.controlplane.task.service.OcrTaskService;
import com.ocrweb.controlplane.task.service.TaskStorageService;
import org.springframework.amqp.rabbit.connection.Connection;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitAdmin;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import javax.net.SocketFactory;
import javax.net.ssl.SSLSocketFactory;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
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
    private final StorageProperties storageProperties;
    private final OcrTaskService ocrTaskService;
    private final TaskStorageService taskStorageService;
    private final ConnectionFactory connectionFactory;
    private final RabbitAdmin rabbitAdmin;
    private final ObjectMapper objectMapper;
    private final Environment environment;

    public DevDashboardService(
            OcrTaskRepository taskRepository,
            TaskCallbackEventRepository callbackEventRepository,
            RabbitMqProperties rabbitMqProperties,
            DevDashboardProperties devDashboardProperties,
            AiServiceProperties aiServiceProperties,
            InternalApiProperties internalApiProperties,
            StorageProperties storageProperties,
            OcrTaskService ocrTaskService,
            TaskStorageService taskStorageService,
            ConnectionFactory connectionFactory,
            ObjectMapper objectMapper,
            Environment environment
    ) {
        this.taskRepository = taskRepository;
        this.callbackEventRepository = callbackEventRepository;
        this.rabbitMqProperties = rabbitMqProperties;
        this.devDashboardProperties = devDashboardProperties;
        this.aiServiceProperties = aiServiceProperties;
        this.internalApiProperties = internalApiProperties;
        this.storageProperties = storageProperties;
        this.ocrTaskService = ocrTaskService;
        this.taskStorageService = taskStorageService;
        this.connectionFactory = connectionFactory;
        this.rabbitAdmin = new RabbitAdmin(connectionFactory);
        this.objectMapper = objectMapper;
        this.environment = environment;
    }

    public DevDashboardDtos.DashboardSnapshot snapshot() {
        List<OcrTaskEntity> tasks = taskRepository.findAll();
        TaskAggregation aggregation = aggregateTasks(tasks);
        List<DevDashboardDtos.QueueInfo> queues = inspectQueues();
        DevDashboardDtos.PythonMetrics pythonMetrics = fetchPythonMetrics();
        return new DevDashboardDtos.DashboardSnapshot(
                OffsetDateTime.now(ZoneOffset.UTC),
                aggregation.taskSummary(),
                aggregation.workflowSummary(),
                queues,
                inspectResources(queues, pythonMetrics),
                aggregation.queuedTasks(),
                aggregation.processingTasks(),
                aggregation.recentTasks(),
                pythonMetrics
        );
    }

    public DevDashboardDtos.TaskInspector inspectTask(Long taskId) {
        return new DevDashboardDtos.TaskInspector(
                ocrTaskService.getTask(taskId),
                ocrTaskService.getWorkflowEvents(taskId)
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
        List<DevDashboardDtos.TaskItem> recentTasks = new ArrayList<>();
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
            recentTasks.add(toTaskItem(task, status, secondsSince(
                    task.getUpdatedAt() == null ? task.getCreatedAt() : task.getUpdatedAt(),
                    now
            )));
        }

        queuedTasks.sort(Comparator.comparing(DevDashboardDtos.TaskItem::createdAt, Comparator.nullsLast(Comparator.naturalOrder())));
        processingTasks.sort(Comparator.comparing(DevDashboardDtos.TaskItem::updatedAt, Comparator.nullsLast(Comparator.reverseOrder())));
        recentTasks.sort(Comparator.comparing(DevDashboardDtos.TaskItem::updatedAt, Comparator.nullsLast(Comparator.reverseOrder())));
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
                processingTasks.stream().limit(50).toList(),
                recentTasks.stream().limit(24).toList()
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

    private List<DevDashboardDtos.ResourceStatus> inspectResources(
            List<DevDashboardDtos.QueueInfo> queues,
            DevDashboardDtos.PythonMetrics pythonMetrics
    ) {
        return List.of(
                inspectRabbitMq(queues),
                inspectRedis(),
                inspectStorage(),
                inspectAiService(pythonMetrics),
                inspectLayoutApi(),
                inspectLlmApi(),
                inspectBaiduVisionApi()
        );
    }

    private DevDashboardDtos.ResourceStatus inspectRabbitMq(List<DevDashboardDtos.QueueInfo> queues) {
        long start = System.nanoTime();
        long backlog = queues.stream().mapToLong(DevDashboardDtos.QueueInfo::messageCount).sum();
        long queueCount = queues.size();
        long healthyQueueCount = queues.stream().filter(DevDashboardDtos.QueueInfo::available).count();
        String target = rabbitMqTarget();
        try (Connection connection = connectionFactory.createConnection()) {
            boolean open = connection.isOpen();
            return resource(
                    "rabbitmq",
                    "RabbitMQ Broker",
                    "mq",
                    "消息队列 / RabbitMQ",
                    open ? "up" : "down",
                    open ? "Broker 连接正常" : "Broker 连接未打开",
                    target,
                    elapsedMs(start),
                    List.of(
                            metric("积压消息", String.valueOf(backlog)),
                            metric("可用队列", healthyQueueCount + "/" + queueCount),
                            metric("命令队列", normalizeValue(rabbitMqProperties.getQueue(), "-"))
                    )
            );
        } catch (Exception error) {
            return resource(
                    "rabbitmq",
                    "RabbitMQ Broker",
                    "mq",
                    "消息队列 / RabbitMQ",
                    "down",
                    safeMessage(error),
                    target,
                    elapsedMs(start),
                    List.of(
                            metric("积压消息", String.valueOf(backlog)),
                            metric("命令队列", normalizeValue(rabbitMqProperties.getQueue(), "-"))
                    )
            );
        }
    }

    private DevDashboardDtos.ResourceStatus inspectRedis() {
        String redisUrl = safeProperty("REDIS_URL");
        if (!StringUtils.hasText(redisUrl)) {
            return resource("redis", "Redis 缓存", "redis", "Redis / 工作流缓存", "missing", "未配置 Redis URL", "", 0, List.of());
        }
        ParsedRedisTarget target = parseRedisUrl(redisUrl);
        if (!StringUtils.hasText(target.host())) {
            return resource("redis", "Redis 缓存", "redis", "Redis / 工作流缓存", "down", "Redis URL 解析失败", maskTarget(redisUrl), 0, List.of());
        }

        long start = System.nanoTime();
        try (Socket socket = openRedisSocket(target.scheme(), target.host(), target.port(), 1500)) {
            socket.setSoTimeout(1500);
            if (StringUtils.hasText(target.password())) {
                String authReply = StringUtils.hasText(target.username())
                        ? sendRedisCommand(socket, "AUTH", target.username(), target.password())
                        : sendRedisCommand(socket, "AUTH", target.password());
                if (!authReply.startsWith("+OK")) {
                    return resource(
                            "redis",
                            "Redis 缓存",
                            "redis",
                            "Redis / 工作流缓存",
                            "down",
                            "Redis AUTH 失败: " + authReply,
                            maskRedisTarget(target),
                            elapsedMs(start),
                            List.of(metric("DB", target.database()))
                    );
                }
            }
            String pingReply = sendRedisCommand(socket, "PING");
            if (pingReply.startsWith("+PONG") || pingReply.startsWith("+OK")) {
                return resource(
                        "redis",
                        "Redis 缓存",
                        "redis",
                        "Redis / 工作流缓存",
                        "up",
                        "Redis PING 成功",
                        maskRedisTarget(target),
                        elapsedMs(start),
                        List.of(
                                metric("DB", target.database()),
                                metric("Checkpointer", normalizeValue(safeProperty("LANGGRAPH_CHECKPOINTER_BACKEND"), "memory"))
                        )
                );
            }
            return resource(
                    "redis",
                    "Redis 缓存",
                    "redis",
                    "Redis / 工作流缓存",
                    "down",
                    "Redis PING 返回异常: " + pingReply,
                    maskRedisTarget(target),
                    elapsedMs(start),
                    List.of(metric("DB", target.database()))
            );
        } catch (Exception error) {
            return resource(
                    "redis",
                    "Redis 缓存",
                    "redis",
                    "Redis / 工作流缓存",
                    "down",
                    safeMessage(error),
                    maskRedisTarget(target),
                    elapsedMs(start),
                    List.of(metric("DB", target.database()))
            );
        }
    }

    private DevDashboardDtos.ResourceStatus inspectStorage() {
        TaskStorageService.StorageProbe probe = taskStorageService.probe();
        String backend = normalizeValue(storageProperties.getBackend(), "local").toLowerCase(Locale.ROOT);
        String state = "s3".equals(backend)
                ? (probe.available() ? "up" : "down")
                : (probe.available() ? "local" : "down");
        return resource(
                "storage",
                "MinIO / 对象存储",
                "storage",
                "MinIO / 对象存储",
                state,
                probe.detail(),
                probe.target(),
                probe.latencyMs(),
                List.of(
                        metric("Backend", backend),
                        metric("Bucket", normalizeValue(storageProperties.getBucket(), "-")),
                        metric("PathStyle", String.valueOf(storageProperties.isPathStyle()))
                )
        );
    }

    private DevDashboardDtos.ResourceStatus inspectAiService(DevDashboardDtos.PythonMetrics pythonMetrics) {
        String baseUrl = safe(aiServiceProperties.getBaseUrl());
        if (!StringUtils.hasText(baseUrl)) {
            return resource("ai-service", "Python AI 服务", "ai", "AI 服务连接", "missing", "未配置 OCR_AI_BASE_URL", "", 0, List.of());
        }
        JsonNode celery = pythonMetrics.payload().path("celery");
        return resource(
                "ai-service",
                "Python AI 服务",
                "ai",
                "AI 服务连接",
                pythonMetrics.available() ? "up" : "down",
                pythonMetrics.detail(),
                joinUrl(baseUrl, devDashboardProperties.getPythonMetricsPath()),
                0,
                List.of(
                        metric("Worker", String.valueOf(celery.path("worker_count").asInt(0))),
                        metric("Active", String.valueOf(celery.path("active_count").asInt(0))),
                        metric("Reserved", String.valueOf(celery.path("reserved_count").asInt(0)))
                )
        );
    }

    private DevDashboardDtos.ResourceStatus inspectLayoutApi() {
        String backend = normalizeValue(safeProperty("OCR_LAYOUT_BACKEND"), "local").toLowerCase(Locale.ROOT);
        String url = safeProperty("OCR_LAYOUT_API_URL");
        if (!"api".equals(backend)) {
            return resource(
                    "layout-api",
                    "版面解析 API",
                    "layout-api",
                    "版面解析 API",
                    "local",
                    "当前使用本地版面引擎",
                    url,
                    0,
                    List.of(metric("Backend", backend))
            );
        }
        if (!StringUtils.hasText(url)) {
            return resource("layout-api", "版面解析 API", "layout-api", "版面解析 API", "missing", "未配置 OCR_LAYOUT_API_URL", "", 0, List.of(metric("Backend", backend)));
        }
        Map<String, String> headers = new LinkedHashMap<>();
        if (StringUtils.hasText(safeProperty("OCR_LAYOUT_API_TOKEN"))) {
            headers.put("Authorization", "Bearer " + safeProperty("OCR_LAYOUT_API_TOKEN"));
        }
        return probeHttpResource(
                "layout-api",
                "版面解析 API",
                "layout-api",
                "版面解析 API",
                url,
                headers,
                List.of(
                        metric("Backend", backend),
                        metric("Timeout", normalizeValue(safeProperty("OCR_LAYOUT_API_TIMEOUT_SECONDS"), "120") + "s")
                )
        );
    }

    private DevDashboardDtos.ResourceStatus inspectLlmApi() {
        String llmBaseUrl = firstNonBlank(safeProperty("LLM_BASE_URL"), safeProperty("MINIMAX_BASE_URL"));
        if (!StringUtils.hasText(llmBaseUrl)) {
            return resource("llm-api", "LLM / OpenAI 兼容接口", "llm-api", "LLM / 视觉模型接口", "missing", "未配置 LLM_BASE_URL / MINIMAX_BASE_URL", "", 0, List.of());
        }
        String apiKey = firstNonBlank(safeProperty("LLM_API_KEY"), safeProperty("MINIMAX_API_KEY"));
        Map<String, String> headers = new LinkedHashMap<>();
        if (StringUtils.hasText(apiKey)) {
            headers.put("Authorization", "Bearer " + apiKey);
        }
        return probeHttpResource(
                "llm-api",
                "LLM / OpenAI 兼容接口",
                "llm-api",
                "LLM / 视觉模型接口",
                resolveLlmProbeUrl(llmBaseUrl),
                headers,
                List.of(
                        metric("文本模型", normalizeValue(firstNonBlank(safeProperty("LLM_MODEL"), safeProperty("MINIMAX_MODEL")), "-")),
                        metric("视觉模型", normalizeValue(safeProperty("VISION_LLM_MODEL"), "-"))
                )
        );
    }

    private DevDashboardDtos.ResourceStatus inspectBaiduVisionApi() {
        String backend = normalizeValue(safeProperty("OCR_VL_BACKEND"), "auto").toLowerCase(Locale.ROOT);
        if (!"baidu".equals(backend) && !"baidu_vl".equals(backend)) {
            return resource(
                    "baidu-api",
                    "百度文档解析",
                    "llm-api",
                    "LLM / 视觉模型接口",
                    "local",
                    "当前未启用百度文档解析链路",
                    "https://aip.baidubce.com",
                    0,
                    List.of(metric("Backend", backend))
            );
        }
        boolean configured = StringUtils.hasText(safeProperty("BAIDU_API_KEY")) && StringUtils.hasText(safeProperty("BAIDU_SECRET_KEY"));
        return resource(
                "baidu-api",
                "百度文档解析",
                "llm-api",
                "LLM / 视觉模型接口",
                configured ? "configured" : "missing",
                configured ? "已配置密钥，任务执行时按需调用" : "未配置 BAIDU_API_KEY / BAIDU_SECRET_KEY",
                "https://aip.baidubce.com",
                0,
                List.of(metric("Backend", backend))
        );
    }

    private DevDashboardDtos.ResourceStatus probeHttpResource(
            String key,
            String label,
            String controlGroup,
            String controlGroupLabel,
            String url,
            Map<String, String> headers,
            List<DevDashboardDtos.ResourceMetric> metrics
    ) {
        long start = System.nanoTime();
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(3))
                    .GET();
            headers.forEach((name, value) -> {
                if (StringUtils.hasText(value)) {
                    builder.header(name, value);
                }
            });
            HttpResponse<Void> response = shortHttpClient().send(builder.build(), HttpResponse.BodyHandlers.discarding());
            int status = response.statusCode();
            String state = status >= 200 && status < 500 ? "up" : "down";
            return resource(
                    key,
                    label,
                    controlGroup,
                    controlGroupLabel,
                    state,
                    "HTTP " + status,
                    maskTarget(url),
                    elapsedMs(start),
                    metrics
            );
        } catch (Exception error) {
            return resource(
                    key,
                    label,
                    controlGroup,
                    controlGroupLabel,
                    "down",
                    safeMessage(error),
                    maskTarget(url),
                    elapsedMs(start),
                    metrics
            );
        }
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
            HttpResponse<String> response = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(Math.max(1, aiServiceProperties.getConnectTimeoutSeconds())))
                    .build()
                    .send(request, HttpResponse.BodyHandlers.ofString());
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
                normalizeValue(task.getFilePath(), ""),
                normalizeValue(task.getMode(), ""),
                status,
                normalizeValue(task.getBatchId(), ""),
                normalizeValue(task.getTraceId(), ""),
                task.getProgressPercent() == null ? 0.0 : task.getProgressPercent(),
                normalizeValue(task.getSubmitterUsername(), ""),
                task.getPageCount() == null ? 0 : task.getPageCount(),
                normalizeValue(task.getErrorMessage(), ""),
                normalizeValue(task.getWorkflowThreadId(), ""),
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

    private String rabbitMqTarget() {
        String host = normalizeValue(safeProperty("SPRING_RABBITMQ_HOST"), "127.0.0.1");
        String port = normalizeValue(safeProperty("SPRING_RABBITMQ_PORT"), "5672");
        String username = normalizeValue(safeProperty("SPRING_RABBITMQ_USERNAME"), "guest");
        String vhost = normalizeValue(safeProperty("SPRING_RABBITMQ_VHOST"), "/");
        return "amqp://" + username + "@"
                + host + ":" + port + "/"
                + ("/".equals(vhost) ? "%2F" : vhost.replaceFirst("^/+", ""));
    }

    private String safeProperty(String key) {
        String value = environment.getProperty(key);
        return value == null ? "" : value.trim();
    }

    private HttpClient shortHttpClient() {
        return HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
    }

    private static Socket openRedisSocket(String scheme, String host, int port, int timeoutMs) throws IOException {
        SocketFactory factory = "rediss".equalsIgnoreCase(scheme)
                ? SSLSocketFactory.getDefault()
                : SocketFactory.getDefault();
        Socket socket = factory.createSocket();
        socket.connect(new java.net.InetSocketAddress(host, port), timeoutMs);
        return socket;
    }

    private static String sendRedisCommand(Socket socket, String... parts) throws IOException {
        OutputStream out = socket.getOutputStream();
        InputStream in = socket.getInputStream();
        out.write(("*" + parts.length + "\r\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
        for (String part : parts) {
            byte[] bytes = (part == null ? "" : part).getBytes(java.nio.charset.StandardCharsets.UTF_8);
            out.write(("$" + bytes.length + "\r\n").getBytes(java.nio.charset.StandardCharsets.UTF_8));
            out.write(bytes);
            out.write("\r\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        out.flush();
        int prefix = in.read();
        if (prefix < 0) {
            throw new IOException("Redis connection closed.");
        }
        return (char) prefix + readRedisLine(in);
    }

    private static String readRedisLine(InputStream in) throws IOException {
        StringBuilder builder = new StringBuilder();
        int previous = -1;
        int current;
        while ((current = in.read()) >= 0) {
            if (previous == '\r' && current == '\n') {
                builder.setLength(Math.max(0, builder.length() - 1));
                return builder.toString();
            }
            builder.append((char) current);
            previous = current;
        }
        throw new IOException("Redis response is incomplete.");
    }

    private static ParsedRedisTarget parseRedisUrl(String rawUrl) {
        try {
            URI uri = URI.create(rawUrl);
            String userInfo = uri.getUserInfo();
            String username = "";
            String password = "";
            if (StringUtils.hasText(userInfo)) {
                String[] parts = userInfo.split(":", 2);
                if (parts.length == 2) {
                    username = parts[0];
                    password = parts[1];
                } else {
                    password = parts[0];
                }
            }
            String database = safePathSegment(uri.getPath(), "0");
            return new ParsedRedisTarget(
                    normalizeValue(uri.getScheme(), "redis"),
                    uri.getHost(),
                    uri.getPort() > 0 ? uri.getPort() : 6379,
                    username,
                    password,
                    database
            );
        } catch (Exception error) {
            return new ParsedRedisTarget("redis", "", 6379, "", "", "0");
        }
    }

    private static String safePathSegment(String path, String fallback) {
        String value = path == null ? "" : path.replaceFirst("^/+", "").trim();
        return StringUtils.hasText(value) ? value : fallback;
    }

    private static String maskRedisTarget(ParsedRedisTarget target) {
        String auth = StringUtils.hasText(target.password())
                ? (StringUtils.hasText(target.username()) ? target.username() + ":***@" : ":***@")
                : "";
        return target.scheme() + "://" + auth + target.host() + ":" + target.port() + "/" + target.database();
    }

    private static String maskTarget(String rawUrl) {
        try {
            URI uri = URI.create(rawUrl);
            if (!StringUtils.hasText(uri.getUserInfo())) {
                return rawUrl;
            }
            String maskedUserInfo = uri.getUserInfo().contains(":")
                    ? uri.getUserInfo().split(":", 2)[0] + ":***"
                    : "***";
            return new URI(
                    uri.getScheme(),
                    maskedUserInfo,
                    uri.getHost(),
                    uri.getPort(),
                    uri.getPath(),
                    uri.getQuery(),
                    uri.getFragment()
            ).toString();
        } catch (Exception error) {
            return rawUrl.replaceAll("://([^:@]+):([^@]+)@", "://$1:***@");
        }
    }

    private static String firstNonBlank(String... values) {
        for (String value : values) {
            if (StringUtils.hasText(value)) {
                return value.trim();
            }
        }
        return "";
    }

    private static String resolveLlmProbeUrl(String baseUrl) {
        String normalized = baseUrl == null ? "" : baseUrl.trim().replaceAll("/+$", "");
        if (normalized.endsWith("/models")) {
            return normalized;
        }
        return normalized + "/models";
    }

    private static DevDashboardDtos.ResourceStatus resource(
            String key,
            String label,
            String controlGroup,
            String controlGroupLabel,
            String state,
            String detail,
            String target,
            long latencyMs,
            List<DevDashboardDtos.ResourceMetric> metrics
    ) {
        return new DevDashboardDtos.ResourceStatus(
                key,
                label,
                controlGroup,
                controlGroupLabel,
                state,
                detail == null ? "" : detail,
                target == null ? "" : target,
                latencyMs,
                metrics == null ? List.of() : metrics
        );
    }

    private static DevDashboardDtos.ResourceMetric metric(String label, String value) {
        return new DevDashboardDtos.ResourceMetric(label, value == null ? "" : value);
    }

    private static long elapsedMs(long startNanos) {
        return Math.max(0, (System.nanoTime() - startNanos) / 1_000_000L);
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private static String safeMessage(Throwable error) {
        if (error == null) {
            return "Unknown error";
        }
        if (StringUtils.hasText(error.getMessage())) {
            return error.getMessage();
        }
        return error.getClass().getSimpleName();
    }

    private record TaskAggregation(
            DevDashboardDtos.TaskSummary taskSummary,
            DevDashboardDtos.WorkflowSummary workflowSummary,
            List<DevDashboardDtos.TaskItem> queuedTasks,
            List<DevDashboardDtos.TaskItem> processingTasks,
            List<DevDashboardDtos.TaskItem> recentTasks
    ) {
    }

    private record ParsedRedisTarget(
            String scheme,
            String host,
            int port,
            String username,
            String password,
            String database
    ) {
    }
}
