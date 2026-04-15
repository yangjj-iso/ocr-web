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

    public record ArchiveDocUnitResponse(
            String id,
            String docId,
            String title,
            Integer sortIndex,
            Integer startPage,
            Integer endPage,
            Integer pageCount,
            String status,
            String previewUrl,
            String pdfUrl
    ) {
    }

    public record ArchiveVersionResponse(
            Long id,
            Integer versionNo,
            String versionType,
            OffsetDateTime createdAt
    ) {
    }

    public record ArchiveRecordDetailResponse(
            Long id,
            String recordId,
            Long taskId,
            String batchId,
            String batchFolder,
            String archiveNo,
            String docNo,
            String responsible,
            String title,
            String date,
            String preservationPeriod,
            String classification,
            String remarks,
            String storagePath,
            Integer pageCount,
            String status,
            String pdfUrl,
            String fileUrl,
            String lastReworkStatus,
            List<ArchiveDocUnitResponse> docUnits,
            List<ArchiveVersionResponse> versions,
            OffsetDateTime createdAt
    ) {
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

    public record BatchUpdateRequest(
            List<Long> ids,
            String responsible,
            String classification,
            String remarks,
            String date,
            @JsonAlias("storage_path") String storagePath
    ) {
    }

    public record BatchUpdateResponse(int updated) {
    }

    public record PageFile(
            Long taskId,
            String filename,
            String status,
            String fileType
    ) {
    }

    public record StoragePathRecordsResponse(
            int recordCount,
            List<ArchiveRecordResponse> records,
            List<PageFile> pageFiles
    ) {
    }

    public record StorageTreeNode(
            String name,
            String path,
            String type,
            int recordCount,
            List<StorageTreeNode> children
    ) {
    }

    public record StorageTreeResponse(
            List<StorageTreeNode> tree,
            int totalPaths,
            int totalRecords
    ) {
    }
}
