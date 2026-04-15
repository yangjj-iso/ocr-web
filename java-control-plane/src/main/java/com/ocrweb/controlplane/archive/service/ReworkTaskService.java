package com.ocrweb.controlplane.archive.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.archive.domain.ArchiveRecordEntity;
import com.ocrweb.controlplane.archive.domain.ReworkTaskEntity;
import com.ocrweb.controlplane.archive.dto.ReworkDtos;
import com.ocrweb.controlplane.archive.repository.ArchiveRecordRepository;
import com.ocrweb.controlplane.archive.repository.ReworkTaskRepository;
import com.ocrweb.controlplane.auth.service.CurrentUser;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import jakarta.transaction.Transactional;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.UUID;

import static org.springframework.http.HttpStatus.FORBIDDEN;
import static org.springframework.http.HttpStatus.NOT_FOUND;

@Service
public class ReworkTaskService {
    private final ReworkTaskRepository reworkTaskRepository;
    private final ArchiveRecordRepository archiveRecordRepository;
    private final ObjectMapper objectMapper;

    public ReworkTaskService(
            ReworkTaskRepository reworkTaskRepository,
            ArchiveRecordRepository archiveRecordRepository,
            ObjectMapper objectMapper
    ) {
        this.reworkTaskRepository = reworkTaskRepository;
        this.archiveRecordRepository = archiveRecordRepository;
        this.objectMapper = objectMapper;
    }

    public ReworkDtos.ReworkTaskListResponse listTasks(
            CurrentUser currentUser,
            String status,
            String keyword,
            Boolean mine,
            String reporter,
            int page,
            int pageSize
    ) {
        List<ReworkTaskEntity> tasks = canViewAll(currentUser)
                ? reworkTaskRepository.findAllByOrderByCreatedAtDesc()
                : reworkTaskRepository.findByTenantIdOrderByCreatedAtDesc(currentUser.effectiveTenantId());

        String normalizedStatus = normalizeFilterStatus(status);
        String normalizedKeyword = safe(keyword).toLowerCase(Locale.ROOT);
        String normalizedReporter = safe(reporter).toLowerCase(Locale.ROOT);
        boolean onlyMine = Boolean.TRUE.equals(mine);

        List<ReworkTaskEntity> filtered = tasks.stream()
                .filter(task -> canAccess(currentUser, task))
                .filter(task -> !onlyMine || matchesReporter(task, currentUser))
                .filter(task -> normalizedReporter.isEmpty() || safe(task.getReportedByUsername()).toLowerCase(Locale.ROOT).equals(normalizedReporter))
                .filter(task -> normalizedStatus.isEmpty() || normalizeStatus(task.getStatus()).equals(normalizedStatus))
                .filter(task -> matchesKeyword(task, normalizedKeyword))
                .toList();

        int safePage = Math.max(1, page);
        int safePageSize = Math.max(1, pageSize);
        int fromIndex = Math.min(filtered.size(), (safePage - 1) * safePageSize);
        int toIndex = Math.min(filtered.size(), fromIndex + safePageSize);
        List<ReworkDtos.ReworkTaskResponse> items = filtered.subList(fromIndex, toIndex).stream().map(this::toResponse).toList();
        return new ReworkDtos.ReworkTaskListResponse(filtered.size(), items);
    }

    @Transactional
    public ReworkDtos.ReworkStatusResponse create(CurrentUser currentUser, ReworkDtos.ReworkCreateRequest request) {
        ReworkTaskEntity entity = buildReworkTask(currentUser, request, null, null);
        reworkTaskRepository.save(entity);
        return new ReworkDtos.ReworkStatusResponse(entity.getReworkTaskId(), normalizeStatus(entity.getStatus()), entity.getBatchId());
    }

