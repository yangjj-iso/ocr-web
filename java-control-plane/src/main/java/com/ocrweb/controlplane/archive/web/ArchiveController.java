package com.ocrweb.controlplane.archive.web;

import com.ocrweb.controlplane.archive.dto.ArchiveDtos;
import com.ocrweb.controlplane.archive.service.ArchiveRecordService;
import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.auth.service.CurrentUser;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.file.Path;
import java.util.Map;

@RestController
@RequestMapping("/api/ocr")
public class ArchiveController {
    private final ArchiveRecordService archiveRecordService;
    private final AuthService authService;

    public ArchiveController(ArchiveRecordService archiveRecordService, AuthService authService) {
        this.archiveRecordService = archiveRecordService;
        this.authService = authService;
    }

    @GetMapping("/scan-folder")
    public ArchiveDtos.FolderScanResponse scanFolder(@RequestParam String path, HttpServletRequest request) {
        authService.requireOperatorOrAdmin(request);
        return archiveRecordService.scanFolder(path);
    }

    @GetMapping("/archive-records")
    public ArchiveDtos.ArchiveRecordListResponse listArchiveRecords(
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(required = false) String batchId,
            @RequestParam(name = "batch_id", required = false) String legacyBatchId,
            @RequestParam(required = false) Integer page,
            @RequestParam(name = "pageSize", required = false) Integer pageSize,
            @RequestParam(name = "page_size", required = false) Integer legacyPageSize,
            HttpServletRequest request
    ) {
        String tenantId = resolveTenantId(request);
        return archiveRecordService.listRecords(
                folder,
                firstText(batchId, legacyBatchId),
                page == null ? 1 : page,
                firstPositive(pageSize, legacyPageSize, 200),
                tenantId
        );
    }

    @GetMapping("/archive-records/export")
    public ResponseEntity<Resource> exportArchiveRecords(
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(required = false) String batchId,
            @RequestParam(name = "batch_id", required = false) String legacyBatchId,
            HttpServletRequest request
    ) {
        CurrentUser user = authService.requireOperatorOrAdmin(request);
        Path filePath = archiveRecordService.exportRecords(folder, firstText(batchId, legacyBatchId), user.effectiveTenantId());
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                .body(new FileSystemResource(filePath));
    }

    @PostMapping("/archive-records/import-excel")
    public Map<String, Object> importArchiveRecords(
            @RequestBody ArchiveDtos.ImportArchiveRequest request,
            HttpServletRequest servletRequest
    ) {
        CurrentUser user = authService.requireOperatorOrAdmin(servletRequest);
        int imported = archiveRecordService.importRecords(request.filePath(), request.batchId(), user.effectiveTenantId());
        return Map.of("imported", imported, "file_path", request.filePath());
    }

    @DeleteMapping("/archive-records")
    public Map<String, Object> deleteArchiveRecords(
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(required = false) String batchId,
            @RequestParam(name = "batch_id", required = false) String legacyBatchId,
            HttpServletRequest request
    ) {
        CurrentUser user = authService.requireOperatorOrAdmin(request);
        return Map.of("deleted", archiveRecordService.deleteRecords(folder, firstText(batchId, legacyBatchId), user.effectiveTenantId()));
    }

    @GetMapping("/storage-tree")
    public ArchiveDtos.StorageTreeResponse getStorageTree(HttpServletRequest request) {
        CurrentUser user = authService.requireOperatorOrAdmin(request);
        return archiveRecordService.getStorageTree(user.effectiveTenantId());
    }

    @GetMapping("/storage-tree/records")
    public ArchiveDtos.StoragePathRecordsResponse getStorageTreeRecords(@RequestParam String path, HttpServletRequest request) {
        CurrentUser user = authService.requireOperatorOrAdmin(request);
        return archiveRecordService.getRecordsByStoragePath(path, user.effectiveTenantId());
    }

    @PutMapping("/archive-records/batch-update")
    public ArchiveDtos.BatchUpdateResponse batchUpdateArchiveRecords(
            @RequestBody ArchiveDtos.BatchUpdateRequest request,
            HttpServletRequest servletRequest
    ) {
        CurrentUser user = authService.requireOperatorOrAdmin(servletRequest);
        int updated = archiveRecordService.batchUpdateRecords(request, user.effectiveTenantId());
        return new ArchiveDtos.BatchUpdateResponse(updated);
    }

    @PostMapping("/folders/ensure-batch")
    public Map<String, Object> ensureFolderBatch(
            @Valid @RequestBody ArchiveDtos.EnsureFolderBatchRequest request,
            HttpServletRequest servletRequest
    ) {
        CurrentUser user = authService.requireOperatorOrAdmin(servletRequest);
        return archiveRecordService.ensureBatchForFolder(request.folder(), user.effectiveTenantId());
    }

    private String resolveTenantId(HttpServletRequest request) {
        CurrentUser user = authService.resolveAuthenticatedUser(request);
        return user != null ? user.effectiveTenantId() : "default";
    }

    private static String firstText(String preferred, String legacy) {
        if (StringUtils.hasText(preferred)) {
            return preferred.trim();
        }
        if (StringUtils.hasText(legacy)) {
            return legacy.trim();
        }
        return "";
    }

    private static int firstPositive(Integer preferred, Integer legacy, int defaultValue) {
        if (preferred != null && preferred > 0) {
            return preferred;
        }
        if (legacy != null && legacy > 0) {
            return legacy;
        }
        return defaultValue;
    }
}
