package com.ocrweb.controlplane.auth.service;

import com.ocrweb.controlplane.auth.domain.UserQuotaEntity;
import com.ocrweb.controlplane.auth.repository.UserQuotaRepository;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.Locale;

@Service
public class UserQuotaService {
    private final UserQuotaRepository userQuotaRepository;

    public UserQuotaService(UserQuotaRepository userQuotaRepository) {
        this.userQuotaRepository = userQuotaRepository;
    }

    public void consumeUploadQuota(CurrentUser currentUser, int fileCount) {
        if (currentUser == null || fileCount <= 0 || currentUser.isAdmin() || currentUser.userId() == null) {
            return;
        }

        String effectiveRole = currentUser.effectiveRole().toLowerCase(Locale.ROOT);
        if (!"operator".equals(effectiveRole)) {
            return;
        }

        UserQuotaEntity quota = loadOrCreateQuota(currentUser.userId());
        if (fileCount > quota.getQuotaPerImport()) {
            throw new ResponseStatusException(
                    HttpStatus.TOO_MANY_REQUESTS,
                    "This upload exceeds the per-import quota for the current operator."
            );
        }

        int nextUsed = quota.getQuotaUsed() + fileCount;
        if (nextUsed > quota.getQuotaTotal()) {
            throw new ResponseStatusException(
                    HttpStatus.TOO_MANY_REQUESTS,
                    "This upload exceeds the operator's remaining total quota."
            );
        }

        quota.setQuotaUsed(nextUsed);
        userQuotaRepository.save(quota);
    }

    private UserQuotaEntity loadOrCreateQuota(Long userId) {
        UserQuotaEntity existing = userQuotaRepository.findByUserIdForUpdate(userId).orElse(null);
        if (existing != null) {
            return existing;
        }

        try {
            UserQuotaEntity created = new UserQuotaEntity();
            created.setUserId(userId);
            return userQuotaRepository.saveAndFlush(created);
        } catch (DataIntegrityViolationException ignored) {
            return userQuotaRepository.findByUserIdForUpdate(userId)
                    .orElseThrow(() -> new IllegalStateException("Failed to resolve quota row for user " + userId));
        }
    }
}
