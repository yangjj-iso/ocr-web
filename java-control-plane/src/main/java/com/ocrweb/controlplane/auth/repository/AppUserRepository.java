package com.ocrweb.controlplane.auth.repository;

import com.ocrweb.controlplane.auth.domain.AppUserEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface AppUserRepository extends JpaRepository<AppUserEntity, Long> {
    Optional<AppUserEntity> findByUsername(String username);

    List<AppUserEntity> findByStatusOrderByCreatedAtDesc(String status);

    List<AppUserEntity> findByStatusAndTenantIdOrderByCreatedAtDesc(String status, String tenantId);

    List<AppUserEntity> findByTenantIdOrderByCreatedAtDesc(String tenantId);
}
