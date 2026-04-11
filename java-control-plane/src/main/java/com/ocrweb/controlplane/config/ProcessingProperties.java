package com.ocrweb.controlplane.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "ocr.processing")
public class ProcessingProperties {
    private String layoutBackend = "local";
    private String vlBackend = "auto";
    private boolean enableHierarchicalAgent = false;
    private String llmBackend = "local";
    private String llmModel = "";
    private String processingStrategy = "auto";
    private int maxRetries = 2;
    private double confidenceThreshold = 0.85;
    private double humanReviewThresholdLow = 0.60;
    private double humanReviewThresholdHigh = 0.85;
    private int timeoutSeconds = 1800;
    private String gpuProfile = "single_gpu";
    private String langgraphGraph = "batch_supervisor_v1";

    public String getLayoutBackend() {
        return layoutBackend;
    }

    public void setLayoutBackend(String layoutBackend) {
        this.layoutBackend = layoutBackend;
    }

    public String getVlBackend() {
        return vlBackend;
    }

    public void setVlBackend(String vlBackend) {
        this.vlBackend = vlBackend;
    }

    public boolean isEnableHierarchicalAgent() {
        return enableHierarchicalAgent;
    }

    public void setEnableHierarchicalAgent(boolean enableHierarchicalAgent) {
        this.enableHierarchicalAgent = enableHierarchicalAgent;
    }

    public String getLlmBackend() {
        return llmBackend;
    }

    public void setLlmBackend(String llmBackend) {
        this.llmBackend = llmBackend;
    }

    public String getLlmModel() {
        return llmModel;
    }

    public void setLlmModel(String llmModel) {
        this.llmModel = llmModel;
    }

    public String getProcessingStrategy() {
        return processingStrategy;
    }

    public void setProcessingStrategy(String processingStrategy) {
        this.processingStrategy = processingStrategy;
    }

    public int getMaxRetries() {
        return maxRetries;
    }

    public void setMaxRetries(int maxRetries) {
        this.maxRetries = maxRetries;
    }

    public double getConfidenceThreshold() {
        return confidenceThreshold;
    }

    public void setConfidenceThreshold(double confidenceThreshold) {
        this.confidenceThreshold = confidenceThreshold;
    }

    public double getHumanReviewThresholdLow() {
        return humanReviewThresholdLow;
    }

    public void setHumanReviewThresholdLow(double humanReviewThresholdLow) {
        this.humanReviewThresholdLow = humanReviewThresholdLow;
    }

    public double getHumanReviewThresholdHigh() {
        return humanReviewThresholdHigh;
    }

    public void setHumanReviewThresholdHigh(double humanReviewThresholdHigh) {
        this.humanReviewThresholdHigh = humanReviewThresholdHigh;
    }

    public int getTimeoutSeconds() {
        return timeoutSeconds;
    }

    public void setTimeoutSeconds(int timeoutSeconds) {
        this.timeoutSeconds = timeoutSeconds;
    }

    public String getGpuProfile() {
        return gpuProfile;
    }

    public void setGpuProfile(String gpuProfile) {
        this.gpuProfile = gpuProfile;
    }

    public String getLanggraphGraph() {
        return langgraphGraph;
    }

    public void setLanggraphGraph(String langgraphGraph) {
        this.langgraphGraph = langgraphGraph;
    }
}
