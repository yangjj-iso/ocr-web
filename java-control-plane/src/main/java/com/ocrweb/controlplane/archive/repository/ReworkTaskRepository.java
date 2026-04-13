package com.ocrweb.controlplane.archive.repository;

import com.ocrweb.controlplane.archive.domain.ReworkTaskEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ReworkTaskRepository extends JpaRepository<ReworkTaskEntity, String> {
    List<ReworkTaskEntity> findAllByOrderByCreatedAtDesc();

    List<ReworkTaskEntity> findByTenantIdOrderByCreatedAtDesc(String tenantId);

    Optional<ReworkTaskEntity> findTopByRecordIdOrderByCreatedAtDesc(String recordId);

    Optional<ReworkTaskEntity> findTopByTenantIdAndRecordIdOrderByCreatedAtDesc(String tenantId, String recordId);
}