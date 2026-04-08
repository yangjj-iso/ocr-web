package com.ocrweb.controlplane.health;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.config.AiServiceProperties;
import com.ocrweb.controlplane.task.service.AiProxyCircuitBreaker;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;

import javax.sql.DataSource;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.sql.Connection;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class ControlPlaneHealthService {
    private final DataSource dataSource;
    private final RabbitTemplate rabbitTemplate;
    private final AiServiceProperties aiServiceProperties;
    private final AiProxyCircuitBreaker aiProxyCircuitBreaker;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;

    @Autowired
    public ControlPlaneHealthService(
            DataSource dataSource,
            RabbitTemplate rabbitTemplate,
            AiServiceProperties aiServiceProperties,
            AiProxyCircuitBreaker aiProxyCircuitBreaker,
            ObjectMapper objectMapper
    ) {
        this(
                dataSource,
                rabbitTemplate,
                aiServiceProperties,
                aiProxyCircuitBreaker,
                objectMapper,
                HttpClient.newBuilder()
                        .connectTimeout(Duration.ofSeconds(Math.max(1, aiServiceProperties.getConnectTimeoutSeconds())))
                        .build()
        );
    }

    ControlPlaneHealthService(
            DataSource dataSource,
            RabbitTemplate rabbitTemplate,
            AiServiceProperties aiServiceProperties,
            AiProxyCircuitBreaker aiProxyCircuitBreaker,
            ObjectMapper objectMapper,
            HttpClient httpClient
    ) {
        this.dataSource = dataSource;
        this.rabbitTemplate = rabbitTemplate;
        this.aiServiceProperties = aiServiceProperties;
        this.aiProxyCircuitBreaker = aiProxyCircuitBreaker;
        this.objectMapper = objectMapper;
        this.httpClient = httpClient;
    }

    public Map<String, Object> live() {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("service", "java-control-plane");
        payload.put("status", "UP");
        payload.put("timestamp", OffsetDateTime.now().toString());
        return payload;
    }

    public ReadinessReport readiness() {
        ComponentHealth database = checkDatabase();
        ComponentHealth rabbitmq = checkRabbitMq();
        ComponentHealth aiService = checkAiService();
        boolean ready = database.up() && rabbitmq.up() && aiService.up();

        Map<String, Object> components = new LinkedHashMap<>();
        components.put("database", database.toMap());
        components.put("rabbitmq", rabbitmq.toMap());
        components.put("ai_service", aiService.toMap());

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("service", "java-control-plane");
        payload.put("status", ready ? "UP" : "DOWN");
        payload.put("timestamp", OffsetDateTime.now().toString());
        payload.put("components", components);
        return new ReadinessReport(ready, payload);
    }

    private ComponentHealth checkDatabase() {
        long start = System.nanoTime();
        try (Connection connection = dataSource.getConnection()) {
            boolean valid = connection.isValid(2);
            if (!valid) {
                return ComponentHealth.down("validation_failed", elapsedMs(start));
            }
            return ComponentHealth.up("connection_valid", elapsedMs(start));
        } catch (Exception error) {
            return ComponentHealth.down(error.getClass().getSimpleName(), elapsedMs(start));
        }
    }

    private ComponentHealth checkRabbitMq() {
        long start = System.nanoTime();
        try {
            Boolean open = rabbitTemplate.execute(channel -> channel.isOpen());
            if (Boolean.TRUE.equals(open)) {
                return ComponentHealth.up("channel_open", elapsedMs(start));
            }
            return ComponentHealth.down("channel_unavailable", elapsedMs(start));
        } catch (Exception error) {
            return ComponentHealth.down(error.getClass().getSimpleName(), elapsedMs(start));
        }
    }

    private ComponentHealth checkAiService() {
        long start = System.nanoTime();
        if (aiProxyCircuitBreaker.isOpen()) {
            return ComponentHealth.down("circuit_open_until:" + aiProxyCircuitBreaker.getOpenUntil(), elapsedMs(start));
        }

        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(resolveAiHealthUri())
                    .timeout(Duration.ofSeconds(Math.max(1, Math.min(aiServiceProperties.getReadTimeoutSeconds(), 10))))
                    .GET()
                    .build();
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                return ComponentHealth.down("http_" + response.statusCode(), elapsedMs(start));
            }
            JsonNode payload = objectMapper.readTree(response.body());
            String status = payload.path("status").asText("").trim();
            if ("ok".equalsIgnoreCase(status) || "up".equalsIgnoreCase(status)) {
                return ComponentHealth.up("http_" + response.statusCode(), elapsedMs(start));
            }
            return ComponentHealth.down(status.isBlank() ? "unknown_status" : status, elapsedMs(start));
        } catch (IOException error) {
            return ComponentHealth.down(error.getClass().getSimpleName(), elapsedMs(start));
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            return ComponentHealth.down("InterruptedException", elapsedMs(start));
        }
    }

    private URI resolveAiHealthUri() {
        String baseUrl = aiServiceProperties.getBaseUrl();
        String healthPath = aiServiceProperties.getHealthPath();
        if (baseUrl.endsWith("/")) {
            baseUrl = baseUrl.substring(0, baseUrl.length() - 1);
        }
        if (!healthPath.startsWith("/")) {
            healthPath = "/" + healthPath;
        }
        return URI.create(baseUrl + healthPath);
    }

    private static long elapsedMs(long startNanos) {
        return Math.max(0, (System.nanoTime() - startNanos) / 1_000_000L);
    }

    record ComponentHealth(boolean up, String detail, long latencyMs) {
        static ComponentHealth up(String detail, long latencyMs) {
            return new ComponentHealth(true, detail, latencyMs);
        }

        static ComponentHealth down(String detail, long latencyMs) {
            return new ComponentHealth(false, detail, latencyMs);
        }

        Map<String, Object> toMap() {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("status", up ? "UP" : "DOWN");
            payload.put("detail", detail);
            payload.put("latency_ms", latencyMs);
            return payload;
        }
    }

    public record ReadinessReport(boolean ready, Map<String, Object> payload) {
    }
}
