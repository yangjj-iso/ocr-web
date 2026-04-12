package com.ocrweb.controlplane.config;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DotenvFileSupportTest {

    @TempDir
    Path tempDir;

    @Test
    void upsertValuesPreservesExistingContentAndAppendsNewKeys() throws IOException {
        Path envFile = tempDir.resolve(".env");
        Files.writeString(envFile, """
                # sample
                AUTH_ENABLED=true
                DEV_DASHBOARD_USERNAME=old-admin
                """, StandardCharsets.UTF_8);

        Map<String, String> updates = new LinkedHashMap<>();
        updates.put("DEV_DASHBOARD_USERNAME", "new-admin");
        updates.put("OCR_AI_BASE_URL", "http://127.0.0.1:8001");
        DotenvFileSupport.upsertValues(envFile, updates);

        String content = Files.readString(envFile, StandardCharsets.UTF_8);
        assertTrue(content.contains("# sample"));
        assertTrue(content.contains("AUTH_ENABLED=true"));
        assertTrue(content.contains("DEV_DASHBOARD_USERNAME=new-admin"));
        assertTrue(content.contains("OCR_AI_BASE_URL=http://127.0.0.1:8001"));
    }

    @Test
    void parseDotenvReadsQuotedValues() throws IOException {
        Path envFile = tempDir.resolve(".env");
        Files.writeString(envFile, """
                AUTH_USERNAME=admin
                APP_NAME="OCR Dev Console"
                """, StandardCharsets.UTF_8);

        Map<String, String> values = DotenvFileSupport.parseDotenv(envFile);

        assertEquals("admin", values.get("AUTH_USERNAME"));
        assertEquals("OCR Dev Console", values.get("APP_NAME"));
    }
}
