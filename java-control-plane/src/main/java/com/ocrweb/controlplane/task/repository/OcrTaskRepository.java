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
            where (:folder = '' or t.filePath like concat(:folder, '%'))
              and (:batchId = '' or t.batchId = :batchId)
              and lower(t.status) = lower(:status)
            order by t.createdAt desc
            """)
    Page<OcrTaskEntity> findByFolderAndBatchIdAndStatus(
            @Param("folder") String folder,
            @Param("batchId") String batchId,
            @Param("status") String status,
            Pageable pageable
    );

    Page<OcrTaskEntity> findByAssigneeUsernameAndStatus(
            String assigneeUsername,
            String status,
            Pageable pageable
    );

    List<OcrTaskEntity> findByAssigneeUsername(String assigneeUsername);

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

    @Query("select t.id, t.filename from OcrTaskEntity t")
    List<Object[]> findAllIdAndFilename();

    @Query("select t.id, t.filename, t.status, t.fileType from OcrTaskEntity t where t.id in :ids")
    List<Object[]> findLightweightByIds(@Param("ids") List<Long> ids);

    @Query("""
            select count(distinct t.storageObjectKey)
            from OcrTaskEntity t
            where t.storageObjectKey is not null
              and t.storageObjectKey <> ''
            """)
    long countStoredObjectKeys();

    long deleteByBatchId(String batchId);

    long deleteByFilePathStartingWith(String filePathPrefix);

    // --- 租户隔离查询 ---

    Optional<OcrTaskEntity> findByIdAndTenantId(Long id, String tenantId);

    @Query("""
            select t
            from OcrTaskEntity t
            where t.tenantId = :tenantId
              and (:folder = '' or t.filePath like concat(:folder, '%'))
              and (:batchId = '' or t.batchId = :batchId)
            order by t.createdAt desc
            """)
    Page<OcrTaskEntity> findByTenantIdAndFolderAndBatchId(
            @Param("tenantId") String tenantId,
            @Param("folder") String folder,
            @Param("batchId") String batchId,
            Pageable pageable
    );

    @Query("""
            select t
            from OcrTaskEntity t
            where t.tenantId = :tenantId
              and (:folder = '' or t.filePath like concat(:folder, '%'))
              and (:batchId = '' or t.batchId = :batchId)
              and lower(t.status) = lower(:status)
            order by t.createdAt desc
            """)
    Page<OcrTaskEntity> findByTenantIdAndFolderAndBatchIdAndStatus(
            @Param("tenantId") String tenantId,
            @Param("folder") String folder,
            @Param("batchId") String batchId,
            @Param("status") String status,
            Pageable pageable
    );

    long countByTenantId(String tenantId);
}
