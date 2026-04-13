package com.ocrweb.controlplane.dev.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.dev.service.DevDashboardAuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;

@Component
public class DevDashboardAuthInterceptor implements HandlerInterceptor {
    private final DevDashboardAuthService authService;
    private final ObjectMapper objectMapper;

    public DevDashboardAuthInterceptor(DevDashboardAuthService authService, ObjectMapper objectMapper) {
        this.authService = authService;
        this.objectMapper = objectMapper;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String path = request.getRequestURI();
        if (path == null || !path.startsWith("/api/dev/dashboard")) {
            return true;
        }
        if (path.startsWith("/api/dev/dashboard/auth/")) {
            return true;
        }
        if (authService.resolveSession(request) != null) {
            return true;
        }

        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("detail", "Dashboard authentication required.");
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write(objectMapper.writeValueAsString(payload));
        return false;
    }
}
