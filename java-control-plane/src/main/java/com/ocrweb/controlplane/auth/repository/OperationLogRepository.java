package com.ocrweb.controlplane.auth.repository;

import com.ocrweb.controlplane.auth.domain.OperationLogEntity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OperationLogRepository extends JpaRepository<OperationLogEntity, Long> {
    Page<OperationLogEntity> findByUserIdOrderByCreatedAtDesc(Long userId, Pageable pageable);

    Page<OperationLogEntity> findByActionTypeOrderByCreatedAtDesc(String actionType, Pageable pageable);

    Page<OperationLogEntity> findByUserIdAndActionTypeOrderByCreatedAtDesc(Long userId, String actionType, Pageable pageable);
}