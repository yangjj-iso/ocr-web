package com.ocrweb.controlplane.archive.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.ocrweb.controlplane.archive.domain.ArchiveRecordEntity;
import com.ocrweb.controlplane.archive.dto.ArchiveDtos;
import com.ocrweb.controlplane.archive.repository.ArchiveRecordRepository;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import jakarta.transaction.Transactional;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
public class ArchiveRecordService {
    private static final Logger log = LoggerFactory.getLogger(ArchiveRecordService.class);
    private static final List<String> EXPORTED_HEADERS = List.of("档号", "文号", "责任者", "题名", "日期", "页数", "密级", "备注");
    private static final List<String> SCAN_EXTENSIONS = List.of(".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf");
    private static final int MAX_BATCH_ID_LENGTH = 100;
    private static final int MAX_BATCH_FOLDER_LENGTH = 500;
    private static final int MAX_ARCHIVE_NO_LENGTH = 200;
    private static final int MAX_DOC_NO_LENGTH = 200;
    private static final int MAX_RESPONSIBLE_LENGTH = 500;
    private static final int MAX_TITLE_LENGTH = 1000;
    private static final int MAX_DATE_LENGTH = 50;
    private static final int MAX_PAGES_LENGTH = 20;
    private static final int MAX_CLASSIFICATION_LENGTH = 50;
    private static final int MAX_REMARKS_LENGTH = 1000;

    private final ArchiveRecordRepository archiveRecordRepository;
    private final OcrTaskRepository ocrTaskRepository;
    private final PathAccessService pathAccessService;

    public ArchiveRecordService(
            ArchiveRecordRepository archiveRecordRepository,
            OcrTaskRepository ocrTaskRepository,
            PathAccessService pathAccessService
    ) {
        this.archiveRecordRepository = archiveRecordRepository;
        this.ocrTaskRepository = ocrTaskRepository;
        this.pathAccessService = pathAccessService;
    }

    public ArchiveDtos.ArchiveRecordListResponse listRecords(String folder, String batchId, int page, int pageSize) {
        var pageResult = archiveRecordRepository.findByFilters(
                safe(folder),
                safe(batchId),
                PageRequest.of(Math.max(0, page - 1), pageSize)
        );
        return new ArchiveDtos.ArchiveRecordListResponse(
                pageResult.getTotalElements(),
                pageResult.getContent().stream().map(this::toResponse).toList()
        );
    }

