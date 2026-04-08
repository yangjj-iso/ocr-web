package com.ocrweb.controlplane.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

@ConfigurationProperties(prefix = "ocr.security")
public class ControlPlaneSecurityProperties {
    private boolean requireUserAuth = true;
    private List<String> publicPaths = new ArrayList<>();
    private List<String> corsAllowedOrigins = new ArrayList<>(List.of(
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173"
    ));
    private boolean corsAllowCredentials = true;
    private long corsMaxAgeSeconds = 3600;

    public boolean isRequireUserAuth() {
        return requireUserAuth;
    }

    public void setRequireUserAuth(boolean requireUserAuth) {
        this.requireUserAuth = requireUserAuth;
    }

    public List<String> getPublicPaths() {
        return publicPaths;
    }

    public void setPublicPaths(List<String> publicPaths) {
        this.publicPaths = publicPaths == null ? new ArrayList<>() : publicPaths;
    }

    public List<String> getCorsAllowedOrigins() {
        return corsAllowedOrigins;
    }

    public void setCorsAllowedOrigins(List<String> corsAllowedOrigins) {
        this.corsAllowedOrigins = corsAllowedOrigins == null ? new ArrayList<>() : corsAllowedOrigins;
    }

    public boolean isCorsAllowCredentials() {
        return corsAllowCredentials;
    }

    public void setCorsAllowCredentials(boolean corsAllowCredentials) {
        this.corsAllowCredentials = corsAllowCredentials;
    }

    public long getCorsMaxAgeSeconds() {
        return corsMaxAgeSeconds;
    }

    public void setCorsMaxAgeSeconds(long corsMaxAgeSeconds) {
        this.corsMaxAgeSeconds = corsMaxAgeSeconds;
    }
}
