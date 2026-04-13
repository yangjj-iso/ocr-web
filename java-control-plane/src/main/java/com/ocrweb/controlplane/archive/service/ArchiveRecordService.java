package com.ocrweb.controlplane.archive.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.ocrweb.controlplane.archive.domain.ArchiveRecordEntity;
import com.ocrweb.controlplane.archive.dto.ArchiveDtos;
import com.ocrweb.controlplane.archive.repository.ArchiveRecordRepository;
import com.ocrweb.controlplane.auth.service.CurrentUser;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import com.ocrweb.controlplane.task.service.TaskStorageService;
import jakarta.transaction.Transactional;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
public class ArchiveRecordService {
    private static final Logger log = LoggerFactory.getLogger(ArchiveRecordService.class);
    private static final List<String> EXPORTED_HEADERS = List.of("档号", "文号", "责任者", "题名", "日期", "页数", "密级", "存放路径", "备注");
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
    private static final int MAX_STORAGE_PATH_LENGTH = 1000;
    private static final int MAX_REMARKS_LENGTH = 1000;

    private final ArchiveRecordRepository archiveRecordRepository;
    private final OcrTaskRepository ocrTaskRepository;
    private final PathAccessService pathAccessService;
    private final ReworkTaskService reworkTaskService;
    private final TaskStorageService taskStorageService;

    public ArchiveRecordService(
            ArchiveRecordRepository archiveRecordRepository,
            OcrTaskRepository ocrTaskRepository,
            PathAccessService pathAccessService,
            ReworkTaskService reworkTaskService,
            TaskStorageService taskStorageService
    ) {
        this.archiveRecordRepository = archiveRecordRepository;
        this.ocrTaskRepository = ocrTaskRepository;
        this.pathAccessService = pathAccessService;
        this.reworkTaskService = reworkTaskService;
        this.taskStorageService = taskStorageService;
    }

    public ArchiveDtos.ArchiveRecordListResponse listRecords(
            String folder,
            String batchId,
            String keyword,
            String dateFrom,
            String dateTo,
            int page,
            int pageSize,
            String tenantId
    ) {
        List<ArchiveRecordEntity> filtered = archiveRecordRepository.findAllByTenantIdAndFilters(
                        safe(tenantId, "default"),
                        safe(folder),
                        safe(batchId)
                ).stream()
                .filter(record -> matchesKeyword(record, keyword))
                .filter(record -> matchesDateRange(record, dateFrom, dateTo))
                .sorted(Comparator.comparing(ArchiveRecordEntity::getCreatedAt, Comparator.nullsLast(Comparator.naturalOrder())))
                .toList();

        int safePage = Math.max(1, page);
        int safePageSize = Math.max(1, pageSize);
        int fromIndex = Math.min(filtered.size(), (safePage - 1) * safePageSize);
        int toIndex = Math.min(filtered.size(), fromIndex + safePageSize);
        return new ArchiveDtos.ArchiveRecordListResponse(
                filtered.size(),
                filtered.subList(fromIndex, toIndex).stream().map(this::toResponse).toList()
        );
    }

    /** Backwards-compatible overload without tenant isolation. */
    public ArchiveDtos.ArchiveRecordListResponse listRecords(String folder, String batchId, int page, int pageSize) {
        return listRecords(folder, batchId, "", "", "", page, pageSize, "default");
    }

