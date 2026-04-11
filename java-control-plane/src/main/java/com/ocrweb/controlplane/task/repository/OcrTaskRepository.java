package com.ocrweb.controlplane.task.repository;

import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;

public interface OcrTaskRepository extends JpaRepository<OcrTaskEntity, Long> {

    @Query("""
            select t
            from OcrTaskEntity t
            where (:folder = '' or t.filePath like concat(:folder, '%'))
              and (:batchId = '' or t.batchId = :batchId)
            order by t.createdAt desc
            """)
    Page<OcrTaskEntity> findByFolderAndBatchId(
            @Param("folder") String folder,
            @Param("batchId") String batchId,
            Pageable pageable
    );

    @Query("""
            select t
            from OcrTaskEntity t
            where lower(t.filename) like lower(concat('%', :keyword, '%'))
               or lower(coalesce(t.fullText, '')) like lower(concat('%', :keyword, '%'))
            order by t.createdAt desc
            """)
    Page<OcrTaskEntity> search(@Param("keyword") String keyword, Pageable pageable);

    @Query("""
            select distinct t
            from OcrTaskEntity t
            left join ArchiveRecordEntity a on a.taskId = t.id
            where lower(t.filename) like lower(concat('%', :keyword, '%'))
               or lower(coalesce(t.fullText, '')) like lower(concat('%', :keyword, '%'))
               or lower(coalesce(a.archiveNo, '')) like lower(concat('%', :keyword, '%'))
               or lower(coalesce(a.docNo, '')) like lower(concat('%', :keyword, '%'))
               or lower(coalesce(a.responsible, '')) like lower(concat('%', :keyword, '%'))
               or lower(coalesce(a.title, '')) like lower(concat('%', :keyword, '%'))
            order by t.createdAt desc
            """)
    Page<OcrTaskEntity> searchWithArchive(@Param("keyword") String keyword, Pageable pageable);

    Optional<OcrTaskEntity> findFirstByBatchIdOrderByCreatedAtAsc(String batchId);

    List<OcrTaskEntity> findByBatchIdOrderByCreatedAtDesc(String batchId);

    List<OcrTaskEntity> findBySubmitterUsernameAndCreatedAtBetweenOrderByCreatedAtAsc(
            String submitterUsername,
            OffsetDateTime start,
            OffsetDateTime end
    );

    long deleteByBatchId(String batchId);

    long deleteByFilePathStartingWith(String filePathPrefix);
}
