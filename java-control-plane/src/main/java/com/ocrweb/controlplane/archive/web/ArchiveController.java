package com.ocrweb.controlplane.archive.web;

import com.ocrweb.controlplane.archive.dto.ArchiveDtos;
import com.ocrweb.controlplane.archive.service.ArchiveRecordService;
import jakarta.validation.Valid;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
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
            @RequestParam(defaultValue = "") String batchId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "200") int pageSize
    ) {
        return archiveRecordService.listRecords(folder, batchId, page, pageSize);
    }

    @GetMapping("/archive-records/export")
    public ResponseEntity<Resource> exportArchiveRecords(
            @RequestParam(defaultValue = "") String folder,
            @RequestParam(defaultValue = "") String batchId
    ) {
        Path filePath = archiveRecordService.exportRecords(folder, batchId);
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
            @RequestParam(defaultValue = "") String batchId
    ) {
        return Map.of("deleted", archiveRecordService.deleteRecords(folder, batchId));
    }

    @PostMapping("/folders/ensure-batch")
    public Map<String, Object> ensureFolderBatch(@Valid @RequestBody ArchiveDtos.EnsureFolderBatchRequest request) {
        return archiveRecordService.ensureBatchForFolder(request.folder());
    }
}
