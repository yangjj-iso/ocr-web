package com.ocrweb.controlplane.health;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.config.AiServiceProperties;
import com.ocrweb.controlplane.task.service.AiProxyCircuitBreaker;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

import javax.sql.DataSource;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ControlPlaneHealthServiceTest {
    private HttpServer server;

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void readinessIsUpWhenDependenciesAreAvailable() throws Exception {
        startServer(200, "{\"status\":\"ok\",\"service\":\"ai-document-service\"}");

        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(2)).thenReturn(true);

        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        when(rabbitTemplate.execute(any())).thenReturn(true);

        AiServiceProperties aiServiceProperties = new AiServiceProperties();
        aiServiceProperties.setBaseUrl("http://127.0.0.1:" + server.getAddress().getPort());
        aiServiceProperties.setHealthPath("/api/health");
        aiServiceProperties.setConnectTimeoutSeconds(2);
        aiServiceProperties.setReadTimeoutSeconds(2);

        AiProxyCircuitBreaker circuitBreaker = mock(AiProxyCircuitBreaker.class);
        when(circuitBreaker.isOpen()).thenReturn(false);

        ControlPlaneHealthService service = new ControlPlaneHealthService(
                dataSource,
                rabbitTemplate,
                aiServiceProperties,
                circuitBreaker,
                new ObjectMapper(),
                HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build()
        );

        ControlPlaneHealthService.ReadinessReport report = service.readiness();
        assertThat(report.ready()).isTrue();
        assertThat(report.payload()).containsEntry("status", "UP");
        @SuppressWarnings("unchecked")
        Map<String, Object> components = (Map<String, Object>) report.payload().get("components");
        assertThat(components).containsKeys("database", "rabbitmq", "ai_service");
        assertThat(((Map<?, ?>) components.get("ai_service")).get("status")).isEqualTo("UP");
    }

    @Test
    void readinessIsDownWhenAiCircuitIsOpen() throws Exception {
        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);
        when(dataSource.getConnection()).thenReturn(connection);
        when(connection.isValid(2)).thenReturn(true);

        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        when(rabbitTemplate.execute(any())).thenReturn(true);

        AiServiceProperties aiServiceProperties = new AiServiceProperties();
        aiServiceProperties.setBaseUrl("http://127.0.0.1:8001");

        AiProxyCircuitBreaker circuitBreaker = mock(AiProxyCircuitBreaker.class);
        when(circuitBreaker.isOpen()).thenReturn(true);
        when(circuitBreaker.getOpenUntil()).thenReturn(Instant.parse("2026-04-09T04:30:00Z"));

        ControlPlaneHealthService service = new ControlPlaneHealthService(
                dataSource,
                rabbitTemplate,
                aiServiceProperties,
                circuitBreaker,
                new ObjectMapper(),
                HttpClient.newHttpClient()
        );

        ControlPlaneHealthService.ReadinessReport report = service.readiness();
        assertThat(report.ready()).isFalse();
        assertThat(report.payload()).containsEntry("status", "DOWN");
        @SuppressWarnings("unchecked")
        Map<String, Object> components = (Map<String, Object>) report.payload().get("components");
        assertThat(((Map<?, ?>) components.get("ai_service")).get("status")).isEqualTo("DOWN");
    }

    private void startServer(int statusCode, String body) throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/api/health", exchange -> writeJson(exchange, statusCode, body));
        server.start();
    }

    private static void writeJson(HttpExchange exchange, int statusCode, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(statusCode, bytes.length);
        try (OutputStream outputStream = exchange.getResponseBody()) {
            outputStream.write(bytes);
        } finally {
            exchange.close();
        }
    }
}
