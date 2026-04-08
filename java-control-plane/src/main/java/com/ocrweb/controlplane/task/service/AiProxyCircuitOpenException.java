package com.ocrweb.controlplane.task.service;

public class AiProxyCircuitOpenException extends RuntimeException {
    public AiProxyCircuitOpenException(String message) {
        super(message);
    }
}
