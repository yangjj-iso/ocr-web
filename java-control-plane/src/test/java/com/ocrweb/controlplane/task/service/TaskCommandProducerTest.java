package com.ocrweb.controlplane.task.service;

import com.ocrweb.controlplane.config.InternalApiProperties;
import com.ocrweb.controlplane.config.ProcessingProperties;
import com.ocrweb.controlplane.config.RabbitMqProperties;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.trace.RequestTraceContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
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
        TaskCommandProducer producer = new TaskCommandProducer(
                rabbitTemplate,
                properties,
                internalApiProperties,
                new ProcessingProperties()
        );

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
        verify(rabbitTemplate).convertAndSend(eq("ocr.task.command.exchange"), eq("ocr.task.submit.v1"), payloadCaptor.capture(), any(MessagePostProcessor.class));
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
        TaskCommandProducer producer = new TaskCommandProducer(
                rabbitTemplate,
                properties,
                internalApiProperties,
                new ProcessingProperties()
        );

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
        verify(rabbitTemplate).convertAndSend(eq("ocr.task.command.exchange"), eq("ocr.task.submit.v1"), payloadCaptor.capture(), any(MessagePostProcessor.class));
        Map<String, Object> payload = payloadCaptor.getValue();
        assertThat(payload.get("trace_id")).isEqualTo("trace-request-456");
    }

    @Test
    void publishUsesConfiguredExecutionSettingsAndArchiveDefaults() {
        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        RabbitMqProperties properties = new RabbitMqProperties();
        properties.setExchange("ocr.task.command.exchange");
        properties.setRoutingKey("ocr.task.submit.v1");
        InternalApiProperties internalApiProperties = new InternalApiProperties();
        internalApiProperties.setBaseUrl("http://127.0.0.1:8080");
        ProcessingProperties processingProperties = new ProcessingProperties();
        processingProperties.setLlmBackend("remote");
        processingProperties.setLlmModel("qwen-max");
        processingProperties.setProcessingStrategy("archive_only");
        processingProperties.setGpuProfile("multi_gpu");
        processingProperties.setLanggraphGraph("   ");

        TaskCommandProducer producer = new TaskCommandProducer(
                rabbitTemplate,
                properties,
                internalApiProperties,
                processingProperties
        );

        OcrTaskEntity task = new OcrTaskEntity();
        task.setFilename("sample.pdf");
        task.setFilePath("uploads/source/sample.pdf");
        task.setFileType(".pdf");
        task.setBatchId("batch-2");
        task.setMode("vl");

        producer.publish(task);

        @SuppressWarnings("unchecked")
        var payloadCaptor = org.mockito.ArgumentCaptor.forClass(Map.class);
        verify(rabbitTemplate).convertAndSend(eq("ocr.task.command.exchange"), eq("ocr.task.submit.v1"), payloadCaptor.capture(), any(MessagePostProcessor.class));
        Map<String, Object> payload = payloadCaptor.getValue();

        @SuppressWarnings("unchecked")
        Map<String, Object> execution = (Map<String, Object>) payload.get("execution");
        assertThat(execution.get("mode")).isEqualTo("vl");
        assertThat(execution.get("llm_backend")).isEqualTo("remote");
        assertThat(execution.get("llm_model")).isEqualTo("qwen-max");
        assertThat(execution.get("processing_strategy")).isEqualTo("archive_only");
        assertThat(execution.get("gpu_profile")).isEqualTo("multi_gpu");
        assertThat(execution.get("langgraph_graph")).isEqualTo("archive_main");
        assertThat(execution).doesNotContainKey("enable_hierarchical_agent");
    }

    @Test
    void publishResumeIncludesArchiveExecutionPayload() {
        RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
        RabbitMqProperties properties = new RabbitMqProperties();
        properties.setExchange("ocr.task.command.exchange");
        properties.setRoutingKey("ocr.task.submit.v1");
        InternalApiProperties internalApiProperties = new InternalApiProperties();
        internalApiProperties.setBaseUrl("http://127.0.0.1:8080");
        ProcessingProperties processingProperties = new ProcessingProperties();
        processingProperties.setLanggraphGraph("archive_resume");

        TaskCommandProducer producer = new TaskCommandProducer(
                rabbitTemplate,
                properties,
                internalApiProperties,
                processingProperties
        );

        OcrTaskEntity task = new OcrTaskEntity();
        task.setFilename("sample.jpg");
        task.setFilePath("uploads/source/sample.jpg");
        task.setFileType(".jpg");
        task.setBatchId("batch-3");
        task.setWorkflowThreadId("thread-77");
        task.setMode("unexpected-mode");

        var resumePayload = new com.fasterxml.jackson.databind.ObjectMapper().createObjectNode();
        resumePayload.put("approved", true);

        producer.publishResume(task, resumePayload);

        @SuppressWarnings("unchecked")
        var payloadCaptor = org.mockito.ArgumentCaptor.forClass(Map.class);
        verify(rabbitTemplate).convertAndSend(eq("ocr.task.command.exchange"), eq("ocr.task.submit.v1"), payloadCaptor.capture(), any(MessagePostProcessor.class));
        Map<String, Object> payload = payloadCaptor.getValue();

        assertThat(payload.get("command")).isEqualTo("OCR_TASK_RESUME");
        assertThat(payload.get("workflow_thread_id")).isEqualTo("thread-77");
        assertThat(payload.get("resume_reason")).isEqualTo("human_review_resume");

        @SuppressWarnings("unchecked")
        Map<String, Object> execution = (Map<String, Object>) payload.get("execution");
        assertThat(execution.get("mode")).isEqualTo("layout");
        assertThat(execution.get("langgraph_graph")).isEqualTo("archive_resume");
        assertThat(execution).doesNotContainKey("enable_hierarchical_agent");
    }
}
