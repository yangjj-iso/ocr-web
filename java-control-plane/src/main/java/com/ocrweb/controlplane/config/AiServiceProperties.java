package com.ocrweb.controlplane.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "ocr.ai")
public class AiServiceProperties {
    private String baseUrl = "http://127.0.0.1:8001";
    private int connectTimeoutSeconds = 10;
    private int readTimeoutSeconds = 300;
    private int circuitFailureThreshold = 5;
    private int circuitOpenSeconds = 30;
    private String healthPath = "/api/health";

    public String getBaseUrl() {
        return baseUrl;
    }

    public void setBaseUrl(String baseUrl) {
        this.baseUrl = baseUrl;
    }

    public int getConnectTimeoutSeconds() {
        return connectTimeoutSeconds;
    }

    public void setConnectTimeoutSeconds(int connectTimeoutSeconds) {
        this.connectTimeoutSeconds = connectTimeoutSeconds;
    }

    public int getReadTimeoutSeconds() {
        return readTimeoutSeconds;
    }

    public void setReadTimeoutSeconds(int readTimeoutSeconds) {
        this.readTimeoutSeconds = readTimeoutSeconds;
    }

    public int getCircuitFailureThreshold() {
        return circuitFailureThreshold;
    }

    public void setCircuitFailureThreshold(int circuitFailureThreshold) {
        this.circuitFailureThreshold = circuitFailureThreshold;
    }

    public int getCircuitOpenSeconds() {
        return circuitOpenSeconds;
    }

    public void setCircuitOpenSeconds(int circuitOpenSeconds) {
        this.circuitOpenSeconds = circuitOpenSeconds;
    }

    public String getHealthPath() {
        return healthPath;
    }

    public void setHealthPath(String healthPath) {
        this.healthPath = healthPath;
    }
}
