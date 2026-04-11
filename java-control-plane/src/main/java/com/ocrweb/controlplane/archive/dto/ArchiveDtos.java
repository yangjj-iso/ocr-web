package com.ocrweb.controlplane.archive.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import jakarta.validation.constraints.NotBlank;

import java.time.OffsetDateTime;
import java.util.List;

public final class ArchiveDtos {
    private ArchiveDtos() {
    }

    public record ArchiveRecordResponse(
            Long id,
            Long taskId,
            String batchId,
            String batchFolder,
            String archiveNo,
            String docNo,
            String responsible,
            String title,
            String date,
            String pages,
            String classification,
            String remarks,
            String storagePath,
            OffsetDateTime createdAt
    ) {
    }

    public record ArchiveRecordListResponse(long total, List<ArchiveRecordResponse> records) {
    }

    public record ImportArchiveRequest(
            @JsonAlias("file_path") String filePath,
            @JsonAlias("batch_id") String batchId
    ) {
    }

    public record EnsureFolderBatchRequest(@NotBlank String folder) {
    }

    public record FolderScanFile(
            String name,
            String path,
            String relPath,
            long size
    ) {
    }

    public record FolderScanResponse(
            String folder,
            int count,
            List<FolderScanFile> files
    ) {
    }
}
