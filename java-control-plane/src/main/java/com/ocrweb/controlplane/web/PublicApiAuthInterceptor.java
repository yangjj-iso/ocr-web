package com.ocrweb.controlplane.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ocrweb.controlplane.auth.service.AuthService;
import com.ocrweb.controlplane.auth.service.CurrentUser;
import com.ocrweb.controlplane.config.ControlPlaneSecurityProperties;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;

@Component
public class PublicApiAuthInterceptor implements HandlerInterceptor {
    private final ControlPlaneSecurityProperties securityProperties;
    private final AuthService authService;
    private final ObjectMapper objectMapper;

    public PublicApiAuthInterceptor(
            ControlPlaneSecurityProperties securityProperties,
            AuthService authService,
            ObjectMapper objectMapper
    ) {
        this.securityProperties = securityProperties;
        this.authService = authService;
        this.objectMapper = objectMapper;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if (!securityProperties.isRequireUserAuth()) {
            return true;
        }
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String path = request.getRequestURI();
        if (path == null || !path.startsWith("/api/")) {
            return true;
        }
        if (path.startsWith("/internal/")) {
            return true;
        }
        CurrentUser currentUser = authService.resolveAuthenticatedUser(request);
        for (String publicPath : securityProperties.getPublicPaths()) {
            if (StringUtils.hasText(publicPath) && path.startsWith(publicPath.trim())) {
                if (currentUser != null) {
                    request.setAttribute(CurrentUser.REQUEST_ATTRIBUTE, currentUser);
                }
                return true;
            }
        }
        if (currentUser != null) {
            request.setAttribute(CurrentUser.REQUEST_ATTRIBUTE, currentUser);
            return true;
        }

        ObjectNode payload = objectMapper.createObjectNode();
        payload.put("detail", "Authentication required.");
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write(objectMapper.writeValueAsString(payload));
        return false;
    }
}