    @Transactional
    public ReworkDtos.ReworkStatusResponse createFromReleaseDecision(CurrentUser currentUser, OcrTaskEntity task, String reason, JsonNode reworkPayload) {
        ObjectNode payload = reworkPayload != null && reworkPayload.isObject()
                ? (ObjectNode) reworkPayload.deepCopy()
                : objectMapper.createObjectNode();

        ArchiveRecordEntity archiveRecord = archiveRecordRepository.findByTaskId(task.getId()).orElse(null);
        String recordId = firstText(
                readText(payload, "record_id"),
                archiveRecord == null ? "" : String.valueOf(archiveRecord.getId())
        );
        payload.put("record_id", recordId);

        if (!StringUtils.hasText(readText(payload, "description"))) {
            payload.put("description", StringUtils.hasText(reason) ? reason : "人工驳回，待返工处理。");
        }
        if (!StringUtils.hasText(readText(payload, "issue_type"))) {
            payload.put("issue_type", "other");
        }
        if (!StringUtils.hasText(readText(payload, "priority"))) {
            payload.put("priority", "normal");
        }
        if (!StringUtils.hasText(readText(payload, "rework_level"))) {
            payload.put("rework_level", "partial");
        }

        JsonNode affectedScope = payload.get("affected_scope");
        ObjectNode scope = affectedScope != null && affectedScope.isObject()
                ? (ObjectNode) affectedScope.deepCopy()
                : objectMapper.createObjectNode();
        if (StringUtils.hasText(recordId)) {
            scope.put("record_id", recordId);
        }
        scope.put("source_review_task_id", task.getId());
        scope.put("source_review_type", "final_release");
        payload.set("affected_scope", scope);

        ReworkDtos.ReworkCreateRequest request = new ReworkDtos.ReworkCreateRequest(
                recordId,
                task.getBatchId(),
                payload.path("record_version").isInt() ? payload.path("record_version").asInt() : null,
                readText(payload, "issue_type"),
                readText(payload, "description"),
                readText(payload, "priority"),
                readText(payload, "rework_level"),
                scope
        );
        ReworkTaskEntity entity = buildReworkTask(currentUser, request, task.getBatchId(), recordId);
        reworkTaskRepository.save(entity);
        return new ReworkDtos.ReworkStatusResponse(entity.getReworkTaskId(), normalizeStatus(entity.getStatus()), entity.getBatchId());
    }

    public ReworkDtos.ReworkTaskResponse get(CurrentUser currentUser, String taskId) {
        ReworkTaskEntity task = findAccessibleTask(currentUser, taskId);
        return toResponse(task);
    }

    @Transactional
    public ReworkDtos.ReworkStatusResponse accept(CurrentUser currentUser, String taskId) {
        ReworkTaskEntity task = findAccessibleTask(currentUser, taskId);
        ensureManagePermission(currentUser, task);
        ensurePending(task);
        task.setStatus("accepted");
        task.setAcceptedByUserId(currentUser.userId());
        task.setAcceptedByUsername(currentUser.username());
        reworkTaskRepository.save(task);
        return new ReworkDtos.ReworkStatusResponse(task.getReworkTaskId(), normalizeStatus(task.getStatus()), task.getBatchId());
    }

    @Transactional
    public ReworkDtos.ReworkStatusResponse reject(CurrentUser currentUser, String taskId, String reason) {
        ReworkTaskEntity task = findAccessibleTask(currentUser, taskId);
        ensureManagePermission(currentUser, task);
        ensurePending(task);
        task.setStatus("rejected");
        task.setAcceptedByUserId(currentUser.userId());
        task.setAcceptedByUsername(currentUser.username());

        ObjectNode scope = task.getAffectedScopeJson() != null && task.getAffectedScopeJson().isObject()
                ? (ObjectNode) task.getAffectedScopeJson().deepCopy()
                : objectMapper.createObjectNode();
        if (StringUtils.hasText(reason)) {
            scope.put("reject_reason", reason.trim());
        }
        task.setAffectedScopeJson(scope);
        reworkTaskRepository.save(task);
        return new ReworkDtos.ReworkStatusResponse(task.getReworkTaskId(), normalizeStatus(task.getStatus()), task.getBatchId());
    }

