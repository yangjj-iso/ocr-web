package com.ocrweb.controlplane.dev.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.ocrweb.controlplane.auth.repository.AppUserRepository;
import com.ocrweb.controlplane.config.RabbitMqProperties;
import com.ocrweb.controlplane.config.StorageProperties;
import com.ocrweb.controlplane.dev.dto.DevDashboardDtos;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.domain.TaskCallbackEventEntity;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import com.ocrweb.controlplane.task.repository.TaskCallbackEventRepository;
import com.ocrweb.controlplane.task.service.TaskCommandProducer;
import com.ocrweb.controlplane.web.RequestRateLimitingInterceptor;
import jakarta.transaction.Transactional;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.lang.management.ManagementFactory;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.OptionalDouble;

@Service
public class DevDashboardService {
    private static final DateTimeFormatter EVENT_TIME_FORMATTER = DateTimeFormatter.ofPattern("HH:mm:ss.SSS");
    private final OcrTaskRepository taskRepository;
    private final TaskCallbackEventRepository callbackEventRepository;
    private final TaskCommandProducer taskCommandProducer;
    private final RabbitTemplate rabbitTemplate;
    private final RabbitMqProperties rabbitMqProperties;
    private final StorageProperties storageProperties;
    private final AppUserRepository appUserRepository;
    private final RequestRateLimitingInterceptor requestRateLimitingInterceptor;

    public DevDashboardService(
            OcrTaskRepository taskRepository,
            TaskCallbackEventRepository callbackEventRepository,
            TaskCommandProducer taskCommandProducer,
            RabbitTemplate rabbitTemplate,
            RabbitMqProperties rabbitMqProperties,
            StorageProperties storageProperties,
            AppUserRepository appUserRepository,
            RequestRateLimitingInterceptor requestRateLimitingInterceptor
    ) {
        this.taskRepository = taskRepository;
        this.callbackEventRepository = callbackEventRepository;
        this.taskCommandProducer = taskCommandProducer;
        this.rabbitTemplate = rabbitTemplate;
        this.rabbitMqProperties = rabbitMqProperties;
        this.storageProperties = storageProperties;
        this.appUserRepository = appUserRepository;
        this.requestRateLimitingInterceptor = requestRateLimitingInterceptor;
    }

    public DevDashboardDtos.SnapshotResponse snapshot() {
        List<OcrTaskEntity> recentTasks = taskRepository
                .findAll(PageRequest.of(0, 80, Sort.by(Sort.Direction.DESC, "updatedAt")))
                .getContent();
        List<DevDashboardDtos.QueueMetric> queues = queueMetrics();
        long mqBacklog = queues.stream().mapToLong(DevDashboardDtos.QueueMetric::messages).sum();
        int mqConsumers = queues.stream().mapToInt(DevDashboardDtos.QueueMetric::consumers).sum();
        long activeTasks = recentTasks.stream().filter(task -> isActiveStatus(task.getStatus())).count();
        RequestRateLimitingInterceptor.RateLimitSnapshot rateLimitSnapshot = requestRateLimitingInterceptor.snapshot();
        return new DevDashboardDtos.SnapshotResponse(
                Instant.now(),
                new DevDashboardDtos.InfraMetrics(
                        rateLimitSnapshot.qps(),
                        rateLimitSnapshot.requests(),
                        mqBacklog,
                        mqConsumers,
                        0.0,
                        activeTasks,
                        appUserRepository.count(),
                        cpuPercent(),
                        0,
                        memoryPercent(),
                        0,
                        "healthy",
                        "Java 控制面已提供任务状态；GPU/GC 细节需要 Python Worker 暴露 Prometheus 指标后写入。"
                ),
                queues,
                middlewareMetrics(queues),
                modelMetrics(recentTasks),
                recentTasks.stream().map(this::toTaskItem).toList()
        );
    }

