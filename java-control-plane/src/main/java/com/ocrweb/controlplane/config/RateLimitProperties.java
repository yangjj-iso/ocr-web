package com.ocrweb.controlplane.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "ocr.rate-limit")
public class RateLimitProperties {
    private boolean enabled = true;
    private int windowSeconds = 60;
    private int uploadMaxRequests = 30;
    private int batchAiMaxRequests = 90;
    private int previewMaxRequests = 240;
    private int generalMaxRequests = 600;

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public int getWindowSeconds() {
        return windowSeconds;
    }

    public void setWindowSeconds(int windowSeconds) {
        this.windowSeconds = windowSeconds;
    }

    public int getUploadMaxRequests() {
        return uploadMaxRequests;
    }

    public void setUploadMaxRequests(int uploadMaxRequests) {
        this.uploadMaxRequests = uploadMaxRequests;
    }

    public int getBatchAiMaxRequests() {
        return batchAiMaxRequests;
    }

    public void setBatchAiMaxRequests(int batchAiMaxRequests) {
        this.batchAiMaxRequests = batchAiMaxRequests;
    }

    public int getPreviewMaxRequests() {
        return previewMaxRequests;
    }

    public void setPreviewMaxRequests(int previewMaxRequests) {
        this.previewMaxRequests = previewMaxRequests;
    }

    public int getGeneralMaxRequests() {
        return generalMaxRequests;
    }

    public void setGeneralMaxRequests(int generalMaxRequests) {
        this.generalMaxRequests = generalMaxRequests;
    }
}