    public ArchiveDtos.ArchiveRecordDetailResponse getRecordDetail(String recordKey, CurrentUser currentUser) {
        ArchiveRecordEntity record = findRecord(recordKey, currentUser.effectiveTenantId());
        OcrTaskEntity task = findTask(record, currentUser.effectiveTenantId());
        String pdfUrl = task == null ? "" : "/api/archive-control/archive-records/" + record.getId() + "/pdf";
        String fileUrl = task == null ? "" : "/api/ocr/tasks/" + task.getId() + "/file";
        int pageCount = resolvePageCount(record, task);
        String title = firstText(record.getTitle(), task == null ? "" : stripExtension(task.getFilename()));
        String lastReworkStatus = reworkTaskService.findLatestRecordStatus(currentUser, String.valueOf(record.getId()));
        return new ArchiveDtos.ArchiveRecordDetailResponse(
                record.getId(),
                String.valueOf(record.getId()),
                record.getTaskId(),
                record.getBatchId(),
                record.getBatchFolder(),
                record.getArchiveNo(),
                record.getDocNo(),
                record.getResponsible(),
                title,
                record.getDate(),
                "",
                record.getClassification(),
                record.getRemarks(),
                record.getStoragePath(),
                pageCount,
                "archived",
                pdfUrl,
                fileUrl,
                safe(lastReworkStatus),
                buildDocUnits(record, title, pageCount, pdfUrl),
                List.of(),
                record.getCreatedAt()
        );
    }

    public TaskStorageService.StoredFileResource getArchiveRecordPdfResource(String recordKey, CurrentUser currentUser) throws IOException {
        ArchiveRecordEntity record = findRecord(recordKey, currentUser.effectiveTenantId());
        OcrTaskEntity task = findTask(record, currentUser.effectiveTenantId());
        if (task == null || !isPdfTask(task)) {
            return null;
        }
        return taskStorageService.loadTaskResource(task);
    }

