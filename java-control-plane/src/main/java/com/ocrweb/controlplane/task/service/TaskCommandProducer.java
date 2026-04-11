package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.ocrweb.controlplane.config.InternalApiProperties;
import com.ocrweb.controlplane.config.ProcessingProperties;
import com.ocrweb.controlplane.config.RabbitMqProperties;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.trace.RequestTraceContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Service
public class TaskCommandProducer {
    private static final Logger logger = LoggerFactory.getLogger(TaskCommandProducer.class);
    private static final Set<String> VISION_MODES = Set.of("vl", "baidu_vl");
    private final RabbitTemplate rabbitTemplate;
    private final RabbitMqProperties properties;
    private final InternalApiProperties internalApiProperties;
    private final ProcessingProperties processingProperties;

    public TaskCommandProducer(
            RabbitTemplate rabbitTemplate,
            RabbitMqProperties properties,
            InternalApiProperties internalApiProperties,
            ProcessingProperties processingProperties
    ) {
        this.rabbitTemplate = rabbitTemplate;
        this.properties = properties;
        this.internalApiProperties = internalApiProperties;
        this.processingProperties = processingProperties;
    }

    public void publish(OcrTaskEntity task) {
        String traceId = resolveTraceId(task);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("schema_version", "v1");
        payload.put("command", "OCR_TASK_SUBMIT");
        payload.put("command_id", UUID.randomUUID().toString());
        payload.put("trace_id", traceId);
        payload.put("task_id", task.getId());
        payload.put("batch_id", task.getBatchId() == null ? "" : task.getBatchId());
        payload.put("tenant_id", "default");
        payload.put("submitted_at", OffsetDateTime.now().toString());
        payload.put("priority", 5);
        payload.put("file", buildFilePayload(task));
        payload.put("execution", buildExecutionPayload(task, false));
        payload.put("business", Map.of(
                "submitted_by", "java-control-plane",
                "source_system", "ocr-web",
                "archive_context", Map.of("folder_path", folderFromFilePath(task.getFilePath()))
        ));
        payload.put("callback", Map.of(
                "contract", "java-internal-v1",
                "base_url", internalBaseUrl(),
                "result_mode", "inline_or_url"
        ));
        rabbitTemplate.convertAndSend(properties.getExchange(), properties.getRoutingKey(), payload);
        logger.info(
                "Published OCR task command: taskId={}, batchId={}, exchange={}, routingKey={}, traceId={}",
                task.getId(),
                task.getBatchId(),
                properties.getExchange(),
                properties.getRoutingKey(),
                traceId
        );
    }

    public void publishResume(OcrTaskEntity task, JsonNode resumePayload) {
        String traceId = resolveTraceId(task);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("schema_version", "v1");
        payload.put("command", "OCR_TASK_RESUME");
        payload.put("command_id", UUID.randomUUID().toString());
        payload.put("trace_id", traceId);
        payload.put("task_id", task.getId());
        payload.put("batch_id", task.getBatchId() == null ? "" : task.getBatchId());
        payload.put("tenant_id", "default");
        payload.put("submitted_at", OffsetDateTime.now().toString());
        payload.put("priority", 5);
        payload.put("execution", buildExecutionPayload(task, true));
        payload.put("business", Map.of(
                "submitted_by", "java-control-plane",
                "source_system", "ocr-web",
                "archive_context", Map.of("folder_path", folderFromFilePath(task.getFilePath()))
        ));
        payload.put("callback", Map.of(
                "contract", "java-internal-v1",
                "base_url", internalBaseUrl(),
                "result_mode", "inline_or_url"
        ));
        payload.put("workflow_thread_id", task.getWorkflowThreadId() == null ? "" : task.getWorkflowThreadId());
        payload.put("resume_payload", resumePayload);
        payload.put("resume_reason", "human_review_resume");
        rabbitTemplate.convertAndSend(properties.getExchange(), properties.getRoutingKey(), payload);
        logger.info(
                "Published OCR resume command: taskId={}, batchId={}, workflowThreadId={}, exchange={}, routingKey={}, traceId={}",
                task.getId(),
                task.getBatchId(),
                task.getWorkflowThreadId(),
                properties.getExchange(),
                properties.getRoutingKey(),
                traceId
        );
    }

    private static String resolveTraceId(OcrTaskEntity task) {
        if (task.getTraceId() != null && !task.getTraceId().isBlank()) {
            return task.getTraceId();
        }
        String requestTraceId = RequestTraceContext.getTraceId();
        if (requestTraceId != null && !requestTraceId.isBlank()) {
            return requestTraceId;
        }
        return UUID.randomUUID().toString();
    }