    public Path exportRecords(String folder, String batchId) {
        List<ArchiveRecordEntity> records = archiveRecordRepository.findAllByFilters(safe(folder), safe(batchId));
        if (records.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "No archive records found.");
        }
        try {
            Path tempFile = Files.createTempFile("archive-records-", ".xlsx");
            try (Workbook workbook = new XSSFWorkbook(); OutputStream outputStream = Files.newOutputStream(tempFile)) {
                Sheet sheet = workbook.createSheet("archive_records");
                Row headerRow = sheet.createRow(0);
                for (int index = 0; index < EXPORTED_HEADERS.size(); index++) {
                    headerRow.createCell(index).setCellValue(EXPORTED_HEADERS.get(index));
                }
                for (int rowIndex = 0; rowIndex < records.size(); rowIndex++) {
                    ArchiveRecordEntity record = records.get(rowIndex);
                    Row row = sheet.createRow(rowIndex + 1);
                    row.createCell(0).setCellValue(nullSafe(record.getArchiveNo()));
                    row.createCell(1).setCellValue(nullSafe(record.getDocNo()));
                    row.createCell(2).setCellValue(nullSafe(record.getResponsible()));
                    row.createCell(3).setCellValue(nullSafe(record.getTitle()));
                    row.createCell(4).setCellValue(nullSafe(record.getDate()));
                    row.createCell(5).setCellValue(nullSafe(record.getPages()));
                    row.createCell(6).setCellValue(nullSafe(record.getClassification()));
                    row.createCell(7).setCellValue(nullSafe(record.getRemarks()));
                }
                workbook.write(outputStream);
            }
            return tempFile;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to export archive records.", error);
        }
    }

    @Transactional
    public int importRecords(String filePath, String batchId) {
        Path safePath = pathAccessService.ensureAllowedPath(filePath, true, false);
        List<Map<String, String>> rows = readArchiveRows(safePath);
        String resolvedBatchId = StringUtils.hasText(batchId) ? batchId.trim() : "import_" + stripExtension(safePath.getFileName().toString());
        String folder = safePath.getParent() == null ? "" : safePath.getParent().toString();

        for (Map<String, String> row : rows) {
            ArchiveRecordEntity entity = new ArchiveRecordEntity();
            entity.setTaskId(null);
            entity.setBatchId(resolvedBatchId);
            entity.setBatchFolder(folder);
            entity.setArchiveNo(row.getOrDefault("档号", ""));
            entity.setDocNo(row.getOrDefault("文号", ""));
            entity.setResponsible(row.getOrDefault("责任者", ""));
            entity.setTitle(row.getOrDefault("题名", ""));
            entity.setDate(row.getOrDefault("日期", ""));
            entity.setPages(row.getOrDefault("页数", ""));
            entity.setClassification(row.getOrDefault("密级", ""));
            entity.setRemarks(row.getOrDefault("备注", ""));
            applyStorageLimits(entity, "archive import batch " + resolvedBatchId);
            archiveRecordRepository.save(entity);
        }
        return rows.size();
    }

    @Transactional
    public long deleteRecords(String folder, String batchId) {
        String safeFolder = safe(folder);
        String safeBatchId = safe(batchId);
        if (StringUtils.hasText(safeBatchId)) {
            List<ArchiveRecordEntity> records = archiveRecordRepository.findAllByFilters("", safeBatchId);
            archiveRecordRepository.deleteAll(records);
            return records.size();
        }
        if (StringUtils.hasText(safeFolder)) {
            List<ArchiveRecordEntity> records = archiveRecordRepository.findAllByFilters(safeFolder, "");
            archiveRecordRepository.deleteAll(records);
            return records.size();
        }
        long total = archiveRecordRepository.count();
        archiveRecordRepository.deleteAllInBatch();
        return total;
    }

    @Transactional
    public long deleteRecordsByTaskId(Long taskId) {
        if (taskId == null) {
            return 0;
        }
        return archiveRecordRepository.deleteByTaskId(taskId);
    }

    public List<ArchiveRecordEntity> findByTaskIds(List<Long> taskIds) {
        if (taskIds == null || taskIds.isEmpty()) {
            return List.of();
        }
        return archiveRecordRepository.findByTaskIdIn(taskIds);
    }

    public ArchiveDtos.FolderScanResponse scanFolder(String folderPath) {
        Path folder = pathAccessService.ensureAllowedPath(folderPath, false, true);
        List<ArchiveDtos.FolderScanFile> files = new ArrayList<>();
        try (var paths = Files.walk(folder)) {
            paths.filter(Files::isRegularFile)
                    .sorted()
                    .forEach(path -> {
                        String extension = extension(path.getFileName().toString());
                        if (!SCAN_EXTENSIONS.contains(extension)) {
                            return;
                        }
                        try {
                            files.add(new ArchiveDtos.FolderScanFile(
                                    path.getFileName().toString(),
                                    path.toString(),
                                    folder.relativize(path).toString(),
                                    Files.size(path)
                            ));
                        } catch (IOException ignored) {
                        }
                    });
        } catch (IOException error) {
            throw new IllegalStateException("Failed to scan folder.", error);
        }
        return new ArchiveDtos.FolderScanResponse(folder.toString(), files.size(), files);
    }

    @Transactional
    public java.util.Map<String, Object> ensureBatchForFolder(String folder) {
        Path safeFolder = pathAccessService.ensureAllowedPath(folder, false, true);
        String normalizedFolder = safeFolder.toString();

        List<String> existingBatchIds = archiveRecordRepository.findDistinctAssignedBatchIdsByFolder(normalizedFolder);
        String batchId = existingBatchIds.isEmpty()
                ? "batch_" + OffsetDateTime.now().toEpochSecond() + "_" + UUID.randomUUID().toString().substring(0, 6)
                : existingBatchIds.get(0);
        boolean created = existingBatchIds.isEmpty();
        int linkedTasks = 0;

        List<ArchiveRecordEntity> unassignedRecords = archiveRecordRepository.findUnassignedByFolder(normalizedFolder);
        if (!unassignedRecords.isEmpty()) {
            for (ArchiveRecordEntity record : unassignedRecords) {
                record.setBatchId(batchId);
                if (!normalizedFolder.equals(safe(record.getBatchFolder()))) {
                    record.setBatchFolder(normalizedFolder);
                }
            }
            archiveRecordRepository.saveAll(unassignedRecords);
        }

        List<OcrTaskEntity> tasks = ocrTaskRepository.findAll().stream()
                .filter(task -> task.getFilePath() != null && Path.of(task.getFilePath()).toAbsolutePath().normalize().startsWith(safeFolder))
                .toList();
        if (tasks.isEmpty()) {
            return java.util.Map.of("batch_id", "", "created", false, "linked_tasks", 0);
        }

        for (OcrTaskEntity task : tasks) {
            ArchiveRecordEntity record = archiveRecordRepository.findByTaskId(task.getId()).orElseGet(ArchiveRecordEntity::new);
            boolean dirty = false;

            if (!Objects.equals(record.getTaskId(), task.getId())) {
                record.setTaskId(task.getId());
                dirty = true;
            }
            if (!batchId.equals(safe(record.getBatchId()))) {
                record.setBatchId(batchId);
                dirty = true;
            }
            if (!normalizedFolder.equals(safe(record.getBatchFolder()))) {
                record.setBatchFolder(normalizedFolder);
                dirty = true;
            }
            if (!StringUtils.hasText(record.getArchiveNo())) {
                record.setArchiveNo(stripExtension(task.getFilename()));
                dirty = true;
            }
            if (!StringUtils.hasText(record.getPages()) && task.getPageCount() != null) {
                record.setPages(String.valueOf(task.getPageCount()));
                dirty = true;
            }
            dirty = applyStorageLimits(record, "folder batch sync for task " + task.getId()) || dirty;
            if (dirty) {
                archiveRecordRepository.save(record);
            }
            linkedTasks++;
        }
        return java.util.Map.of(
                "batch_id", batchId,
                "created", created,
                "linked_tasks", linkedTasks
        );
    }

    @Transactional
    public void saveArchiveRecordFromTaskCompletion(Long taskId, String batchId, String batchFolder, JsonNode archiveFields) {
        if (taskId == null) {
            return;
        }
        ArchiveRecordEntity record = archiveRecordRepository.findByTaskId(taskId).orElseGet(ArchiveRecordEntity::new);
        record.setTaskId(taskId);
        record.setBatchId(safe(batchId));
        record.setBatchFolder(safe(batchFolder));
        if (archiveFields != null && archiveFields.isObject()) {
            record.setArchiveNo(readText(archiveFields, "archive_no", record.getArchiveNo()));
            record.setDocNo(readText(archiveFields, "doc_no", record.getDocNo()));
            record.setResponsible(readText(archiveFields, "responsible", record.getResponsible()));
            record.setTitle(readText(archiveFields, "title", record.getTitle()));
            record.setDate(readText(archiveFields, "date", record.getDate()));
            record.setPages(readText(archiveFields, "pages", record.getPages()));
            record.setClassification(readText(archiveFields, "classification", record.getClassification()));
            record.setRemarks(readText(archiveFields, "remarks", record.getRemarks()));
        }
        applyStorageLimits(record, "task completion " + taskId);
        archiveRecordRepository.save(record);
    }

    private boolean applyStorageLimits(ArchiveRecordEntity record, String context) {
        boolean changed = false;

        String batchId = limitField("batchId", record.getBatchId(), MAX_BATCH_ID_LENGTH, context);
        if (!Objects.equals(batchId, record.getBatchId())) {
            record.setBatchId(batchId);
            changed = true;
        }

        String batchFolder = limitField("batchFolder", record.getBatchFolder(), MAX_BATCH_FOLDER_LENGTH, context);
        if (!Objects.equals(batchFolder, record.getBatchFolder())) {
            record.setBatchFolder(batchFolder);
            changed = true;
        }

        String archiveNo = limitField("archiveNo", record.getArchiveNo(), MAX_ARCHIVE_NO_LENGTH, context);
        if (!Objects.equals(archiveNo, record.getArchiveNo())) {
            record.setArchiveNo(archiveNo);
            changed = true;
        }

        String docNo = limitField("docNo", record.getDocNo(), MAX_DOC_NO_LENGTH, context);
        if (!Objects.equals(docNo, record.getDocNo())) {
            record.setDocNo(docNo);
            changed = true;
        }

        String responsible = limitField("responsible", record.getResponsible(), MAX_RESPONSIBLE_LENGTH, context);
        if (!Objects.equals(responsible, record.getResponsible())) {
            record.setResponsible(responsible);
            changed = true;
        }

        String title = limitField("title", record.getTitle(), MAX_TITLE_LENGTH, context);
        if (!Objects.equals(title, record.getTitle())) {
            record.setTitle(title);
            changed = true;
        }

        String date = limitField("date", record.getDate(), MAX_DATE_LENGTH, context);
        if (!Objects.equals(date, record.getDate())) {
            record.setDate(date);
            changed = true;
        }

        String pages = limitField("pages", record.getPages(), MAX_PAGES_LENGTH, context);
        if (!Objects.equals(pages, record.getPages())) {
            record.setPages(pages);
            changed = true;
        }

        String classification = limitField("classification", record.getClassification(), MAX_CLASSIFICATION_LENGTH, context);
        if (!Objects.equals(classification, record.getClassification())) {
            record.setClassification(classification);
            changed = true;
        }

        String remarks = limitField("remarks", record.getRemarks(), MAX_REMARKS_LENGTH, context);
        if (!Objects.equals(remarks, record.getRemarks())) {
            record.setRemarks(remarks);
            changed = true;
        }

        return changed;
    }

    private List<Map<String, String>> readArchiveRows(Path filePath) {
        try (InputStream inputStream = Files.newInputStream(filePath); Workbook workbook = WorkbookFactory.create(inputStream)) {
            Sheet sheet = workbook.getSheetAt(0);
            int headerRowIndex = -1;
            List<String> headers = List.of();
            for (int rowIndex = 0; rowIndex < Math.min(6, sheet.getLastRowNum() + 1); rowIndex++) {
                Row row = sheet.getRow(rowIndex);
                if (row == null) {
                    continue;
                }
                List<String> values = readRowValues(row, 9);
                if (values.contains("档号") || values.contains("文号")) {
                    headerRowIndex = rowIndex;
                    headers = values;
                    break;
                }
            }
            if (headerRowIndex < 0) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Could not find the header row in the workbook.");
            }

            List<Map<String, String>> rows = new ArrayList<>();
            for (int rowIndex = headerRowIndex + 1; rowIndex <= sheet.getLastRowNum(); rowIndex++) {
                Row row = sheet.getRow(rowIndex);
                if (row == null) {
                    continue;
                }
                java.util.LinkedHashMap<String, String> values = new java.util.LinkedHashMap<>();
                boolean hasAny = false;
                for (int cellIndex = 0; cellIndex < headers.size(); cellIndex++) {
                    String header = headers.get(cellIndex);
                    if (!StringUtils.hasText(header)) {
                        continue;
                    }
                    String value = readCell(row.getCell(cellIndex));
                    if (StringUtils.hasText(value)) {
                        hasAny = true;
                    }
                    values.put(header, value);
                }
                if (hasAny) {
                    rows.add(values);
                }
            }
            return rows;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to import archive records.", error);
        }
    }

    private List<String> readRowValues(Row row, int maxCells) {
        List<String> values = new ArrayList<>();
        for (int cellIndex = 0; cellIndex < maxCells; cellIndex++) {
            values.add(readCell(row.getCell(cellIndex)));
        }
        return values;
    }

    private String readCell(Cell cell) {
        if (cell == null) {
            return "";
        }
        return switch (cell.getCellType()) {
            case STRING -> safe(cell.getStringCellValue());
            case NUMERIC -> {
                double value = cell.getNumericCellValue();
                long integer = (long) value;
                yield value == integer ? Long.toString(integer) : Double.toString(value);
            }
            case BOOLEAN -> Boolean.toString(cell.getBooleanCellValue());
            case FORMULA -> safe(cell.getCellFormula());
            default -> "";
        };
    }

    private ArchiveDtos.ArchiveRecordResponse toResponse(ArchiveRecordEntity entity) {
        return new ArchiveDtos.ArchiveRecordResponse(
                entity.getId(),
                entity.getTaskId(),
                entity.getBatchId(),
                entity.getBatchFolder(),
                entity.getArchiveNo(),
                entity.getDocNo(),
                entity.getResponsible(),
                entity.getTitle(),
                entity.getDate(),
                entity.getPages(),
                entity.getClassification(),
                entity.getRemarks(),
                entity.getStoragePath(),
                entity.getCreatedAt()
        );
    }

    private static String readText(JsonNode payload, String field, String fallback) {
        String value = payload.path(field).asText("");
        return StringUtils.hasText(value) ? value : fallback;
    }

    private static String limitField(String fieldName, String value, int maxLength, String context) {
        String normalized = safe(value);
        if (normalized.length() <= maxLength) {
            return normalized;
        }
        String truncated = truncate(normalized, maxLength);
        log.warn(
                "Truncated archive record field '{}' from {} to {} characters while saving {}.",
                fieldName,
                normalized.length(),
                truncated.length(),
                context
        );
        return truncated;
    }

    private static String truncate(String value, int maxLength) {
        if (maxLength <= 0) {
            return "";
        }
        if (value.length() <= maxLength) {
            return value;
        }
        if (maxLength <= 3) {
            return value.substring(0, maxLength);
        }
        return value.substring(0, maxLength - 3) + "...";
    }

    private static String normalizeTaskStatus(String status) {
        if (status == null) {
            return "";
        }
        return status.trim().toLowerCase(Locale.ROOT);
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private static String extension(String filename) {
        int index = filename == null ? -1 : filename.lastIndexOf('.');
        return index >= 0 ? filename.substring(index).toLowerCase(Locale.ROOT) : "";
    }

    private static String stripExtension(String filename) {
        int index = filename == null ? -1 : filename.lastIndexOf('.');
        return index >= 0 ? filename.substring(0, index) : filename;
    }

    private static String nullSafe(String value) {
        return value == null ? "" : value;
    }
}
