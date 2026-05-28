package com.ocrweb.controlplane.task.web;

import com.ocrweb.controlplane.task.service.TaskSseService;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

/**
 * SSE endpoint for real-time task progress streaming.
 * <p>
 * Clients connect via GET /api/ocr/tasks/events/stream and receive events
 * as the Python compute worker reports progress back through the internal callback API.
 * <p>
 * Query parameters:
 * <ul>
 *   <li>{@code taskIds} — optional comma-separated task IDs to subscribe to</li>
 *   <li>{@code batchId} — optional batch ID to subscribe to all tasks in a batch</li>
 * </ul>
 * If neither is provided, the client receives events for all tasks.
 */
@RestController
@RequestMapping("/api/ocr/tasks")
public class TaskSseController {

    private final TaskSseService sseService;

    public TaskSseController(TaskSseService sseService) {
        this.sseService = sseService;
    }

    @GetMapping(value = "/events/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamEvents(
            @RequestParam(required = false) List<Long> taskIds,
            @RequestParam(required = false) String batchId
    ) {
        SseEmitter emitter = new SseEmitter(TaskSseService.getEmitterTimeoutMs());
        sseService.register(emitter, taskIds, batchId);
        return emitter;
    }
}
