package com.ocrweb.controlplane.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.auth.repository.AppUserRepository;
import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.auth.service.PasswordHashService;
import com.ocrweb.controlplane.auth.service.SessionTokenService;
import com.ocrweb.controlplane.config.AuthProperties;
import com.ocrweb.controlplane.config.ControlPlaneSecurityProperties;
import com.ocrweb.controlplane.config.RateLimitProperties;
import com.ocrweb.controlplane.task.service.AiProxyTimeoutException;
import com.ocrweb.controlplane.tenant.service.TenantService;
import com.ocrweb.controlplane.trace.TraceContextFilter;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.web.filter.CorsFilter;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;

import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.emptyOrNullString;
import static org.mockito.Mockito.mock;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ControlPlaneWebInfrastructureTest {
    @Test
    void missingAuthIsRejectedAndTraceHeaderIsGenerated() throws Exception {
        MockMvc mockMvc = buildMockMvc(defaultSecurity(), defaultRateLimit());

        mockMvc.perform(get("/api/ocr/tasks").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isUnauthorized())
                .andExpect(header().string(TraceContextFilter.TRACE_HEADER, not(emptyOrNullString())))
                .andExpect(jsonPath("$.detail").value("Authentication required."));
    }

    @Test
    void authMeIsAllowedWithoutAuthentication() throws Exception {
        ControlPlaneSecurityProperties securityProperties = defaultSecurity();
        securityProperties.setPublicPaths(List.of("/api/auth/me", "/api/auth/login", "/api/auth/register", "/api/auth/logout"));
        MockMvc mockMvc = buildMockMvc(securityProperties, defaultRateLimit());

        mockMvc.perform(get("/api/auth/me").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ok"));
    }

    @Test
    void corsPreflightAllowsFrontendLoginRequest() throws Exception {
        ControlPlaneSecurityProperties securityProperties = defaultSecurity();
        MockMvc mockMvc = buildMockMvc(securityProperties, defaultRateLimit());

        mockMvc.perform(
                        options("/api/auth/login")
                                .header(HttpHeaders.ORIGIN, "http://localhost:3000")
                                .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST")
                                .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "content-type")
                )
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, "http://localhost:3000"))
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_CREDENTIALS, "true"));
    }

    @Test
    void suppliedTraceHeaderIsPreserved() throws Exception {
        MockMvc mockMvc = buildMockMvc(defaultSecurity(), defaultRateLimit());

        mockMvc.perform(
                        get("/api/ocr/tasks")
                                .header(HttpHeaders.AUTHORIZATION, basicAdminHeader())
                                .header(TraceContextFilter.TRACE_HEADER, "trace-abc-123")
                                .accept(MediaType.APPLICATION_JSON)
                )
                .andExpect(status().isOk())
                .andExpect(header().string(TraceContextFilter.TRACE_HEADER, "trace-abc-123"))
                .andExpect(jsonPath("$.status").value("ok"));
    }

    @Test
    void rateLimitAppliesToBatchAiEndpoints() throws Exception {
        RateLimitProperties rateLimitProperties = defaultRateLimit();
        rateLimitProperties.setBatchAiMaxRequests(1);
        MockMvc mockMvc = buildMockMvc(defaultSecurity(), rateLimitProperties);

        mockMvc.perform(get("/api/ocr/batches/batch-1/qa/metrics").header(HttpHeaders.AUTHORIZATION, basicAdminHeader()))
                .andExpect(status().isOk());

        mockMvc.perform(get("/api/ocr/batches/batch-1/qa/metrics").header(HttpHeaders.AUTHORIZATION, basicAdminHeader()))
                .andExpect(status().isTooManyRequests())
                .andExpect(jsonPath("$.bucket").value("batch_ai"));
    }

    @Test
    void aiTimeoutIsMappedToGatewayTimeout() throws Exception {
        MockMvc mockMvc = buildMockMvc(defaultSecurity(), defaultRateLimit());

        mockMvc.perform(get("/api/ocr/fail-timeout").header(HttpHeaders.AUTHORIZATION, basicAdminHeader()))
                .andExpect(status().isGatewayTimeout())
                .andExpect(jsonPath("$.detail").value("AI proxy request timed out."));
    }

    private static MockMvc buildMockMvc(ControlPlaneSecurityProperties securityProperties, RateLimitProperties rateLimitProperties) {
        ObjectMapper objectMapper = new ObjectMapper();
        AuthProperties authProperties = new AuthProperties();
        authProperties.setEnabled(true);
        authProperties.setUsername("admin");
        authProperties.setPassword("change-me");
        AppUserRepository appUserRepository = mock(AppUserRepository.class);
        TenantService tenantService = mock(TenantService.class);
        AuthService authService = new AuthService(
                appUserRepository,
                new PasswordHashService(),
                new SessionTokenService(authProperties, objectMapper),
            authProperties,
            tenantService
        );
        return MockMvcBuilders
                .standaloneSetup(new TestController())
                .addFilters(corsFilter(securityProperties))
                .addInterceptors(
                        new PublicApiAuthInterceptor(securityProperties, authService, objectMapper),
                        new RequestRateLimitingInterceptor(rateLimitProperties, objectMapper)
                )
                .addFilters(new TraceContextFilter())
                .setControllerAdvice(new GlobalExceptionHandler(objectMapper))
                .build();
    }

    private static ControlPlaneSecurityProperties defaultSecurity() {
        ControlPlaneSecurityProperties properties = new ControlPlaneSecurityProperties();
        properties.setRequireUserAuth(true);
        properties.setPublicPaths(List.of());
        return properties;
    }

    private static RateLimitProperties defaultRateLimit() {
        RateLimitProperties properties = new RateLimitProperties();
        properties.setEnabled(true);
        properties.setWindowSeconds(60);
        properties.setUploadMaxRequests(10);
        properties.setBatchAiMaxRequests(10);
        properties.setPreviewMaxRequests(10);
        properties.setGeneralMaxRequests(10);
        return properties;
    }

    private static CorsFilter corsFilter(ControlPlaneSecurityProperties securityProperties) {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowCredentials(securityProperties.isCorsAllowCredentials());
        configuration.setAllowedOriginPatterns(securityProperties.getCorsAllowedOrigins());
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.addAllowedHeader(CorsConfiguration.ALL);
        configuration.setExposedHeaders(List.of(HttpHeaders.LOCATION, "X-Trace-Id"));
        configuration.setMaxAge(securityProperties.getCorsMaxAgeSeconds());
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", configuration);
        return new CorsFilter(source);
    }

    private static String basicAdminHeader() {
        return "Basic " + Base64.getEncoder().encodeToString("admin:change-me".getBytes(StandardCharsets.UTF_8));
    }

    @RestController
    @RequestMapping("/api")
    static class TestController {
        @GetMapping("/ocr/tasks")
        public java.util.Map<String, Object> tasks() {
            return java.util.Map.of("status", "ok");
        }

        @GetMapping("/ocr/batches/{batchId}/qa/metrics")
        public java.util.Map<String, Object> qaMetrics() {
            return java.util.Map.of("status", "ok");
        }

        @GetMapping("/ocr/fail-timeout")
        public java.util.Map<String, Object> failTimeout() {
            throw new AiProxyTimeoutException("AI proxy request timed out.", new HttpTimeoutException("timeout"));
        }

        @GetMapping("/auth/me")
        public java.util.Map<String, Object> authMe() {
            return java.util.Map.of("status", "ok");
        }
    }
}
