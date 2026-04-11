package com.ocrweb.controlplane.auth.repository;

import com.ocrweb.controlplane.auth.domain.UserQuotaEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface UserQuotaRepository extends JpaRepository<UserQuotaEntity, Long> {
    Optional<UserQuotaEntity> findByUserId(Long userId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select quota from UserQuotaEntity quota where quota.userId = :userId")
    Optional<UserQuotaEntity> findByUserIdForUpdate(@Param("userId") Long userId);
}
