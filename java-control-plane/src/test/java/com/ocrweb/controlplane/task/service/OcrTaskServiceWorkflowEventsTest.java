package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.archive.service.ArchiveRecordService;
import com.ocrweb.controlplane.archive.service.ReworkTaskService;
import com.ocrweb.controlplane.auth.service.UserQuotaService;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.domain.TaskCallbackEventEntity;
import com.ocrweb.controlplane.task.dto.TaskDtos;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import com.ocrweb.controlplane.task.repository.TaskCallbackEventRepository;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OcrTaskServiceWorkflowEventsTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final OcrTaskRepository taskRepository = mock(OcrTaskRepository.class);
    private final TaskCallbackEventRepository callbackEventRepository = mock(TaskCallbackEventRepository.class);
    private final TaskStorageService storageService = mock(TaskStorageService.class);
    private final TaskCommandProducer taskCommandProducer = mock(TaskCommandProducer.class);
    private final ArchiveRecordService archiveRecordService = mock(ArchiveRecordService.class);
        private final ReworkTaskService reworkTaskService = mock(ReworkTaskService.class);
    private final UserQuotaService userQuotaService = mock(UserQuotaService.class);

    private final OcrTaskService service = new OcrTaskService(
            taskRepository,
            callbackEventRepository,
            storageService,
            taskCommandProducer,
            archiveRecordService,
            reworkTaskService,
            userQuotaService,
            objectMapper
    );

    @Test
    void handleEventPersistsWorkflowThreadIdFromPayload() {
        OcrTaskEntity task = new OcrTaskEntity();
        task.setStatus("pending");
        when(callbackEventRepository.existsByEventId("event-1")).thenReturn(false);
        when(taskRepository.findById(7L)).thenReturn(Optional.of(task));

        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("workflow_thread_id", "thread-123");
        TaskDtos.TaskEventRequest request = new TaskDtos.TaskEventRequest(
                "v1",
                "event-1",
                "trace-1",
                7L,
                "batch-1",
                "NODE_ENTER",
                "2026-04-10T00:00:00Z",
                new TaskDtos.CallbackWorker("worker-1", "localhost", "queue", 0),
                new TaskDtos.CallbackProgress(1, 3, 33.3),
                payload
        );

        service.handleEvent(7L, request);

        assertThat(task.getWorkflowThreadId()).isEqualTo("thread-123");
        assertThat(task.getStatus()).isEqualTo("processing");
        verify(callbackEventRepository).save(any(TaskCallbackEventEntity.class));
        verify(taskRepository).save(task);
    }

    @Test
    void getWorkflowEventsReturnsMappedPayloadAndFallbackThreadId() throws Exception {
        OcrTaskEntity task = new OcrTaskEntity();
        setEntityId(task, 7L);
        task.setFilename("sample.pdf");
        task.setMode("layout");
        task.setStatus("processing");
        task.setWorkflowThreadId("");
        when(taskRepository.findById(7L)).thenReturn(Optional.of(task));

        ObjectNode innerPayload = objectMapper.createObjectNode();
        innerPayload.put("workflow_thread_id", "thread-123");
        innerPayload.put("graph_id", "archive_main");
        innerPayload.put("node_id", "node_prepare_batch");
        ObjectNode progress = objectMapper.createObjectNode();
        progress.put("currentPage", 1);
        progress.put("totalPages", 2);
        progress.put("percent", 50.0);
        ObjectNode callbackPayload = objectMapper.createObjectNode();
        callbackPayload.put("eventId", "event-2");
        callbackPayload.put("occurredAt", "2026-04-10T00:00:01Z");
        callbackPayload.set("payload", innerPayload);
        callbackPayload.set("progress", progress);

        TaskCallbackEventEntity event = new TaskCallbackEventEntity();
        event.setTaskId(7L);
        event.setEventId("event-2");
        event.setEventType("NODE_EXIT");
        event.setPayloadJson(callbackPayload);
        event.setCreatedAt(OffsetDateTime.parse("2026-04-10T00:00:02Z"));
        when(callbackEventRepository.findByTaskIdOrderByCreatedAtAscIdAsc(7L)).thenReturn(List.of(event));

        TaskDtos.WorkflowEventsResponse response = service.getWorkflowEvents(7L);

        assertThat(response.taskId()).isEqualTo(7L);
        assertThat(response.workflowThreadId()).isEqualTo("thread-123");
        assertThat(response.taskStatus()).isEqualTo("processing");
        assertThat(response.events()).hasSize(1);
        assertThat(response.events().get(0).eventType()).isEqualTo("NODE_EXIT");
        assertThat(response.events().get(0).payload().path("graph_id").asText()).isEqualTo("archive_main");
        assertThat(response.events().get(0).progress().path("currentPage").asInt()).isEqualTo(1);
    }

    private static void setEntityId(OcrTaskEntity task, Long value) throws Exception {
        Field field = OcrTaskEntity.class.getDeclaredField("id");
        field.setAccessible(true);
        field.set(task, value);
    }
}