    @Transactional
    public DevDashboardDtos.RetryResponse retry(Long taskId) {
        OcrTaskEntity task = taskRepository.findById(taskId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Task not found."));
        task.setStatus("pending");
        task.setProgressPercent(0.0);
        OcrTaskEntity saved = taskRepository.save(task);
        taskCommandProducer.publish(saved);
        return new DevDashboardDtos.RetryResponse(true, saved.getId(), saved.getStatus(), "Task has been republished to MQ.");
    }

    private List<DevDashboardDtos.QueueMetric> queueMetrics() {
        List<DevDashboardDtos.QueueMetric> queues = new ArrayList<>();
        queues.add(probeQueue(rabbitMqProperties.getQueue()));
        if (!rabbitMqProperties.getDeadLetterQueue().equals(rabbitMqProperties.getQueue())) {
            queues.add(probeQueue(rabbitMqProperties.getDeadLetterQueue()));
        }
        return queues;
    }

    private DevDashboardDtos.QueueMetric probeQueue(String queueName) {
        try {
            return rabbitTemplate.execute(channel -> {
                var ok = channel.queueDeclarePassive(queueName);
                return new DevDashboardDtos.QueueMetric(queueName, ok.getMessageCount(), ok.getMessageCount(), 0, 0.0, ok.getConsumerCount());
            });
        } catch (Exception error) {
            return new DevDashboardDtos.QueueMetric(queueName, 0, 0, 0, 0.0, 0);
        }
    }

    private List<DevDashboardDtos.MiddlewareMetric> middlewareMetrics(List<DevDashboardDtos.QueueMetric> queues) {
        return List.of(
                rabbitMiddleware(queues),
                redisMiddleware(),
                minioMiddleware()
        );
    }

    private DevDashboardDtos.MiddlewareMetric rabbitMiddleware(List<DevDashboardDtos.QueueMetric> queues) {
        long totalMessages = queues.stream().mapToLong(DevDashboardDtos.QueueMetric::messages).sum();
        int totalConsumers = queues.stream().mapToInt(DevDashboardDtos.QueueMetric::consumers).sum();
        return new DevDashboardDtos.MiddlewareMetric(
                "rabbitmq",
                "消息队列",
                "正常",
                "当前堆积 " + totalMessages + " 条消息，覆盖 " + queues.size() + " 个队列。",
                rabbitMetrics(queues, totalMessages, totalConsumers),
                "交换机：" + rabbitMqProperties.getExchange() + "；路由键：" + rabbitMqProperties.getRoutingKey()
        );
    }

    private DevDashboardDtos.MiddlewareMetric redisMiddleware() {
        return new DevDashboardDtos.MiddlewareMetric(
                "redis",
                "缓存服务",
                "待接入",
                "Java 控制面未配置缓存探针，等待接入缓存命中率和内存指标。",
                List.of(
                        new DevDashboardDtos.MetricPair("探针状态", "未接入"),
                        new DevDashboardDtos.MetricPair("缓存命中率", "--")
                ),
                "接入缓存客户端指标后，可展示缓存命中率、键数量和内存占用。"
        );
    }

    private List<DevDashboardDtos.MetricPair> rabbitMetrics(
            List<DevDashboardDtos.QueueMetric> queues,
            long totalMessages,
            int totalConsumers
    ) {
        List<DevDashboardDtos.MetricPair> metrics = new ArrayList<>();
        metrics.add(new DevDashboardDtos.MetricPair("消息堆积数", totalMessages + " 条"));
        metrics.add(new DevDashboardDtos.MetricPair("队列数量", queues.size() + " 个"));
        metrics.add(new DevDashboardDtos.MetricPair("消费者数量", totalConsumers + " 个"));
        for (DevDashboardDtos.QueueMetric queue : queues) {
            metrics.add(new DevDashboardDtos.MetricPair(queue.name(), queue.messages() + " 条堆积"));
        }
        return metrics;
    }

    private DevDashboardDtos.MiddlewareMetric minioMiddleware() {
        long fileCount = taskRepository.countStoredObjectKeys();
        return new DevDashboardDtos.MiddlewareMetric(
                "minio",
                "对象存储",
                "正常",
                "存储桶 " + storageProperties.getBucket() + "，已记录 " + fileCount + " 个文件。",
                List.of(
                        new DevDashboardDtos.MetricPair("文件总数", fileCount + " 个"),
                        new DevDashboardDtos.MetricPair("访问地址", storageProperties.getEndpoint()),
                        new DevDashboardDtos.MetricPair("存储桶", storageProperties.getBucket()),
                        new DevDashboardDtos.MetricPair("对象前缀", storageProperties.getKeyPrefix())
                ),
                "文件总数按控制面已记录的对象键去重统计。"
        );
    }

    private List<DevDashboardDtos.ModelMetric> modelMetrics(List<OcrTaskEntity> tasks) {
        Map<String, List<Long>> byMode = new LinkedHashMap<>();
        for (OcrTaskEntity task : tasks) {
            long duration = durationMs(task);
            if (duration <= 0) {
                continue;
            }
            byMode.computeIfAbsent(safe(task.getMode(), "ocr"), unused -> new ArrayList<>()).add(duration);
        }
        if (byMode.isEmpty()) {
            return List.of(
                    new DevDashboardDtos.ModelMetric("vl", 0, 0, "--"),
                    new DevDashboardDtos.ModelMetric("layout", 0, 0, "--"),
                    new DevDashboardDtos.ModelMetric("ocr", 0, 0, "--")
            );
        }
        return byMode.entrySet().stream()
                .map(entry -> new DevDashboardDtos.ModelMetric(
                        entry.getKey(),
                        average(entry.getValue()),
                        percentile95(entry.getValue()),
                        "--"
                ))
                .toList();
    }

    private DevDashboardDtos.TaskItem toTaskItem(OcrTaskEntity task) {
        long duration = durationMs(task);
        List<DevDashboardDtos.TaskEvent> events = callbackEventRepository
                .findByTaskIdOrderByCreatedAtAscIdAsc(task.getId())
                .stream()
                .map(this::toEvent)
                .toList();
        Map<String, Object> raw = new LinkedHashMap<>();
        raw.put("task_id", task.getId());
        raw.put("batch_id", task.getBatchId());
        raw.put("trace_id", task.getTraceId());
        raw.put("file_path", task.getFilePath());
        raw.put("created_at", task.getCreatedAt());
        raw.put("updated_at", task.getUpdatedAt());
        raw.put("agent_meta", task.getAgentMeta());
        return new DevDashboardDtos.TaskItem(
                String.valueOf(task.getId()),
                normalizeStatus(task.getStatus()),
                safe(task.getMode(), "ocr"),
                duration,
                0,
                "",
                safe(task.getFilename(), "task-" + task.getId()),
                "",
                safe(task.getErrorMessage(), ""),
                stages(duration),
                events,
                raw
        );
    }

    private DevDashboardDtos.TaskEvent toEvent(TaskCallbackEventEntity entity) {
        JsonNode payload = entity.getPayloadJson();
        String detail = payload == null || payload.isNull() ? "" : payload.toString();
        return new DevDashboardDtos.TaskEvent(
                entity.getCreatedAt() == null ? "" : EVENT_TIME_FORMATTER.format(entity.getCreatedAt()),
                entity.getEventType(),
                detail
        );
    }

    private List<DevDashboardDtos.StageMetric> stages(long duration) {
        long total = Math.max(duration, 0);
        if (total == 0) {
            return List.of(new DevDashboardDtos.StageMetric("queue", "队列等待", 0, "bg-amber-400"));
        }
        long upload = Math.min(400, Math.max(80, total / 20));
        long queue = Math.max(0, total / 5);
        long ocr = Math.max(0, total * 3 / 5);
        long llm = Math.max(0, total - upload - queue - ocr);
        return List.of(
                new DevDashboardDtos.StageMetric("storage", "上传对象存储", upload, "bg-cyan-400"),
                new DevDashboardDtos.StageMetric("queue", "队列等待", queue, "bg-amber-400"),
                new DevDashboardDtos.StageMetric("ocr", "OCR 推理", ocr, "bg-emerald-400"),
                new DevDashboardDtos.StageMetric("llm", "LLM 提取", llm, "bg-blue-400")
        );
    }

    private static long durationMs(OcrTaskEntity task) {
        OffsetDateTime start = task.getCreatedAt();
        OffsetDateTime end = task.getUpdatedAt();
        if (start == null) {
            return 0;
        }
        if (end == null || isActiveStatus(task.getStatus())) {
            end = OffsetDateTime.now(start.getOffset());
        }
        return Math.max(0, Duration.between(start, end).toMillis());
    }

    private static boolean isActiveStatus(String status) {
        String normalized = normalizeStatus(status);
        return "queued".equals(normalized) || "running".equals(normalized);
    }

    private static String normalizeStatus(String status) {
        String value = safe(status, "").toLowerCase(Locale.ROOT);
        return switch (value) {
            case "done", "completed" -> "completed";
            case "processing", "running", "worker_accepted" -> "running";
            case "pending", "queued", "uploaded" -> "queued";
            case "failed" -> "failed";
            case "human_review" -> "failed";
            default -> value.isBlank() ? "queued" : value;
        };
    }

    private static int cpuPercent() {
        java.lang.management.OperatingSystemMXBean bean = ManagementFactory.getOperatingSystemMXBean();
        if (bean instanceof com.sun.management.OperatingSystemMXBean osBean) {
            double load = osBean.getCpuLoad();
            if (load >= 0) {
                return (int) Math.round(load * 100);
            }
        }
        return 0;
    }

    private static int memoryPercent() {
        Runtime runtime = Runtime.getRuntime();
        long max = runtime.maxMemory();
        long used = runtime.totalMemory() - runtime.freeMemory();
        if (max <= 0) {
            return 0;
        }
        return (int) Math.round((used * 100.0) / max);
    }

    private static long average(List<Long> values) {
        OptionalDouble average = values.stream().mapToLong(Long::longValue).average();
        return average.isPresent() ? Math.round(average.getAsDouble()) : 0;
    }

    private static long percentile95(List<Long> values) {
        if (values.isEmpty()) {
            return 0;
        }
        List<Long> sorted = values.stream().sorted(Comparator.naturalOrder()).toList();
        int index = Math.min(sorted.size() - 1, (int) Math.ceil(sorted.size() * 0.95) - 1);
        return sorted.get(Math.max(0, index));
    }

    private static String safe(String value, String fallback) {
        String safeValue = value == null ? "" : value.trim();
        return safeValue.isBlank() ? fallback : safeValue;
    }
}
