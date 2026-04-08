package com.ocrweb.controlplane.task.domain;

public enum OcrTaskStatus {
    PENDING,
    QUEUED,
    WORKER_ACCEPTED,
    RUNNING,
    HUMAN_REVIEW,
    COMPLETED,
    FAILED
}
