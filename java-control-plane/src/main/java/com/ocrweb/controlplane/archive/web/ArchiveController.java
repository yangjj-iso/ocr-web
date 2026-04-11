package com.ocrweb.controlplane.archive.web;

import com.ocrweb.controlplane.archive.dto.ArchiveDtos;
import com.ocrweb.controlplane.archive.service.ArchiveRecordService;
import jakarta.validation.Valid;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
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

    public ArchiveController(ArchiveRecordService archiveRecordService) {
        this.archiveRecordService = archiveRecordService;
    }

    @GetMapping("/scan-folder")
    public ArchiveDtos.FolderScanResponse scanFolder(@RequestParam String path) {
        return archiveRecordService.scanFolder(path);
    }

    @GetMapping("/archive-records")
    public ArchiveDtos.ArchiveRecordListResponse listArchiveRecords(
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(required = false) String batchId,
            @RequestParam(name = "batch_id", required = false) String legacyBatchId,
            @RequestParam(required = false) Integer page,
            @RequestParam(name = "pageSize", required = false) Integer pageSize,
            @RequestParam(name = "page_size", required = false) Integer legacyPageSize
    ) {
        return archiveRecordService.listRecords(
                folder,
                firstText(batchId, legacyBatchId),
                page == null ? 1 : page,
                firstPositive(pageSize, legacyPageSize, 200)
        );
    }

    @GetMapping("/archive-records/export")
    public ResponseEntity<Resource> exportArchiveRecords(
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(required = false) String batchId,
            @RequestParam(name = "batch_id", required = false) String legacyBatchId
    ) {
        Path filePath = archiveRecordService.exportRecords(folder, firstText(batchId, legacyBatchId));
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                .body(new FileSystemResource(filePath));
    }

    @PostMapping("/archive-records/import-excel")
    public Map<String, Object> importArchiveRecords(@RequestBody ArchiveDtos.ImportArchiveRequest request) {
        int imported = archiveRecordService.importRecords(request.filePath(), request.batchId());
        return Map.of("imported", imported, "file_path", request.filePath());
    }

    @DeleteMapping("/archive-records")
    public Map<String, Object> deleteArchiveRecords(
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(required = false) String batchId,
            @RequestParam(name = "batch_id", required = false) String legacyBatchId
    ) {
        return Map.of("deleted", archiveRecordService.deleteRecords(folder, firstText(batchId, legacyBatchId)));
    }

    @PostMapping("/folders/ensure-batch")
    public Map<String, Object> ensureFolderBatch(@Valid @RequestBody ArchiveDtos.EnsureFolderBatchRequest request) {
        return archiveRecordService.ensureBatchForFolder(request.folder());
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
