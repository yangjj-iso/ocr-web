package com.ocrweb.controlplane.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.config.RateLimitProperties;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@Component
public class RequestRateLimitingInterceptor implements HandlerInterceptor {
    private final RateLimitProperties rateLimitProperties;
    private final ObjectMapper objectMapper;
    private final ConcurrentHashMap<String, AtomicLong> counters = new ConcurrentHashMap<>();

    public RequestRateLimitingInterceptor(RateLimitProperties rateLimitProperties, ObjectMapper objectMapper) {
        this.rateLimitProperties = rateLimitProperties;
        this.objectMapper = objectMapper;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if (!rateLimitProperties.isEnabled()) {
            return true;
        }
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String path = request.getRequestURI();
        if (path == null || !path.startsWith("/api/ocr/")) {
            return true;
        }
        long windowSeconds = Math.max(1, rateLimitProperties.getWindowSeconds());
        long currentWindow = Instant.now().getEpochSecond() / windowSeconds;
        String bucket = bucketName(path);
        String key = resolveClientKey(request) + "|" + bucket + "|" + currentWindow;
        long count = counters.computeIfAbsent(key, unused -> new AtomicLong(0)).incrementAndGet();
        cleanupOldWindows(currentWindow);
        int limit = resolveLimit(path);
        if (limit <= 0) {
            return true;
        }
        if (count <= limit) {
            return true;
        }

        response.setStatus(429);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader("Retry-After", String.valueOf(windowSeconds));
        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("detail", "Request rate limit exceeded.");
        payload.put("bucket", bucketName(path));
        payload.put("limit", limit);
        payload.put("window_seconds", windowSeconds);
        response.getWriter().write(objectMapper.writeValueAsString(payload));
        return false;
    }

    public RateLimitSnapshot snapshot() {
        long windowSeconds = Math.max(1, rateLimitProperties.getWindowSeconds());
        long currentWindow = Instant.now().getEpochSecond() / windowSeconds;
        long requests = counters.entrySet()
                .stream()
                .filter(entry -> isWindow(entry, currentWindow))
                .mapToLong(entry -> entry.getValue().get())
                .sum();
        return new RateLimitSnapshot(windowSeconds, requests, requests / (double) windowSeconds);
    }

    private void cleanupOldWindows(long currentWindow) {
        if (counters.size() < 1024) {
            return;
        }
        counters.entrySet().removeIf(entry -> isOlderWindow(entry, currentWindow - 2));
    }

    private boolean isOlderWindow(Map.Entry<String, AtomicLong> entry, long thresholdWindow) {
        String[] parts = entry.getKey().split("\\|");
        if (parts.length < 3) {
            return false;
        }
        try {
            long window = Long.parseLong(parts[parts.length - 1]);
            return window < thresholdWindow;
        } catch (NumberFormatException ignored) {
            return false;
        }
    }

    private boolean isWindow(Map.Entry<String, AtomicLong> entry, long expectedWindow) {
        String[] parts = entry.getKey().split("\\|");
        if (parts.length < 3) {
            return false;
        }
        try {
            long window = Long.parseLong(parts[parts.length - 1]);
            return window == expectedWindow;
        } catch (NumberFormatException ignored) {
            return false;
        }
    }

    private int resolveLimit(String path) {
        String bucket = bucketName(path);
        return switch (bucket) {
            case "upload" -> rateLimitProperties.getUploadMaxRequests();
            case "batch_ai" -> rateLimitProperties.getBatchAiMaxRequests();
            case "preview" -> rateLimitProperties.getPreviewMaxRequests();
            default -> rateLimitProperties.getGeneralMaxRequests();
        };
    }

    private String bucketName(String path) {
        if ("/api/ocr/upload".equals(path) || "/api/ocr/upload-from-path".equals(path)) {
            return "upload";
        }
        if (path.contains("/thumbnail") || path.contains("/pages/")) {
            return "preview";
        }
        if (path.contains("/batches/")) {
            return "batch_ai";
        }
        return "general";
    }

    private String resolveClientKey(HttpServletRequest request) {
        String forwardedFor = request.getHeader("X-Forwarded-For");
        if (StringUtils.hasText(forwardedFor)) {
            return forwardedFor.split(",")[0].trim();
        }
        String realIp = request.getHeader("X-Real-IP");
        if (StringUtils.hasText(realIp)) {
            return realIp.trim();
        }
        return String.valueOf(request.getRemoteAddr());
    }

    public record RateLimitSnapshot(long windowSeconds, long requests, double qps) {
    }

}
