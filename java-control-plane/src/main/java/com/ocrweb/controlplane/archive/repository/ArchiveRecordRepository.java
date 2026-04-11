package com.ocrweb.controlplane.archive.repository;

import com.ocrweb.controlplane.archive.domain.ArchiveRecordEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface ArchiveRecordRepository extends JpaRepository<ArchiveRecordEntity, Long> {
    Optional<ArchiveRecordEntity> findByTaskId(Long taskId);

    @Query("""
            select r from ArchiveRecordEntity r
            where (:folder = '' or r.batchFolder = :folder)
              and (:batchId = '' or r.batchId = :batchId)
            order by r.createdAt asc
            """)
    Page<ArchiveRecordEntity> findByFilters(@Param("folder") String folder, @Param("batchId") String batchId, Pageable pageable);

    @Query("""
            select r from ArchiveRecordEntity r
            where (:folder = '' or r.batchFolder = :folder)
              and (:batchId = '' or r.batchId = :batchId)
            order by r.createdAt asc
            """)
    List<ArchiveRecordEntity> findAllByFilters(@Param("folder") String folder, @Param("batchId") String batchId);

    List<ArchiveRecordEntity> findByBatchFolderAndBatchIdIsNull(String batchFolder);

    @Query("""
            select r from ArchiveRecordEntity r
            where r.batchFolder = :folder and (r.batchId is null or r.batchId = '')
            order by r.createdAt asc
            """)
    List<ArchiveRecordEntity> findUnassignedByFolder(@Param("folder") String folder);

    @Query("""
            select distinct r.batchId from ArchiveRecordEntity r
            where r.batchFolder = :folder and r.batchId is not null and r.batchId <> ''
            """)
    List<String> findDistinctAssignedBatchIdsByFolder(@Param("folder") String folder);

    @Query("select r from ArchiveRecordEntity r where r.taskId in :taskIds")
    List<ArchiveRecordEntity> findByTaskIdIn(@Param("taskIds") List<Long> taskIds);

    long deleteByBatchFolder(String batchFolder);

    long deleteByBatchId(String batchId);

    long deleteByTaskId(Long taskId);
}
