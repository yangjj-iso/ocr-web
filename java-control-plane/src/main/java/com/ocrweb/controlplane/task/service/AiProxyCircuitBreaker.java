package com.ocrweb.controlplane.task.service;

import com.ocrweb.controlplane.config.AiServiceProperties;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

@Component
public class AiProxyCircuitBreaker {
    private final AiServiceProperties aiServiceProperties;
    private final AtomicInteger consecutiveFailures = new AtomicInteger(0);
    private final AtomicReference<Instant> openUntil = new AtomicReference<>(Instant.EPOCH);

    public AiProxyCircuitBreaker(AiServiceProperties aiServiceProperties) {
        this.aiServiceProperties = aiServiceProperties;
    }

    public void beforeRequest() {
        Instant until = openUntil.get();
        if (until != null && Instant.now().isBefore(until)) {
            throw new AiProxyCircuitOpenException("AI proxy circuit is temporarily open.");
        }
    }

    public void recordSuccess() {
        consecutiveFailures.set(0);
        openUntil.set(Instant.EPOCH);
    }

    public void recordFailure() {
        int failures = consecutiveFailures.incrementAndGet();
        if (failures >= Math.max(1, aiServiceProperties.getCircuitFailureThreshold())) {
            openUntil.set(Instant.now().plusSeconds(Math.max(1, aiServiceProperties.getCircuitOpenSeconds())));
            consecutiveFailures.set(0);
        }
    }

    public boolean isOpen() {
        Instant until = openUntil.get();
        return until != null && Instant.now().isBefore(until);
    }

    public Instant getOpenUntil() {
        return openUntil.get();
    }
}
