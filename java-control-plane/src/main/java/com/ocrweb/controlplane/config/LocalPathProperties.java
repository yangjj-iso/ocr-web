package com.ocrweb.controlplane.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

@ConfigurationProperties(prefix = "ocr.local-path")
public class LocalPathProperties {
    private List<String> roots = new ArrayList<>();

    public List<String> getRoots() {
        return roots;
    }

    public void setRoots(List<String> roots) {
        this.roots = roots == null ? new ArrayList<>() : roots;
    }
}