    public String findLatestRecordStatus(CurrentUser currentUser, String recordId) {
        if (!StringUtils.hasText(recordId)) {
            return null;
        }
        ReworkTaskEntity task = canViewAll(currentUser)
                ? reworkTaskRepository.findTopByRecordIdOrderByCreatedAtDesc(recordId).orElse(null)
                : reworkTaskRepository.findTopByTenantIdAndRecordIdOrderByCreatedAtDesc(currentUser.effectiveTenantId(), recordId).orElse(null);
        return task == null ? null : normalizeStatus(task.getStatus());
    }

    private ReworkTaskEntity buildReworkTask(CurrentUser currentUser, ReworkDtos.ReworkCreateRequest request, String fallbackBatchId, String fallbackRecordId) {
        String recordId = firstText(request.recordId(), fallbackRecordId);
        String batchId = resolveBatchId(request.batchId(), recordId, fallbackBatchId);
        ObjectNode scope = normalizeScope(request.affectedScope());
        if (StringUtils.hasText(recordId)) {
            scope.put("record_id", recordId);
        }
        scope.put("priority", safeOrDefault(request.priority(), "normal"));

        ReworkTaskEntity entity = new ReworkTaskEntity();
        entity.setReworkTaskId(buildReworkTaskId(batchId));
        entity.setTenantId(currentUser.effectiveTenantId());
        entity.setBatchId(batchId);
        entity.setRecordId(recordId);
        entity.setRecordVersion(request.recordVersion() == null ? 1 : request.recordVersion());
        entity.setIssueType(normalizeIssueType(request.issueType()));
        entity.setDescription(safeOrDefault(request.description(), "问题提报"));
        entity.setPriority(safeOrDefault(request.priority(), "normal"));
        entity.setStatus("pending");
        entity.setReworkLevel(safeOrDefault(request.reworkLevel(), "partial"));
        entity.setAffectedScopeJson(scope);
        entity.setReportedByUserId(currentUser.userId());
        entity.setReportedByUsername(currentUser.username());
        return entity;
    }

