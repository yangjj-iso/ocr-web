package com.ocrweb.controlplane.config;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class DotenvFileSupport {
    private DotenvFileSupport() {
    }

    static Map<String, Object> loadLocalDotenv() {
        for (Path candidate : candidates()) {
            if (Files.isRegularFile(candidate)) {
                return read(candidate);
            }
        }
        return Map.of();
    }

    private static List<Path> candidates() {
        Path cwd = Path.of("").toAbsolutePath().normalize();
        return List.of(
                cwd.resolve(".env"),
                cwd.getParent() == null ? cwd.resolve(".env") : cwd.getParent().resolve(".env")
        );
    }

    private static Map<String, Object> read(Path path) {
        Map<String, Object> values = new LinkedHashMap<>();
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                parseLine(line, values);
            }
        } catch (IOException ignored) {
            return Map.of();
        }
        return values;
    }

    private static void parseLine(String rawLine, Map<String, Object> values) {
        String line = rawLine == null ? "" : rawLine.trim();
        if (line.isEmpty() || line.startsWith("#") || !line.contains("=")) {
            return;
        }
        if (line.startsWith("export ")) {
            line = line.substring("export ".length()).trim();
        }
        int separator = line.indexOf('=');
        String key = line.substring(0, separator).trim();
        String value = stripQuotes(line.substring(separator + 1).trim());
        if (!key.isEmpty()) {
            values.put(key, value);
        }
    }

    private static String stripQuotes(String value) {
        if (value.length() >= 2) {
            char first = value.charAt(0);
            char last = value.charAt(value.length() - 1);
            if ((first == '"' && last == '"') || (first == '\'' && last == '\'')) {
                return value.substring(1, value.length() - 1);
            }
        }
        return value;
    }
}
