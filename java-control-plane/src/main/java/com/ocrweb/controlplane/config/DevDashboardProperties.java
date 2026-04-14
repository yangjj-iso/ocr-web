package com.ocrweb.controlplane.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "ocr.dev-dashboard")
public class DevDashboardProperties {
    private boolean enabled = true;
    private String username = "devadmin";
    private String password = "change-me-dev-dashboard";
    private String twoFactorSecret = "JBSWY3DPEHPK3PXP";
    private String sessionSecret = "change-this-dev-dashboard-session-secret";
    private String cookieName = "ocr_dev_dashboard_session";
    private boolean cookieSecure = false;
    private String cookieSameSite = "lax";
    private int sessionTtl = 28800;
    private int twoFactorWindowSteps = 1;

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

    public String getTwoFactorSecret() {
        return twoFactorSecret;
    }

    public void setTwoFactorSecret(String twoFactorSecret) {
        this.twoFactorSecret = twoFactorSecret;
    }

    public String getSessionSecret() {
        return sessionSecret;
    }

    public void setSessionSecret(String sessionSecret) {
        this.sessionSecret = sessionSecret;
    }

    public String getCookieName() {
        return cookieName;
    }

    public void setCookieName(String cookieName) {
        this.cookieName = cookieName;
    }

    public boolean isCookieSecure() {
        return cookieSecure;
    }

    public void setCookieSecure(boolean cookieSecure) {
        this.cookieSecure = cookieSecure;
    }

    public String getCookieSameSite() {
        return cookieSameSite;
    }

    public void setCookieSameSite(String cookieSameSite) {
        this.cookieSameSite = cookieSameSite;
    }

    public int getSessionTtl() {
        return sessionTtl;
    }

    public void setSessionTtl(int sessionTtl) {
        this.sessionTtl = sessionTtl;
    }

    public int getTwoFactorWindowSteps() {
        return twoFactorWindowSteps;
    }

    public void setTwoFactorWindowSteps(int twoFactorWindowSteps) {
        this.twoFactorWindowSteps = twoFactorWindowSteps;
    }
}