    public Path exportRecords(String folder, String batchId, String tenantId) {
        List<ArchiveRecordEntity> records = archiveRecordRepository.findAllByTenantIdAndFilters(safe(tenantId, "default"), safe(folder), safe(batchId));
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
                    row.createCell(7).setCellValue(nullSafe(record.getStoragePath()));
                    row.createCell(8).setCellValue(nullSafe(record.getRemarks()));
                }
                workbook.write(outputStream);
            }
            return tempFile;
        } catch (IOException error) {
            throw new IllegalStateException("Failed to export archive records.", error);
        }
    }

    @Transactional
    public int importRecords(String filePath, String batchId, String tenantId) {
        Path safePath = pathAccessService.ensureAllowedPath(filePath, true, false);
        List<Map<String, String>> rows = readArchiveRows(safePath);
        String resolvedBatchId = StringUtils.hasText(batchId) ? batchId.trim() : "import_" + stripExtension(safePath.getFileName().toString());
        String folder = safePath.getParent() == null ? "" : safePath.getParent().toString();
        String effectiveTenant = safe(tenantId, "default");

        for (Map<String, String> row : rows) {
            ArchiveRecordEntity entity = new ArchiveRecordEntity();
            entity.setTaskId(null);
            entity.setBatchId(resolvedBatchId);
            entity.setBatchFolder(folder);
            entity.setTenantId(effectiveTenant);
            entity.setArchiveNo(row.getOrDefault("档号", ""));
            entity.setDocNo(row.getOrDefault("文号", ""));
            entity.setResponsible(row.getOrDefault("责任者", ""));
            entity.setTitle(row.getOrDefault("题名", ""));
            entity.setDate(row.getOrDefault("日期", ""));
            entity.setPages(row.getOrDefault("页数", ""));
            entity.setClassification(row.getOrDefault("密级", ""));
            entity.setStoragePath(row.getOrDefault("存放路径", ""));
            entity.setRemarks(row.getOrDefault("备注", ""));
            applyStorageLimits(entity, "archive import batch " + resolvedBatchId);
            archiveRecordRepository.save(entity);
        }
        return rows.size();
    }

    @Transactional
    public long deleteRecords(String folder, String batchId, String tenantId) {
        String safeFolder = safe(folder);
        String safeBatchId = safe(batchId);
        String effectiveTenant = safe(tenantId, "default");
        if (StringUtils.hasText(safeBatchId)) {
            List<ArchiveRecordEntity> records = archiveRecordRepository.findAllByTenantIdAndFilters(effectiveTenant, "", safeBatchId);
            archiveRecordRepository.deleteAll(records);
            return records.size();
        }
        if (StringUtils.hasText(safeFolder)) {
            List<ArchiveRecordEntity> records = archiveRecordRepository.findAllByTenantIdAndFilters(effectiveTenant, safeFolder, "");
            archiveRecordRepository.deleteAll(records);
            return records.size();
        }
        List<ArchiveRecordEntity> records = archiveRecordRepository.findByTenantId(effectiveTenant);
        archiveRecordRepository.deleteAll(records);
        return records.size();
    }

    /** Backwards-compatible overload without tenant isolation. */
    @Transactional
    public long deleteRecords(String folder, String batchId) {
        return deleteRecords(folder, batchId, "default");
    }

    @Transactional
    public long deleteRecordsByTaskId(Long taskId) {
        if (taskId == null) {
            return 0;
        }
        return archiveRecordRepository.deleteByTaskId(taskId);
    }

    @Transactional
    public int batchUpdateRecords(ArchiveDtos.BatchUpdateRequest request, String tenantId) {
        if (request.ids() == null || request.ids().isEmpty()) {
            return 0;
        }
        String effectiveTenant = safe(tenantId, "default");
        List<ArchiveRecordEntity> records = archiveRecordRepository.findAllById(request.ids());
        int updated = 0;
        for (ArchiveRecordEntity record : records) {
            if (!effectiveTenant.equals(record.getTenantId())) {
                continue;
            }
            boolean dirty = false;
            if (request.responsible() != null) {
                record.setResponsible(request.responsible());
                dirty = true;
            }
            if (request.classification() != null) {
                record.setClassification(request.classification());
                dirty = true;
            }
            if (request.remarks() != null) {
                record.setRemarks(request.remarks());
                dirty = true;
            }
            if (request.date() != null) {
                record.setDate(request.date());
                dirty = true;
            }
            if (request.storagePath() != null) {
                record.setStoragePath(request.storagePath());
                dirty = true;
            }
            if (dirty) {
                applyStorageLimits(record, "batch update record " + record.getId());
                archiveRecordRepository.save(record);
                updated++;
            }
        }
        return updated;
    }

    public ArchiveDtos.StorageTreeResponse getStorageTree(String tenantId) {
        String effectiveTenant = safe(tenantId, "default");
        // 1. Paths from archive records
        List<String> archivePaths = archiveRecordRepository.findDistinctStoragePathsByTenantId(effectiveTenant);
        Map<String, List<String>> parentToChildren = new java.util.LinkedHashMap<>();
        Map<String, Integer> pathRecordCounts = new java.util.HashMap<>();
        java.util.Set<String> allLeafPaths = new java.util.LinkedHashSet<>(archivePaths);
        int totalRecords = 0;

        for (String path : archivePaths) {
            int count = archiveRecordRepository.findByTenantIdAndStoragePath(effectiveTenant, path).size();
            pathRecordCounts.put(path, count);
            totalRecords += count;
        }

        // 2. Also derive paths from OCR tasks that have no archive record with storage_path
        // Use lightweight projection to avoid loading full entities with large JSON
        List<Object[]> taskIdFilenames = ocrTaskRepository.findAllIdAndFilename();
        java.util.Set<Long> tasksWithStoragePath = new java.util.HashSet<>();
        for (ArchiveRecordEntity ar : archiveRecordRepository.findByTenantId(effectiveTenant)) {
            if (StringUtils.hasText(ar.getStoragePath()) && ar.getTaskId() != null) {
                tasksWithStoragePath.add(ar.getTaskId());
            }
        }
        Map<String, Integer> taskPathCounts = new java.util.HashMap<>();
        for (Object[] row : taskIdFilenames) {
            Long taskId = (Long) row[0];
            String filename = (String) row[1];
            if (tasksWithStoragePath.contains(taskId)) continue;
            String derived = deriveStoragePathFromFilename(filename);
            if (!StringUtils.hasText(derived)) continue;
            allLeafPaths.add(derived);
            taskPathCounts.merge(derived, 1, Integer::sum);
        }
        for (var e : taskPathCounts.entrySet()) {
            pathRecordCounts.merge(e.getKey(), e.getValue(), Integer::sum);
            totalRecords += e.getValue();
        }

        // 3. Build tree from all paths
        for (String path : allLeafPaths) {
            String[] segments = path.split("/");
            StringBuilder current = new StringBuilder();
            for (int i = 1; i < segments.length; i++) {
                String parent = current.toString();
                current.append("/").append(segments[i]);
                parentToChildren.computeIfAbsent(parent, k -> new ArrayList<>());
                String child = current.toString();
                if (!parentToChildren.get(parent).contains(child)) {
                    parentToChildren.get(parent).add(child);
                }
            }
        }

        List<ArchiveDtos.StorageTreeNode> rootChildren = buildTreeLevel("", parentToChildren, pathRecordCounts, allLeafPaths);
        return new ArchiveDtos.StorageTreeResponse(rootChildren, allLeafPaths.size(), totalRecords);
    }

    static String deriveStoragePathFromFilename(String filename) {
        if (!StringUtils.hasText(filename)) return "";
        // Remove extension: WS·2024·D30-0156-001.jpg → WS·2024·D30-0156-001
        String stem = filename.contains(".") ? filename.substring(0, filename.lastIndexOf('.')) : filename;
        // Remove folder prefix if present: 0311/WS·2024·D10-0311-009 → WS·2024·D10-0311-009
        if (stem.contains("/")) stem = stem.substring(stem.lastIndexOf('/') + 1);
        if (stem.contains("\\")) stem = stem.substring(stem.lastIndexOf('\\') + 1);
        // Normalize separators: replace · with -
        String normalized = stem.replace('·', '-').replace('•', '-').replace('・', '-');
        // Split by - : [WS, 2024, D30, 0156, 001]
        String[] parts = normalized.split("-");
        if (parts.length < 2) return "";
        // Drop the last segment (page number) if it looks like a page number (all digits, ≤ 3 digits)
        int end = parts.length;
        String lastPart = parts[end - 1].trim();
        if (lastPart.matches("\\d{1,3}")) {
            end--;
        }
        if (end < 2) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < end; i++) {
            String p = parts[i].trim();
            if (p.isEmpty()) continue;
            sb.append("/").append(p);
        }
        return sb.toString();
    }

    private List<ArchiveDtos.StorageTreeNode> buildTreeLevel(
            String parentPath,
            Map<String, List<String>> parentToChildren,
            Map<String, Integer> pathRecordCounts,
            java.util.Set<String> leafPaths
    ) {
        List<String> children = parentToChildren.getOrDefault(parentPath, List.of());
        List<ArchiveDtos.StorageTreeNode> nodes = new ArrayList<>();
        for (String childPath : children) {
            String name = childPath.substring(childPath.lastIndexOf('/') + 1);
            boolean isLeaf = leafPaths.contains(childPath);
            int recordCount = pathRecordCounts.getOrDefault(childPath, 0);
            List<ArchiveDtos.StorageTreeNode> subChildren = buildTreeLevel(childPath, parentToChildren, pathRecordCounts, leafPaths);
            // Sum up record counts from children for folder nodes
            if (!isLeaf && recordCount == 0) {
                recordCount = subChildren.stream().mapToInt(ArchiveDtos.StorageTreeNode::recordCount).sum();
            }
            String type = subChildren.isEmpty() && isLeaf ? "file" : "folder";
            nodes.add(new ArchiveDtos.StorageTreeNode(name, childPath, type, recordCount, subChildren));
        }
        return nodes;
    }

    public ArchiveDtos.StoragePathRecordsResponse getRecordsByStoragePath(String storagePath, String tenantId) {
        String effectiveTenant = safe(tenantId, "default");
        // Try exact match first, then prefix match for folder nodes
        List<ArchiveRecordEntity> records = archiveRecordRepository.findByTenantIdAndStoragePath(effectiveTenant, storagePath);
        if (records.isEmpty()) {
            records = archiveRecordRepository.findByStoragePathStartingWith(storagePath);
        }
        // Collect task IDs from archive records
        java.util.Set<Long> archiveTaskIds = records.stream()
                .map(ArchiveRecordEntity::getTaskId)
                .filter(Objects::nonNull)
                .collect(java.util.stream.Collectors.toSet());
        // Build pageFiles: deduplicate by base filename, keeping highest taskId (most recent)
        Map<String, ArchiveDtos.PageFile> bestByFilename = new java.util.LinkedHashMap<>();
        // 1. From archive record tasks
        if (!archiveTaskIds.isEmpty()) {
            for (Object[] row : ocrTaskRepository.findLightweightByIds(new ArrayList<>(archiveTaskIds))) {
                ArchiveDtos.PageFile pf = new ArchiveDtos.PageFile((Long) row[0], (String) row[1], (String) row[2], (String) row[3]);
                String baseFilename = baseFilename(pf.filename());
                ArchiveDtos.PageFile existing = bestByFilename.get(baseFilename);
                if (existing == null || pf.taskId() > existing.taskId()) {
                    bestByFilename.put(baseFilename, pf);
                }
            }
        }
        // 2. Extra tasks without archive records that match this path
        java.util.Set<Long> seenTaskIds = new java.util.HashSet<>(archiveTaskIds);
        for (Object[] row : ocrTaskRepository.findAllIdAndFilename()) {
            Long tid = (Long) row[0];
            if (seenTaskIds.contains(tid)) continue;
            String filename = (String) row[1];
            String derived = deriveStoragePathFromFilename(filename);
            if (StringUtils.hasText(derived) && (derived.equals(storagePath) || derived.startsWith(storagePath + "/"))) {
                String baseFilename = baseFilename(filename);
                // Only add if no archive-record task already covers this filename
                if (!bestByFilename.containsKey(baseFilename)) {
                    ArchiveDtos.PageFile existing = bestByFilename.get(baseFilename);
                    if (existing == null || tid > existing.taskId()) {
                        bestByFilename.put(baseFilename, new ArchiveDtos.PageFile(tid, filename, null, null));
                    }
                }
            }
        }
        // Fetch lightweight details for extra tasks that need status/fileType
        List<Long> needDetails = bestByFilename.values().stream()
                .filter(pf -> pf.status() == null)
                .map(ArchiveDtos.PageFile::taskId)
                .toList();
        if (!needDetails.isEmpty()) {
            Map<Long, Object[]> detailMap = new java.util.HashMap<>();
            for (Object[] row : ocrTaskRepository.findLightweightByIds(needDetails)) {
                detailMap.put((Long) row[0], row);
            }
            for (var entry : bestByFilename.entrySet()) {
                ArchiveDtos.PageFile pf = entry.getValue();
                if (pf.status() == null) {
                    Object[] row = detailMap.get(pf.taskId());
                    if (row != null) {
                        entry.setValue(new ArchiveDtos.PageFile((Long) row[0], (String) row[1], (String) row[2], (String) row[3]));
                    }
                }
            }
        }
        List<ArchiveDtos.PageFile> pageFiles = new ArrayList<>(bestByFilename.values());
        pageFiles.sort((a, b) -> {
            int cmp = String.valueOf(a.filename()).compareTo(String.valueOf(b.filename()));
            return cmp != 0 ? cmp : Long.compare(a.taskId(), b.taskId());
        });
        // Aggregate by archive_no: merge multi-page documents into single entries
        Map<String, List<ArchiveRecordEntity>> grouped = new java.util.LinkedHashMap<>();
        List<ArchiveRecordEntity> noArchiveNo = new ArrayList<>();
        for (ArchiveRecordEntity r : records) {
            String key = r.getArchiveNo();
            if (!StringUtils.hasText(key)) {
                noArchiveNo.add(r);
                continue;
            }
            grouped.computeIfAbsent(key, k -> new ArrayList<>()).add(r);
        }
        List<ArchiveRecordEntity> result = new ArrayList<>();
        for (var entry : grouped.entrySet()) {
            List<ArchiveRecordEntity> group = entry.getValue();
            // Use the first record directly — after Python writeback all records share the same values
            ArchiveRecordEntity representative = group.get(0);
            representative.setPages(String.valueOf(group.size()));
            result.add(representative);
        }
        result.addAll(noArchiveNo);
        return new ArchiveDtos.StoragePathRecordsResponse(
                result.size(),
                result.stream().map(this::toResponse).toList(),
                pageFiles
        );
    }

    private static int fieldScore(ArchiveRecordEntity r) {
        int score = 0;
        if (StringUtils.hasText(r.getTitle())) score++;
        if (StringUtils.hasText(r.getDocNo())) score++;
        if (StringUtils.hasText(r.getResponsible())) score++;
        if (StringUtils.hasText(r.getDate())) score++;
        if (StringUtils.hasText(r.getClassification())) score++;
        if (StringUtils.hasText(r.getRemarks())) score++;
        return score;
    }

    private static String baseFilename(String filename) {
        if (filename == null) return "";
        String s = filename;
        int slash = s.lastIndexOf('/');
        if (slash >= 0) s = s.substring(slash + 1);
        int back = s.lastIndexOf('\\');
        if (back >= 0) s = s.substring(back + 1);
        return s;
    }

    private String laterDateOf(String a, String b) {
        if (!StringUtils.hasText(a)) return b;
        if (!StringUtils.hasText(b)) return a;
        return a.trim().compareTo(b.trim()) >= 0 ? a : b;
    }

    private ArchiveRecordEntity findRecord(String recordKey, String tenantId) {
        String normalizedRecordKey = safe(recordKey);
        if (!StringUtils.hasText(normalizedRecordKey)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Archive record not found.");
        }
        try {
            Long recordId = Long.valueOf(normalizedRecordKey);
            var byId = archiveRecordRepository.findByIdAndTenantId(recordId, safe(tenantId, "default"));
            if (byId.isPresent()) {
                return byId.get();
            }
        } catch (NumberFormatException ignored) {
        }
        return archiveRecordRepository.findByArchiveNoAndTenantId(normalizedRecordKey, safe(tenantId, "default"))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Archive record not found."));
    }

    private OcrTaskEntity findTask(ArchiveRecordEntity record, String tenantId) {
        if (record.getTaskId() == null) {
            return null;
        }
        return ocrTaskRepository.findByIdAndTenantId(record.getTaskId(), safe(tenantId, "default")).orElse(null);
    }

    private boolean matchesKeyword(ArchiveRecordEntity record, String keyword) {
        String normalizedKeyword = safe(keyword).toLowerCase(Locale.ROOT);
        if (normalizedKeyword.isEmpty()) {
            return true;
        }
        String haystack = String.join(
                " ",
                safe(record.getArchiveNo()),
                safe(record.getDocNo()),
                safe(record.getResponsible()),
                safe(record.getTitle()),
                safe(record.getRemarks()),
                safe(record.getStoragePath())
        ).toLowerCase(Locale.ROOT);
        return haystack.contains(normalizedKeyword);
    }

    private boolean matchesDateRange(ArchiveRecordEntity record, String dateFrom, String dateTo) {
        LocalDate candidateDate = resolveRecordDate(record);
        LocalDate lowerBound = parseDate(dateFrom);
        LocalDate upperBound = parseDate(dateTo);
        if (lowerBound == null && upperBound == null) {
            return true;
        }
        if (candidateDate == null) {
            return false;
        }
        if (lowerBound != null && candidateDate.isBefore(lowerBound)) {
            return false;
        }
        return upperBound == null || !candidateDate.isAfter(upperBound);
    }

    private LocalDate resolveRecordDate(ArchiveRecordEntity record) {
        LocalDate explicitDate = parseDate(record.getDate());
        if (explicitDate != null) {
            return explicitDate;
        }
        return record.getCreatedAt() == null ? null : record.getCreatedAt().toLocalDate();
    }

    private static LocalDate parseDate(String value) {
        String normalized = safe(value);
        if (!StringUtils.hasText(normalized)) {
            return null;
        }
        String candidate = normalized.length() >= 10 ? normalized.substring(0, 10) : normalized;
        try {
            return LocalDate.parse(candidate);
        } catch (Exception ignored) {
            return null;
        }
    }

    private int resolvePageCount(ArchiveRecordEntity record, OcrTaskEntity task) {
        int pages = parsePages(record.getPages());
        if (pages > 0) {
            return pages;
        }
        return task == null || task.getPageCount() == null ? 0 : Math.max(task.getPageCount(), 0);
    }

    private List<ArchiveDtos.ArchiveDocUnitResponse> buildDocUnits(
            ArchiveRecordEntity record,
            String title,
            int pageCount,
            String pdfUrl
    ) {
        String docId = String.valueOf(record.getId());
        return List.of(new ArchiveDtos.ArchiveDocUnitResponse(
                docId,
                docId,
                title,
                1,
                pageCount > 0 ? 1 : null,
                pageCount > 0 ? pageCount : null,
                pageCount > 0 ? pageCount : null,
                "archived",
                pdfUrl,
                pdfUrl
        ));
    }

    private static boolean isPdfTask(OcrTaskEntity task) {
        return "pdf".equalsIgnoreCase(safe(task.getFileType())) || ".pdf".equals(extension(task.getFilename()));
    }

    private static String firstText(String preferred, String fallback) {
        return StringUtils.hasText(preferred) ? preferred.trim() : safe(fallback);
    }

    private String longerOf(String a, String b) {
        int lenA = StringUtils.hasText(a) ? a.trim().length() : 0;
        int lenB = StringUtils.hasText(b) ? b.trim().length() : 0;
        return lenB > lenA ? b : a;
    }

    private int parsePages(String pages) {
        if (!StringUtils.hasText(pages)) return 0;
        try {
            return (int) Double.parseDouble(pages.trim());
        } catch (NumberFormatException e) {
            return 0;
        }
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
    public java.util.Map<String, Object> ensureBatchForFolder(String folder, String tenantId) {
        Path safeFolder = pathAccessService.ensureAllowedPath(folder, false, true);
        String normalizedFolder = safeFolder.toString();
        String effectiveTenant = safe(tenantId, "default");

        List<String> existingBatchIds = archiveRecordRepository.findDistinctAssignedBatchIdsByTenantIdAndFolder(effectiveTenant, normalizedFolder);
        String batchId = existingBatchIds.isEmpty()
                ? "batch_" + OffsetDateTime.now().toEpochSecond() + "_" + UUID.randomUUID().toString().substring(0, 6)
                : existingBatchIds.get(0);
        boolean created = existingBatchIds.isEmpty();
        int linkedTasks = 0;

        List<ArchiveRecordEntity> unassignedRecords = archiveRecordRepository.findUnassignedByTenantIdAndFolder(effectiveTenant, normalizedFolder);
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

            if (!effectiveTenant.equals(record.getTenantId())) {
                record.setTenantId(effectiveTenant);
                dirty = true;
            }
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
            record.setStoragePath(readText(archiveFields, "storage_path", record.getStoragePath()));
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

        String storagePath = limitField("storagePath", record.getStoragePath(), MAX_STORAGE_PATH_LENGTH, context);
        if (!Objects.equals(storagePath, record.getStoragePath())) {
            record.setStoragePath(storagePath);
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

    private static String safe(String value, String defaultValue) {
        String trimmed = value == null ? "" : value.trim();
        return trimmed.isEmpty() ? defaultValue : trimmed;
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
