package com.ocrweb.controlplane.task.service;

public class AiProxyTimeoutException extends AiProxyException {
    public AiProxyTimeoutException(String message, Throwable cause) {
        super(message, cause);
    }
}
