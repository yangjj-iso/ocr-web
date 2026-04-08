package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.config.AiServiceProperties;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class AiProxyService {
    private static final Set<String> RESPONSE_HEADERS_TO_SKIP = Set.of(
            "connection",
            "content-length",
            "host",
            "keep-alive",
            "transfer-encoding"
    );

    private final AiServiceProperties aiServiceProperties;
    private final ObjectMapper objectMapper;
    private final AiProxyCircuitBreaker circuitBreaker;
    private final HttpClient httpClient;

    public AiProxyService(
            AiServiceProperties aiServiceProperties,
            ObjectMapper objectMapper,
            AiProxyCircuitBreaker circuitBreaker
    ) {
        this.aiServiceProperties = aiServiceProperties;
        this.objectMapper = objectMapper;
        this.circuitBreaker = circuitBreaker;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(Math.max(1, aiServiceProperties.getConnectTimeoutSeconds())))
                .build();
    }

    public ResponseEntity<byte[]> proxyBinaryGet(String path, HttpServletRequest incomingRequest) {
        HttpRequest request = baseRequest(path, incomingRequest)
                .GET()
                .build();
        HttpResponse<byte[]> response = sendBytes(request);
        return ResponseEntity.status(response.statusCode())
                .headers(extractHeaders(response))
                .body(response.body());
    }

    public ResponseEntity<JsonNode> proxyJsonGet(String path, HttpServletRequest incomingRequest) {
        HttpRequest request = baseRequest(path, incomingRequest)
                .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .GET()
                .build();
        HttpResponse<byte[]> response = sendBytes(request);
        return jsonResponse(response);
    }

    public ResponseEntity<JsonNode> proxyJsonPost(String path, JsonNode payload, HttpServletRequest incomingRequest) {
        return proxyJsonWithBody("POST", path, payload, incomingRequest);
    }

    public ResponseEntity<JsonNode> proxyJsonPut(String path, JsonNode payload, HttpServletRequest incomingRequest) {
        return proxyJsonWithBody("PUT", path, payload, incomingRequest);
    }

    private ResponseEntity<JsonNode> proxyJsonWithBody(String method, String path, JsonNode payload, HttpServletRequest incomingRequest) {
        JsonNode safePayload = payload == null ? objectMapper.createObjectNode() : payload;
        HttpRequest request;
        try {
            HttpRequest.Builder builder = baseRequest(path, incomingRequest)
                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                    .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE);
            String body = objectMapper.writeValueAsString(safePayload);
            if ("PUT".equalsIgnoreCase(method)) {
                request = builder.PUT(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8)).build();
            } else {
                request = builder.POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8)).build();
            }
        } catch (IOException error) {
            throw new IllegalStateException("Failed to serialize AI proxy payload.", error);
        }
        HttpResponse<byte[]> response = sendBytes(request);
        return jsonResponse(response);
    }

    private ResponseEntity<JsonNode> jsonResponse(HttpResponse<byte[]> response) {
        return ResponseEntity.status(response.statusCode())
                .headers(extractHeaders(response))
                .body(parseJson(response.body()));
    }

    private HttpHeaders extractHeaders(HttpResponse<byte[]> response) {
        HttpHeaders headers = new HttpHeaders();
        for (Map.Entry<String, List<String>> entry : response.headers().map().entrySet()) {
            if (RESPONSE_HEADERS_TO_SKIP.contains(entry.getKey().toLowerCase())) {
                continue;
            }
            headers.put(entry.getKey(), entry.getValue());
        }
        return headers;
    }

    private JsonNode parseJson(byte[] body) {
        if (body == null || body.length == 0) {
            return objectMapper.createObjectNode();
        }
        try {
            return objectMapper.readTree(body);
        } catch (IOException error) {
            ObjectNode fallback = objectMapper.createObjectNode();
            fallback.put("detail", new String(body, StandardCharsets.UTF_8));
            return fallback;
        }
    }

    private HttpResponse<byte[]> sendBytes(HttpRequest request) {
        circuitBreaker.beforeRequest();
        try {
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
            if (response.statusCode() >= 500) {
                circuitBreaker.recordFailure();
            } else {
                circuitBreaker.recordSuccess();
            }
            return response;
        } catch (HttpTimeoutException error) {
            circuitBreaker.recordFailure();
            throw new AiProxyTimeoutException("AI proxy request timed out.", error);
        } catch (IOException error) {
            circuitBreaker.recordFailure();
            throw new AiProxyException("AI proxy request failed.", error);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            circuitBreaker.recordFailure();
            throw new AiProxyException("AI proxy request interrupted.", error);
        }
    }

    private HttpRequest.Builder baseRequest(String path, HttpServletRequest incomingRequest) {
        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(resolveUri(path, incomingRequest))
                .timeout(Duration.ofSeconds(Math.max(1, aiServiceProperties.getReadTimeoutSeconds())));
        forwardIfPresent(incomingRequest, builder, HttpHeaders.AUTHORIZATION);
        forwardIfPresent(incomingRequest, builder, HttpHeaders.COOKIE);
        forwardIfPresent(incomingRequest, builder, "X-Trace-Id");
        return builder;
    }

    private static void forwardIfPresent(HttpServletRequest incomingRequest, HttpRequest.Builder builder, String headerName) {
        String value = incomingRequest.getHeader(headerName);
        if (value != null && !value.isBlank()) {
            builder.header(headerName, value);
        }
    }

    public String taskPageImagePath(Long taskId, Integer pageNum) {
        return "/api/ocr/tasks/" + taskId + "/pages/" + pageNum + "/image";
    }

    public String taskThumbnailPath(Long taskId) {
        return "/api/ocr/tasks/" + taskId + "/thumbnail";
    }

    public String taskExtractFieldsPath(Long taskId) {
        return "/api/ocr/tasks/" + taskId + "/extract-fields";
    }

    public String taskAiExtractFieldsPath(Long taskId) {
        return "/api/ocr/tasks/" + taskId + "/ai-extract-fields";
    }

    public String batchAiMergeExtractPath(String batchId) {
        return batchPath(batchId, "/ai-merge-extract");
    }

    public String batchEvaluationTruthPath(String batchId) {
        return batchPath(batchId, "/evaluation-truth");
    }

    public String batchEvaluationMetricsPath(String batchId) {
        return batchPath(batchId, "/evaluation-metrics");
    }

    public String batchEvaluationReportPath(String batchId) {
        return batchPath(batchId, "/evaluation-report");
    }

    public String batchBoundaryAnalysisPath(String batchId) {
        return batchPath(batchId, "/boundary-analysis");
    }

    public String batchBoundaryTruthPath(String batchId) {
        return batchPath(batchId, "/boundary-truth");
    }

    public String batchQaPath(String batchId) {
        return batchPath(batchId, "/qa");
    }

    public String batchQaHistoryPath(String batchId) {
        return batchPath(batchId, "/qa/history");
    }

    public String batchQaFeedbackPath(String batchId, Long qaId) {
        return batchPath(batchId, "/qa/" + qaId + "/feedback");
    }

    public String batchQaMetricsPath(String batchId) {
        return batchPath(batchId, "/qa/metrics");
    }

    private String batchPath(String batchId, String suffix) {
        return "/api/ocr/batches/" + encodeSegment(batchId) + suffix;
    }

    private URI resolveUri(String path, HttpServletRequest incomingRequest) {
        String baseUrl = aiServiceProperties.getBaseUrl();
        if (baseUrl.endsWith("/")) {
            baseUrl = baseUrl.substring(0, baseUrl.length() - 1);
        }
        String normalizedPath = path.startsWith("/") ? path : "/" + path;
        String queryString = incomingRequest == null ? null : incomingRequest.getQueryString();
        return URI.create(baseUrl + normalizedPath + (queryString == null || queryString.isBlank() ? "" : "?" + queryString));
    }

    private static String encodeSegment(String segment) {
        return URLEncoder.encode(segment, StandardCharsets.UTF_8).replace("+", "%20");
    }
}
