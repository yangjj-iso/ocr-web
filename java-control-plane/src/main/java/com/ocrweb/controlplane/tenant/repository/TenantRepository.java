package com.ocrweb.controlplane.tenant.repository;

import com.ocrweb.controlplane.tenant.domain.TenantEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface TenantRepository extends JpaRepository<TenantEntity, String> {
    List<TenantEntity> findAllByOrderByCreatedAtAsc();

    List<TenantEntity> findByStatusOrderByNameAsc(String status);
}