package com.ocrweb.controlplane.auth.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.auth.domain.OperationLogEntity;
import com.ocrweb.controlplane.auth.repository.OperationLogRepository;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class OperationLogService {
    private final OperationLogRepository operationLogRepository;
    private final ObjectMapper objectMapper;

    public OperationLogService(OperationLogRepository operationLogRepository, ObjectMapper objectMapper) {
        this.operationLogRepository = operationLogRepository;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> listLogs(Long userId, String actionType, int limit, int offset) {
        int pageSize = Math.max(1, Math.min(limit, 1000));
        int page = Math.max(0, offset / pageSize);
        PageRequest pageable = PageRequest.of(page, pageSize);
        Page<OperationLogEntity> result;
        if (userId != null && actionType != null && !actionType.isBlank()) {
            result = operationLogRepository.findByUserIdAndActionTypeOrderByCreatedAtDesc(userId, actionType, pageable);
        } else if (userId != null) {
            result = operationLogRepository.findByUserIdOrderByCreatedAtDesc(userId, pageable);
        } else if (actionType != null && !actionType.isBlank()) {
            result = operationLogRepository.findByActionTypeOrderByCreatedAtDesc(actionType, pageable);
        } else {
            result = operationLogRepository.findAll(pageable);
        }

        List<Map<String, Object>> items = result.getContent().stream().map(this::toPayload).toList();
        return Map.of("items", items, "total", result.getTotalElements());
    }

    public void writeLog(CurrentUser currentUser, HttpServletRequest request, String actionType, String resourceType, String resourceId, Map<String, Object> detail) {
        OperationLogEntity entity = new OperationLogEntity();
        entity.setUserId(currentUser == null ? null : currentUser.userId());
        entity.setUsername(currentUser == null ? "" : currentUser.username());
        entity.setActionType(actionType);
        entity.setResourceType(resourceType);
        entity.setResourceId(resourceId);
        entity.setDetailJson(detailToJson(detail));
        entity.setIpAddress(resolveIp(request));
        operationLogRepository.save(entity);
    }

    private Map<String, Object> toPayload(OperationLogEntity entity) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("id", entity.getId());
        payload.put("user_id", entity.getUserId());
        payload.put("username", entity.getUsername());
        payload.put("action_type", entity.getActionType());
        payload.put("resource_type", entity.getResourceType());
        payload.put("resource_id", entity.getResourceId());
        payload.put("detail", entity.getDetailJson() == null ? Map.of() : objectMapper.convertValue(entity.getDetailJson(), Map.class));
        payload.put("ip_address", entity.getIpAddress());
        payload.put("created_at", entity.getCreatedAt());
        return payload;
    }

    private JsonNode detailToJson(Map<String, Object> detail) {
        return objectMapper.valueToTree(detail == null ? Map.of() : detail);
    }

    private String resolveIp(HttpServletRequest request) {
        if (request == null) return null;
        String forwarded = request.getHeader("x-forwarded-for");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}