    private ReworkTaskEntity findAccessibleTask(CurrentUser currentUser, String taskId) {
        ReworkTaskEntity task = reworkTaskRepository.findById(taskId)
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "返工任务不存在。"));
        if (!canAccess(currentUser, task)) {
            throw new ResponseStatusException(NOT_FOUND, "返工任务不存在。");
        }
        return task;
    }

    private void ensureManagePermission(CurrentUser currentUser, ReworkTaskEntity task) {
        String role = currentUser == null ? "" : currentUser.effectiveRole();
        if (currentUser != null && (currentUser.isAdmin() || "admin".equals(role) || "tenant_admin".equals(role))) {
            if (canViewAll(currentUser) || Objects.equals(task.getTenantId(), currentUser.effectiveTenantId())) {
                return;
            }
        }
        throw new ResponseStatusException(FORBIDDEN, "无权处理返工任务。");
    }

    private void ensurePending(ReworkTaskEntity task) {
        if (!"pending".equals(normalizeStatus(task.getStatus()))) {
            throw new ResponseStatusException(FORBIDDEN, "返工任务当前状态不可处理。");
        }
    }

    private boolean canAccess(CurrentUser currentUser, ReworkTaskEntity task) {
        return currentUser != null && (canViewAll(currentUser) || Objects.equals(task.getTenantId(), currentUser.effectiveTenantId()));
    }

    private boolean canViewAll(CurrentUser currentUser) {
        if (currentUser == null) {
            return false;
        }
        String role = currentUser.effectiveRole();
        return currentUser.isAdmin() || "admin".equals(role) || "tenant_admin".equals(role);
    }

    private boolean matchesReporter(ReworkTaskEntity task, CurrentUser currentUser) {
        if (currentUser == null) {
            return false;
        }
        if (currentUser.userId() != null && Objects.equals(task.getReportedByUserId(), currentUser.userId())) {
            return true;
        }
        return safe(task.getReportedByUsername()).equalsIgnoreCase(safe(currentUser.username()));
    }

    private boolean matchesKeyword(ReworkTaskEntity task, String keyword) {
        if (keyword.isBlank()) {
            return true;
        }
        String haystack = String.join(" ",
                safe(task.getReworkTaskId()),
                safe(task.getRecordId()),
                safe(task.getBatchId()),
                safe(task.getDescription())
        ).toLowerCase(Locale.ROOT);
        return haystack.contains(keyword);
    }

    private ReworkDtos.ReworkTaskResponse toResponse(ReworkTaskEntity task) {
        return new ReworkDtos.ReworkTaskResponse(
                task.getReworkTaskId(),
                task.getReworkTaskId(),
                task.getRecordId(),
                task.getBatchId(),
                task.getIssueType(),
                safeOrDefault(task.getPriority(), "normal"),
                normalizeStatus(task.getStatus()),
                task.getCreatedAt(),
                task.getDescription(),
                task.getReportedByUsername(),
                task.getAffectedScopeJson()
        );
    }

    private String resolveBatchId(String requestedBatchId, String recordId, String fallbackBatchId) {
        String batchId = safe(requestedBatchId);
        if (StringUtils.hasText(batchId)) {
            return batchId;
        }
        if (StringUtils.hasText(recordId)) {
            ArchiveRecordEntity record = findArchiveRecord(recordId);
            if (record != null && StringUtils.hasText(record.getBatchId())) {
                return record.getBatchId().trim();
            }
        }
        if (StringUtils.hasText(fallbackBatchId)) {
            return fallbackBatchId.trim();
        }
        return "record_" + (StringUtils.hasText(recordId) ? recordId : UUID.randomUUID().toString().substring(0, 8));
    }

    private ArchiveRecordEntity findArchiveRecord(String recordId) {
        if (!StringUtils.hasText(recordId)) {
            return null;
        }
        if (recordId.chars().allMatch(Character::isDigit)) {
            return archiveRecordRepository.findById(Long.parseLong(recordId)).orElse(null);
        }
        return archiveRecordRepository.findByArchiveNo(recordId).orElse(null);
    }

    private ObjectNode normalizeScope(JsonNode rawScope) {
        if (rawScope != null && rawScope.isObject()) {
            return (ObjectNode) rawScope.deepCopy();
        }
        ObjectNode scope = objectMapper.createObjectNode();
        if (rawScope != null && !rawScope.isNull()) {
            scope.put("label", rawScope.asText(""));
        }
        return scope;
    }

    private String buildReworkTaskId(String batchId) {
        String safeBatchId = safe(batchId).replaceAll("[^A-Za-z0-9_-]", "_");
        if (safeBatchId.isBlank()) {
            safeBatchId = "batch";
        }
        return "rw_" + safeBatchId + "_" + UUID.randomUUID().toString().replace("-", "").substring(0, 8);
    }

    private String normalizeIssueType(String issueType) {
        String normalized = safe(issueType).toLowerCase(Locale.ROOT);
        return switch (normalized) {
            case "boundary_error", "missing_page" -> "boundary";
            case "metadata_error" -> "metadata";
            case "ordering_error" -> "ordering";
            case "pdf_quality" -> "other";
            case "boundary", "metadata", "ordering", "other" -> normalized;
            default -> normalized.isBlank() ? "other" : normalized;
        };
    }

    private String normalizeFilterStatus(String status) {
        String normalized = safe(status).toLowerCase(Locale.ROOT);
        return switch (normalized) {
            case "processing", "pending", "rejected", "done" -> normalized;
            default -> "";
        };
    }

    private String normalizeStatus(String status) {
        String normalized = safe(status).toLowerCase(Locale.ROOT);
        if (normalized.equals("accepted") || normalized.equals("in_rework")) {
            return "processing";
        }
        if (normalized.equals("rejected")) {
            return "rejected";
        }
        if (normalized.equals("done")) {
            return "done";
        }
        return "pending";
    }

    private static String readText(JsonNode payload, String field) {
        return payload == null ? "" : safe(payload.path(field).asText(""));
    }

    private static String firstText(String primary, String fallback) {
        return StringUtils.hasText(primary) ? primary.trim() : safe(fallback);
    }

    private static String safeOrDefault(String value, String fallback) {
        String trimmed = safe(value);
        return trimmed.isBlank() ? fallback : trimmed;
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }
}