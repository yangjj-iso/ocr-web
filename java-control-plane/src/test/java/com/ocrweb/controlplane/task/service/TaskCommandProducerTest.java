package com.ocrweb.controlplane.task.service;

import com.ocrweb.controlplane.config.InternalApiProperties;
import com.ocrweb.controlplane.config.RabbitMqProperties;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.trace.RequestTraceContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

class TaskCommandProducerTest {
    @AfterEach
    void clearTraceContext() {
        RequestTraceContext.clear();
    }

    @Test
    void publishUsesRequestTraceIdWhenPresent() {
        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        RabbitMqProperties properties = new RabbitMqProperties();
        properties.setExchange("ocr.task.command.exchange");
        properties.setRoutingKey("ocr.task.submit.v1");
        InternalApiProperties internalApiProperties = new InternalApiProperties();
        internalApiProperties.setBaseUrl("http://127.0.0.1:8080");
        TaskCommandProducer producer = new TaskCommandProducer(rabbitTemplate, properties, internalApiProperties);

        OcrTaskEntity task = new OcrTaskEntity();
        task.setFilename("sample.jpg");
        task.setFilePath("uploads/source/sample.jpg");
        task.setFileType(".jpg");
        task.setBatchId("batch-1");
        task.setTraceId("trace-task-123");
        task.setStorageProvider("s3");
        task.setStorageBucket("ocr-source");
        task.setStorageObjectKey("uploads/source/sample.jpg");
        task.setFileSha256("abc123");
        task.setFileSizeBytes(128L);

        producer.publish(task);

        @SuppressWarnings("unchecked")
        var payloadCaptor = org.mockito.ArgumentCaptor.forClass(Map.class);
        verify(rabbitTemplate).convertAndSend(eq("ocr.task.command.exchange"), eq("ocr.task.submit.v1"), payloadCaptor.capture());
        Map<String, Object> payload = payloadCaptor.getValue();
        assertThat(payload.get("trace_id")).isEqualTo("trace-task-123");
        @SuppressWarnings("unchecked")
        Map<String, Object> filePayload = (Map<String, Object>) payload.get("file");
        assertThat(String.valueOf(filePayload.get("file_url")))
                .startsWith("http://127.0.0.1:8080/internal/api/v1/ocr/tasks/")
                .endsWith("/source-file");
        assertThat(filePayload.get("storage_provider")).isEqualTo("s3");
        assertThat(filePayload.get("object_key")).isEqualTo("uploads/source/sample.jpg");
        assertThat(filePayload.get("sha256")).isEqualTo("abc123");
    }

    @Test
    void publishFallsBackToCurrentRequestTraceId() {
        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        RabbitMqProperties properties = new RabbitMqProperties();
        properties.setExchange("ocr.task.command.exchange");
        properties.setRoutingKey("ocr.task.submit.v1");
        InternalApiProperties internalApiProperties = new InternalApiProperties();
        internalApiProperties.setBaseUrl("http://127.0.0.1:8080");
        TaskCommandProducer producer = new TaskCommandProducer(rabbitTemplate, properties, internalApiProperties);

        OcrTaskEntity task = new OcrTaskEntity();
        task.setFilename("sample.jpg");
        task.setFilePath("sample.jpg");
        task.setFileType(".jpg");
        task.setBatchId("batch-1");
        task.setStorageProvider("s3");
        task.setStorageBucket("ocr-source");
        task.setStorageObjectKey("uploads/sample.jpg");
        task.setFileSha256("abc456");
        task.setFileSizeBytes(256L);

        RequestTraceContext.setTraceId("trace-request-456");
        producer.publish(task);

        @SuppressWarnings("unchecked")
        var payloadCaptor = org.mockito.ArgumentCaptor.forClass(Map.class);
        verify(rabbitTemplate).convertAndSend(eq("ocr.task.command.exchange"), eq("ocr.task.submit.v1"), payloadCaptor.capture());
        Map<String, Object> payload = payloadCaptor.getValue();
        assertThat(payload.get("trace_id")).isEqualTo("trace-request-456");
    }
}
