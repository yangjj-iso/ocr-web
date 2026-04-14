package com.ocrweb.controlplane.auth.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.auth.domain.AppUserEntity;
import com.ocrweb.controlplane.auth.repository.AppUserRepository;
import com.ocrweb.controlplane.config.AuthProperties;
import com.ocrweb.controlplane.tenant.service.TenantService;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class AuthServiceTest {
    @Test
    void loginCookiePreservesCapabilities() {
        AuthProperties authProperties = new AuthProperties();
        authProperties.setEnabled(true);

        PasswordHashService passwordHashService = new PasswordHashService();
        SessionTokenService sessionTokenService = new SessionTokenService(authProperties, new ObjectMapper());
        AppUserRepository appUserRepository = mock(AppUserRepository.class);
        TenantService tenantService = mock(TenantService.class);

        AppUserEntity user = new AppUserEntity();
        user.setUsername("member01");
        user.setPasswordHash(passwordHashService.hashPassword("secret123"));
        user.setStatus("active");
        user.setRole("member");
        user.setCapabilities("operator");
        user.setTenantId("tenant-a");

        when(appUserRepository.findByUsername("member01")).thenReturn(Optional.of(user));

        AuthService authService = new AuthService(appUserRepository, passwordHashService, sessionTokenService, authProperties, tenantService);

        AuthService.AuthLoginResult result = authService.login("member01", "secret123");

        assertThat(result.payload()).isNotNull();
        assertThat(result.payload().capabilities()).isEqualTo("operator");

        String cookieValue = result.setCookieHeader().split(";", 2)[0].split("=", 2)[1];
        CurrentUser currentUser = sessionTokenService.verifySessionToken(cookieValue);

        assertThat(currentUser).isNotNull();
        assertThat(currentUser.effectiveRole()).isEqualTo("member");
        assertThat(currentUser.effectiveTenantId()).isEqualTo("tenant-a");
        assertThat(currentUser.effectiveCapabilities()).isEqualTo("operator");
    }
}