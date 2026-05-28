package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.stream.Collectors;

/**
 * Manages Server-Sent Event (SSE) connections for real-time task progress push.
 * <p>
 * Clients subscribe via {@link #register(SseEmitter, List, String)} and receive
 * broadcasts whenever the Python compute worker sends callback events.
 */
@Service
public class TaskSseService {
    private static final Logger logger = LoggerFactory.getLogger(TaskSseService.class);
    private static final long EMITTER_TIMEOUT_MS = 300_000L; // 5 minutes

    private final CopyOnWriteArrayList<SseSubscription> subscriptions = new CopyOnWriteArrayList<>();
    private final ObjectMapper objectMapper;

    public TaskSseService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    /**
     * Register a new SSE emitter that will receive events for the given task IDs or batch.
     */
    public void register(SseEmitter emitter, List<Long> taskIds, String batchId) {
        emitter.onCompletion(() -> removeByEmitter(emitter));
        emitter.onTimeout(() -> removeByEmitter(emitter));
        emitter.onError(ex -> removeByEmitter(emitter));

        Set<Long> taskIdSet = taskIds == null ? Set.of() : taskIds.stream().collect(Collectors.toSet());
        String safeBatchId = batchId == null ? "" : batchId.trim();

        SseSubscription subscription = new SseSubscription(emitter, taskIdSet, safeBatchId);
        subscriptions.add(subscription);

        // Send initial connection event
        try {
            ObjectNode connectPayload = objectMapper.createObjectNode();
            connectPayload.put("type", "CONNECTED");
            connectPayload.put("subscribedTaskIds", taskIdSet.toString());
            connectPayload.put("subscribedBatchId", safeBatchId);
            emitter.send(SseEmitter.event()
                    .name("CONNECTED")
                    .data(connectPayload.toString()));
        } catch (IOException e) {
            removeByEmitter(emitter);
        }

        logger.debug("SSE client registered: taskIds={}, batchId={}, total_subscriptions={}",
                taskIdSet, safeBatchId, subscriptions.size());
    }

    /**
     * Broadcast an event to all subscribed SSE clients matching the given taskId or batchId.
     */
    public void broadcast(Long taskId, String batchId, String eventType, Object data) {
        if (subscriptions.isEmpty()) {
            return;
        }

        String safeBatchId = batchId == null ? "" : batchId.trim();
        String jsonData;
        try {
            jsonData = objectMapper.writeValueAsString(data);
        } catch (Exception e) {
            logger.warn("Failed to serialize SSE event data for taskId={}: {}", taskId, e.getMessage());
            return;
        }

        for (SseSubscription subscription : subscriptions) {
            if (!subscription.matches(taskId, safeBatchId)) {
                continue;
            }
            try {
                subscription.emitter().send(SseEmitter.event()
                        .name(eventType)
                        .data(jsonData));
            } catch (IOException e) {
                removeByEmitter(subscription.emitter());
            }
        }
    }

    /**
     * Periodic heartbeat to keep SSE connections alive through proxies and load balancers.
     */
    @Scheduled(fixedRate = 30_000)
    public void heartbeat() {
        if (subscriptions.isEmpty()) {
            return;
        }
        for (SseSubscription subscription : subscriptions) {
            try {
                subscription.emitter().send(SseEmitter.event().comment("heartbeat"));
            } catch (IOException e) {
                removeByEmitter(subscription.emitter());
            }
        }
    }

    /**
     * Returns the number of active SSE subscriptions (useful for monitoring).
     */
    public int getActiveSubscriptionCount() {
        return subscriptions.size();
    }

    public static long getEmitterTimeoutMs() {
        return EMITTER_TIMEOUT_MS;
    }

    private void removeByEmitter(SseEmitter emitter) {
        subscriptions.removeIf(sub -> sub.emitter() == emitter);
    }

    private record SseSubscription(SseEmitter emitter, Set<Long> taskIds, String batchId) {
        boolean matches(Long taskId, String eventBatchId) {
            // If subscription has specific task IDs, check membership
            if (!taskIds.isEmpty() && taskId != null && taskIds.contains(taskId)) {
                return true;
            }
            // If subscription has a batch ID filter, check match
            if (!batchId.isEmpty() && batchId.equals(eventBatchId)) {
                return true;
            }
            // If subscription has no filters (subscribes to all), match everything
            return taskIds.isEmpty() && batchId.isEmpty();
        }
    }
}
