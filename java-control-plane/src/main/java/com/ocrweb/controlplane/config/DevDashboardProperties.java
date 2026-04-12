package com.ocrweb.controlplane.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "ocr.dev-dashboard")
public class DevDashboardProperties {
    private boolean enabled = true;
    private String username = "";
    private String password = "";
    private String cookieName = "ocr_dev_dashboard_session";
    private int sessionTtl = 28800;
    private String celeryQueue = "ocr.compute.internal.queue";
    private String pythonMetricsPath = "/internal/api/v1/worker/metrics";

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public String getCookieName() {
        return cookieName;
    }

    public void setCookieName(String cookieName) {
        this.cookieName = cookieName;
    }

    public int getSessionTtl() {
        return sessionTtl;
    }

    public void setSessionTtl(int sessionTtl) {
        this.sessionTtl = sessionTtl;
    }

    public String getCeleryQueue() {
        return celeryQueue;
    }

    public void setCeleryQueue(String celeryQueue) {
        this.celeryQueue = celeryQueue;
    }

    public String getPythonMetricsPath() {
        return pythonMetricsPath;
    }

    public void setPythonMetricsPath(String pythonMetricsPath) {
        this.pythonMetricsPath = pythonMetricsPath;
    }
}
