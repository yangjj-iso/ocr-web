package com.ocrweb.controlplane.config;

import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class DotenvFileSupport {
    public static final String PROPERTY_SOURCE_NAME = "ocrDotenv";
    private static final int MAX_PARENT_DEPTH = 4;

    private DotenvFileSupport() {
    }

    public static Map<String, Object> loadDotenvValues() {
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

    public static List<Path> dotenvCandidates() {
        List<Path> candidates = new ArrayList<>();
        Path current = Path.of(System.getProperty("user.dir", ".")).toAbsolutePath().normalize();
        for (int depth = 0; current != null && depth < MAX_PARENT_DEPTH; depth++) {
            candidates.add(current.resolve(".env"));
            current = current.getParent();
        }
        return candidates;
    }

    public static Path resolveWritableDotenvPath() {
        for (Path candidate : dotenvCandidates()) {
            if (Files.isRegularFile(candidate)) {
                return candidate;
            }
        }
        List<Path> candidates = dotenvCandidates();
        return candidates.isEmpty() ? Path.of(".env").toAbsolutePath().normalize() : candidates.get(0);
    }

    public static Map<String, String> parseDotenv(Path path) {
        Map<String, String> values = new LinkedHashMap<>();
        for (Entry entry : readEntries(path)) {
            if (entry.key() != null) {
                values.put(entry.key(), entry.value());
            }
        }
        return values;
    }

    public static List<Entry> readEntries(Path path) {
        List<Entry> entries = new ArrayList<>();
        List<String> lines;
        try {
            lines = Files.exists(path) ? Files.readAllLines(path, StandardCharsets.UTF_8) : List.of();
        } catch (IOException error) {
            return entries;
        }
        for (String line : lines) {
            entries.add(parseLine(line));
        }
        return entries;
    }

    public static void upsertValues(Path path, Map<String, String> updates) throws IOException {
        if (updates == null || updates.isEmpty()) {
            return;
        }
        List<Entry> entries = readEntries(path);
        List<Entry> rewritten = new ArrayList<>(entries.size() + updates.size() + 2);
        Set<String> applied = new LinkedHashSet<>();
        for (Entry entry : entries) {
            if (entry.key() != null && updates.containsKey(entry.key())) {
                rewritten.add(new Entry(entry.key() + "=" + formatValue(updates.get(entry.key())), entry.key(), updates.get(entry.key())));
                applied.add(entry.key());
            } else {
                rewritten.add(entry);
            }
        }
        if (!rewritten.isEmpty() && !rewritten.get(rewritten.size() - 1).raw().isBlank()) {
            rewritten.add(new Entry("", null, null));
        }
        for (Map.Entry<String, String> update : updates.entrySet()) {
            if (applied.contains(update.getKey())) {
                continue;
            }
            rewritten.add(new Entry(update.getKey() + "=" + formatValue(update.getValue()), update.getKey(), update.getValue()));
        }
        writeEntries(path, rewritten);
    }

    public static void writeEntries(Path path, List<Entry> entries) throws IOException {
        Path parent = path.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        List<String> lines = entries.stream().map(Entry::raw).toList();
        Files.write(path, lines, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
    }

    static Entry parseLine(String rawLine) {
        String line = rawLine.trim();
        if (!StringUtils.hasText(line) || line.startsWith("#")) {
            return new Entry(rawLine, null, null);
        }
        String normalized = line.startsWith("export ") ? line.substring("export ".length()).trim() : line;
        int separator = normalized.indexOf('=');
        if (separator <= 0) {
            return new Entry(rawLine, null, null);
        }
        String key = normalized.substring(0, separator).trim();
        if (!StringUtils.hasText(key)) {
            return new Entry(rawLine, null, null);
        }
        String value = unquote(normalized.substring(separator + 1).trim());
        return new Entry(rawLine, key, value);
    }

    static String formatValue(String value) {
        String safeValue = value == null ? "" : value;
        boolean requiresQuoting = safeValue.contains(" ") || safeValue.contains("\t") || safeValue.startsWith("#");
        if (!requiresQuoting) {
            return safeValue;
        }
        return "\"" + safeValue
                .replace("\\", "\\\\")
                .replace("\"", "\\\"") + "\"";
    }

    static String unquote(String value) {
        if (value.length() < 2) {
            return value;
        }
        char first = value.charAt(0);
        char last = value.charAt(value.length() - 1);
        if ((first == '"' && last == '"') || (first == '\'' && last == '\'')) {
            return value.substring(1, value.length() - 1)
                    .replace("\\\"", "\"")
                    .replace("\\\\", "\\");
        }
        return value;
    }

    public record Entry(String raw, String key, String value) {
    }
}