    private Map<String, Object> buildExecutionPayload(OcrTaskEntity task, boolean resumeWorkflow) {
        String requestedMode = normalizeMode(task.getMode());
        boolean forceHierarchicalResume = resumeWorkflow
                && task.getWorkflowThreadId() != null
                && !task.getWorkflowThreadId().isBlank();
        boolean hierarchicalEnabled = (processingProperties.isEnableHierarchicalAgent()
                && supportsHierarchicalAgent(requestedMode))
                || forceHierarchicalResume;
        boolean visionEnabled = VISION_MODES.contains(requestedMode) || hierarchicalEnabled;

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("mode", requestedMode);
        payload.put("ocr_backend", guessOcrBackend(requestedMode));
        payload.put("llm_backend", hierarchicalEnabled ? safe(processingProperties.getLlmBackend(), "local") : "local");
        payload.put("llm_model", hierarchicalEnabled ? safe(processingProperties.getLlmModel()) : "");
        payload.put("vision_enabled", visionEnabled);
        payload.put("enable_hierarchical_agent", hierarchicalEnabled);
        payload.put("processing_strategy", safe(processingProperties.getProcessingStrategy(), "auto"));
        payload.put("max_retries", processingProperties.getMaxRetries());
        payload.put("confidence_threshold", processingProperties.getConfidenceThreshold());
        payload.put("human_review_threshold_low", processingProperties.getHumanReviewThresholdLow());
        payload.put("human_review_threshold_high", processingProperties.getHumanReviewThresholdHigh());
        payload.put("timeout_seconds", processingProperties.getTimeoutSeconds());
        payload.put("gpu_profile", safe(processingProperties.getGpuProfile(), "single_gpu"));
        payload.put("langgraph_graph", safe(processingProperties.getLanggraphGraph(), "batch_supervisor_v1"));
        return payload;
    }

    private boolean supportsHierarchicalAgent(String mode) {
        return VISION_MODES.contains(mode);
    }

    private String guessOcrBackend(String mode) {
        if ("ocr".equals(mode) || "layout".equals(mode)) {
            return "api".equalsIgnoreCase(safe(processingProperties.getLayoutBackend()))
                    ? "aistudio_paddleocr_api"
                    : "paddleocr";
        }
        if ("baidu_vl".equals(mode)) {
            return "vision_baidu";
        }

        String vlBackend = safe(processingProperties.getVlBackend(), "auto").toLowerCase();
        return "local".equals(vlBackend) ? "vision_local" : "vision_" + vlBackend;
    }

    private static String normalizeMode(String mode) {
        String normalized = safe(mode).toLowerCase();
        return switch (normalized) {
            case "ocr", "layout", "vl", "baidu_vl" -> normalized;
            case "hierarchical_agent" -> "layout";
            default -> "layout";
        };
    }

    private Map<String, Object> buildFilePayload(OcrTaskEntity task) {
        return Map.of(
                "storage_provider", safe(task.getStorageProvider(), "control_plane"),
                "bucket", safe(task.getStorageBucket()),
                "object_key", safe(task.getStorageObjectKey()),
                "file_url", internalBaseUrl() + "/internal/api/v1/ocr/tasks/" + task.getId() + "/source-file",
                "filename", task.getFilename(),
                "content_type", guessContentType(task.getFilename()),
                "sha256", safe(task.getFileSha256()),
                "size_bytes", task.getFileSizeBytes() == null ? 0L : task.getFileSizeBytes()
        );
    }

    private String internalBaseUrl() {
        return internalApiProperties.getBaseUrl() == null ? "http://127.0.0.1:8080" : internalApiProperties.getBaseUrl().replaceAll("/+$", "");
    }

    private static String guessContentType(String filename) {
        if (filename == null) {
            return "application/octet-stream";
        }
        if (filename.endsWith(".pdf")) {
            return "application/pdf";
        }
        if (filename.endsWith(".png")) {
            return "image/png";
        }
        return "image/jpeg";
    }

    private static String folderFromFilePath(String filePath) {
        if (filePath == null || filePath.isBlank()) {
            return "";
        }
        Path parent = Path.of(filePath).getParent();
        return parent == null ? "" : parent.toString();
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private static String safe(String value, String fallback) {
        String trimmed = safe(value);
        return trimmed.isBlank() ? fallback : trimmed;
    }
}
