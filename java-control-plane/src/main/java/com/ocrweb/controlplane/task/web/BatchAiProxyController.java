package com.ocrweb.controlplane.task.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.task.service.AiProxyService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/ocr")
public class BatchAiProxyController {
    private final AiProxyService aiProxyService;
    private final AuthService authService;

    public BatchAiProxyController(AiProxyService aiProxyService, AuthService authService) {
        this.aiProxyService = aiProxyService;
        this.authService = authService;
    }

    @PostMapping("/batches/{batchId}/ai-merge-extract")
    public ResponseEntity<JsonNode> aiMergeExtractBatch(
            @PathVariable String batchId,
            @RequestBody(required = false) JsonNode requestBody,
            HttpServletRequest request
    ) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonPost(aiProxyService.batchAiMergeExtractPath(batchId), requestBody, request);
    }

    @GetMapping("/batches/{batchId}/evaluation-truth")
    public ResponseEntity<JsonNode> getBatchEvaluationTruth(@PathVariable String batchId, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonGet(aiProxyService.batchEvaluationTruthPath(batchId), request);
    }

    @GetMapping("/batches/{batchId}/ai-merge-export")
    public ResponseEntity<byte[]> exportBatchMergeExcel(@PathVariable String batchId, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyBinaryGet(aiProxyService.batchAiMergeExportPath(batchId), request);
    }

    @PutMapping("/batches/{batchId}/evaluation-truth")
    public ResponseEntity<JsonNode> putBatchEvaluationTruth(
            @PathVariable String batchId,
            @RequestBody(required = false) JsonNode requestBody,
            HttpServletRequest request
    ) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonPut(aiProxyService.batchEvaluationTruthPath(batchId), requestBody, request);
    }

    @GetMapping("/batches/{batchId}/evaluation-metrics")
    public ResponseEntity<JsonNode> getBatchEvaluationMetrics(@PathVariable String batchId, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonGet(aiProxyService.batchEvaluationMetricsPath(batchId), request);
    }

    @GetMapping("/batches/{batchId}/evaluation-report")
    public ResponseEntity<JsonNode> getBatchEvaluationReport(@PathVariable String batchId, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonGet(aiProxyService.batchEvaluationReportPath(batchId), request);
    }

    @GetMapping("/batches/{batchId}/boundary-analysis")
    public ResponseEntity<JsonNode> getBatchBoundaryAnalysis(@PathVariable String batchId, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonGet(aiProxyService.batchBoundaryAnalysisPath(batchId), request);
    }

    @GetMapping("/batches/{batchId}/boundary-truth")
    public ResponseEntity<JsonNode> getBatchBoundaryTruth(@PathVariable String batchId, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonGet(aiProxyService.batchBoundaryTruthPath(batchId), request);
    }

    @PutMapping("/batches/{batchId}/boundary-truth")
    public ResponseEntity<JsonNode> putBatchBoundaryTruth(
            @PathVariable String batchId,
            @RequestBody(required = false) JsonNode requestBody,
            HttpServletRequest request
    ) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonPut(aiProxyService.batchBoundaryTruthPath(batchId), requestBody, request);
    }

    @PostMapping("/batches/{batchId}/qa")
    public ResponseEntity<JsonNode> askBatchQuestion(
            @PathVariable String batchId,
            @RequestBody(required = false) JsonNode requestBody,
            HttpServletRequest request
    ) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonPost(aiProxyService.batchQaPath(batchId), requestBody, request);
    }

    @GetMapping("/batches/{batchId}/qa/history")
    public ResponseEntity<JsonNode> getBatchQaHistory(@PathVariable String batchId, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonGet(aiProxyService.batchQaHistoryPath(batchId), request);
    }

    @PostMapping("/batches/{batchId}/qa/{qaId}/feedback")
    public ResponseEntity<JsonNode> submitBatchQaFeedback(
            @PathVariable String batchId,
            @PathVariable Long qaId,
            @RequestBody(required = false) JsonNode requestBody,
            HttpServletRequest request
    ) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonPost(aiProxyService.batchQaFeedbackPath(batchId, qaId), requestBody, request);
    }

    @GetMapping("/batches/{batchId}/qa/metrics")
    public ResponseEntity<JsonNode> getBatchQaMetrics(@PathVariable String batchId, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return aiProxyService.proxyJsonGet(aiProxyService.batchQaMetricsPath(batchId), request);
    }
}
