package com.ocrweb.controlplane.config;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class DotenvEnvironmentPostProcessor implements EnvironmentPostProcessor, Ordered {
    private static final String PROPERTY_SOURCE_NAME = "ocrDotenv";
    private static final int MAX_PARENT_DEPTH = 4;

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        Map<String, Object> values = loadDotenvValues();
        if (values.isEmpty()) {
            return;
        }
        if (environment.getPropertySources().contains(PROPERTY_SOURCE_NAME)) {
            environment.getPropertySources().remove(PROPERTY_SOURCE_NAME);
        }
        MapPropertySource propertySource = new MapPropertySource(PROPERTY_SOURCE_NAME, values);
        if (environment.getPropertySources().contains(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME)) {
            environment.getPropertySources().addAfter(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME, propertySource);
        } else {
            environment.getPropertySources().addFirst(propertySource);
        }
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE + 20;
    }

    static Map<String, Object> loadDotenvValues() {
        List<Path> candidates = dotenvCandidates();
        Map<String, Object> values = new LinkedHashMap<>();
        for (int index = candidates.size() - 1; index >= 0; index--) {
            Path candidate = candidates.get(index);
            if (Files.isRegularFile(candidate)) {
                values.putAll(parseDotenv(candidate));
            }
        }
        return values;
    }

    static List<Path> dotenvCandidates() {
        List<Path> candidates = new ArrayList<>();
        Path current = Path.of(System.getProperty("user.dir", ".")).toAbsolutePath().normalize();
        for (int depth = 0; current != null && depth < MAX_PARENT_DEPTH; depth++) {
            candidates.add(current.resolve(".env"));
            current = current.getParent();
        }
        return candidates;
    }

    private static Map<String, Object> parseDotenv(Path path) {
        Map<String, Object> values = new LinkedHashMap<>();
        List<String> lines;
        try {
            lines = Files.readAllLines(path, StandardCharsets.UTF_8);
        } catch (IOException error) {
            return values;
        }
        for (String rawLine : lines) {
            String line = rawLine.trim();
            if (!StringUtils.hasText(line) || line.startsWith("#")) {
                continue;
            }
            if (line.startsWith("export ")) {
                line = line.substring("export ".length()).trim();
            }
            int separator = line.indexOf('=');
            if (separator <= 0) {
                continue;
            }
            String key = line.substring(0, separator).trim();
            if (!StringUtils.hasText(key)) {
                continue;
            }
            values.put(key, unquote(line.substring(separator + 1).trim()));
        }
        return values;
    }

    private static String unquote(String value) {
        if (value.length() < 2) {
            return value;
        }
        char first = value.charAt(0);
        char last = value.charAt(value.length() - 1);
        if ((first == '"' && last == '"') || (first == '\'' && last == '\'')) {
            return value.substring(1, value.length() - 1);
        }
        return value;
    }
}
