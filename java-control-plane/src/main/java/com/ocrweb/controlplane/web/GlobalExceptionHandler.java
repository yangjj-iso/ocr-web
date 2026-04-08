package com.ocrweb.controlplane.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.task.service.AiProxyCircuitOpenException;
import com.ocrweb.controlplane.task.service.AiProxyException;
import com.ocrweb.controlplane.task.service.AiProxyTimeoutException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

import java.nio.file.NoSuchFileException;
import java.util.NoSuchElementException;

@RestControllerAdvice
public class GlobalExceptionHandler {
    private final ObjectMapper objectMapper;

    public GlobalExceptionHandler(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @ExceptionHandler(NoSuchElementException.class)
    public ResponseEntity<ObjectNode> handleNotFound(NoSuchElementException error) {
        return build(HttpStatus.NOT_FOUND, "Resource not found.");
    }

    @ExceptionHandler(NoSuchFileException.class)
    public ResponseEntity<ObjectNode> handleMissingFile(NoSuchFileException error) {
        return build(HttpStatus.NOT_FOUND, "Task file not found.");
    }

    @ExceptionHandler(AiProxyCircuitOpenException.class)
    public ResponseEntity<ObjectNode> handleAiCircuitOpen(AiProxyCircuitOpenException error) {
        return build(HttpStatus.SERVICE_UNAVAILABLE, error.getMessage());
    }

    @ExceptionHandler(AiProxyTimeoutException.class)
    public ResponseEntity<ObjectNode> handleAiTimeout(AiProxyTimeoutException error) {
        return build(HttpStatus.GATEWAY_TIMEOUT, error.getMessage());
    }

    @ExceptionHandler(AiProxyException.class)
    public ResponseEntity<ObjectNode> handleAiProxy(AiProxyException error) {
        return build(HttpStatus.BAD_GATEWAY, error.getMessage());
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<ObjectNode> handleResponseStatus(ResponseStatusException error) {
        String detail = error.getReason() == null || error.getReason().isBlank()
                ? error.getMessage()
                : error.getReason();
        return build(HttpStatus.valueOf(error.getStatusCode().value()), detail);
    }

    private ResponseEntity<ObjectNode> build(HttpStatus status, String detail) {
        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("detail", detail);
        return ResponseEntity.status(status).body(payload);
    }
}
