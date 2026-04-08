package com.ocrweb.controlplane.task.repository;

import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface OcrTaskRepository extends JpaRepository<OcrTaskEntity, Long> {

    @Query("""
            select t
            from OcrTaskEntity t
            where (:folder = '' or t.filePath like concat(:folder, '%'))
            order by t.createdAt desc
            """)
    Page<OcrTaskEntity> findByFolder(@Param("folder") String folder, Pageable pageable);

    @Query("""
            select t
            from OcrTaskEntity t
            where lower(t.filename) like lower(concat('%', :keyword, '%'))
               or lower(coalesce(t.fullText, '')) like lower(concat('%', :keyword, '%'))
            order by t.createdAt desc
            """)
    Page<OcrTaskEntity> search(@Param("keyword") String keyword, Pageable pageable);

    long deleteByFilePathStartingWith(String filePathPrefix);
}
