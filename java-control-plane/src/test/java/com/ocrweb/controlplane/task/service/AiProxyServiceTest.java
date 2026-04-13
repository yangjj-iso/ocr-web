package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.config.AiServiceProperties;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.mock.web.MockHttpServletRequest;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

class AiProxyServiceTest {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void proxyJsonPostNormalizesJsonContentTypeWhenUpstreamReturnsTextPlain() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/api/ocr/tasks/21/ai-extract-fields", exchange -> {
            byte[] responseBody = "{\"status\":\"ok\",\"detail\":\"proxied\"}".getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add(HttpHeaders.CONTENT_TYPE, "text/plain;charset=utf-8");
            exchange.sendResponseHeaders(200, responseBody.length);
            exchange.getResponseBody().write(responseBody);
            exchange.close();
        });
        server.start();

        try {
            AiServiceProperties properties = new AiServiceProperties();
            properties.setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
            AiProxyService service = new AiProxyService(
                    properties,
                    objectMapper,
                    new AiProxyCircuitBreaker(properties)
            );

            MockHttpServletRequest request = new MockHttpServletRequest();
            request.setMethod("POST");
            request.setRequestURI("/api/ocr/tasks/21/ai-extract-fields");

            ResponseEntity<JsonNode> response = service.proxyJsonPost(
                    "/api/ocr/tasks/21/ai-extract-fields",
                    objectMapper.createObjectNode(),
                    request
            );

            assertThat(response.getStatusCode().value()).isEqualTo(200);
            assertThat(response.getHeaders().getContentType()).isEqualTo(MediaType.APPLICATION_JSON);
            assertThat(response.getBody()).isNotNull();
            assertThat(response.getBody().path("status").asText()).isEqualTo("ok");
            assertThat(response.getBody().path("detail").asText()).isEqualTo("proxied");
        } finally {
            server.stop(0);
        }
    }
}
