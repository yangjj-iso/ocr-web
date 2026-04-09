package com.ocrweb.controlplane.archive.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.archive.domain.ArchiveRecordEntity;
import com.ocrweb.controlplane.archive.repository.ArchiveRecordRepository;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ArchiveRecordServiceTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void saveArchiveRecordFromTaskCompletion_truncatesOversizedFieldsBeforeSave() {
        ArchiveRecordRepository archiveRecordRepository = mock(ArchiveRecordRepository.class);
        OcrTaskRepository ocrTaskRepository = mock(OcrTaskRepository.class);
        PathAccessService pathAccessService = mock(PathAccessService.class);
        ArchiveRecordService service = new ArchiveRecordService(
                archiveRecordRepository,
                ocrTaskRepository,
                pathAccessService
        );

        when(archiveRecordRepository.findByTaskId(286L)).thenReturn(Optional.empty());

        String longTitle = "题".repeat(1205);
        String longRemarks = "备".repeat(1308);
        ObjectNode payload = objectMapper.createObjectNode()
                .put("archive_no", "KJ-JJ-2017-02-001-026")
                .put("title", longTitle)
                .put("remarks", longRemarks);

        service.saveArchiveRecordFromTaskCompletion(286L, "batch_x", "D:\\archive", payload);

        ArgumentCaptor<ArchiveRecordEntity> captor = ArgumentCaptor.forClass(ArchiveRecordEntity.class);
        verify(archiveRecordRepository).save(captor.capture());
        ArchiveRecordEntity saved = captor.getValue();

        assertEquals(1000, saved.getTitle().length());
        assertEquals(1000, saved.getRemarks().length());
        assertTrue(saved.getTitle().endsWith("..."));
        assertTrue(saved.getRemarks().endsWith("..."));
        assertEquals("KJ-JJ-2017-02-001-026", saved.getArchiveNo());
    }
}
