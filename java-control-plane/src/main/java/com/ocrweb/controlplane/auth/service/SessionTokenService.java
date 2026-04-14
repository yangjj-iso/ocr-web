package com.ocrweb.controlplane.auth.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.ocrweb.controlplane.config.AuthProperties;
import org.springframework.stereotype.Service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class SessionTokenService {
    private final AuthProperties authProperties;
    private final ObjectMapper objectMapper;

    public SessionTokenService(AuthProperties authProperties, ObjectMapper objectMapper) {
        this.authProperties = authProperties;
        this.objectMapper = objectMapper.copy().configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
    }

    public String createSessionToken(String username, Long userId, boolean isAdmin, String userStatus, String role, String tenantId, String capabilities) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("sub", username);
        payload.put("exp", Instant.now().getEpochSecond() + authProperties.getSessionTtl());
        payload.put("uid", userId);
        payload.put("is_admin", isAdmin);
        payload.put("user_status", userStatus == null || userStatus.isBlank() ? "active" : userStatus);
        payload.put("role", role == null || role.isBlank() ? (isAdmin ? "admin" : "member") : role);
        payload.put("tenant_id", tenantId == null || tenantId.isBlank() ? "default" : tenantId);
        payload.put("capabilities", capabilities == null ? "" : capabilities);
        String encodedPayload = Base64.getUrlEncoder().withoutPadding().encodeToString(writeJson(payload));
        return encodedPayload + "." + sign(encodedPayload);
    }

    /** Backwards-compatible overload without capabilities. */
    public String createSessionToken(String username, Long userId, boolean isAdmin, String userStatus, String role, String tenantId) {
        return createSessionToken(username, userId, isAdmin, userStatus, role, tenantId, "");
    }

    /** Backwards-compatible overload without tenantId or capabilities. */
    public String createSessionToken(String username, Long userId, boolean isAdmin, String userStatus, String role) {
        return createSessionToken(username, userId, isAdmin, userStatus, role, "default", "");
    }

    public CurrentUser verifySessionToken(String token) {
        if (token == null || token.isBlank() || !token.contains(".")) {
            return null;
        }
        String[] parts = token.split("\\.", 2);
        String payloadEncoded = parts[0];
        String signature = parts[1];
        if (!sign(payloadEncoded).equals(signature)) {
            return null;
        }
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> payload = objectMapper.readValue(
                    new String(decodeBase64Url(payloadEncoded), StandardCharsets.UTF_8),
                    Map.class
            );
            long exp = asLong(payload.get("exp"));
            if (exp < Instant.now().getEpochSecond()) {
                return null;
            }
            String userStatus = asString(payload.get("user_status"), "active");
            if (!"active".equalsIgnoreCase(userStatus)) {
                return null;
            }
            return new CurrentUser(
                    asString(payload.get("sub"), ""),
                    asBoolean(payload.get("is_admin")),
                    userStatus,
                    asNullableLong(payload.get("uid")),
                    asString(payload.get("role"), "member"),
                    asString(payload.get("tenant_id"), "default"),
                    asString(payload.get("capabilities"), "")
            );
        } catch (Exception error) {
            return null;
        }
    }

    private byte[] writeJson(Map<String, Object> payload) {
        try {
            return objectMapper.writeValueAsBytes(payload);
        } catch (JsonProcessingException error) {
            throw new IllegalStateException("Failed to serialize session payload.", error);
        }
    }

    private String sign(String encodedPayload) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(authProperties.getSecret().getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] digest = mac.doFinal(encodedPayload.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(digest.length * 2);
            for (byte value : digest) {
                builder.append(String.format("%02x", value));
            }
            return builder.toString();
        } catch (Exception error) {
            throw new IllegalStateException("Failed to sign session token.", error);
        }
    }

    private static byte[] decodeBase64Url(String value) {
        int remainder = value.length() % 4;
        String padded = remainder == 0 ? value : value + "=".repeat(4 - remainder);
        return Base64.getUrlDecoder().decode(padded);
    }

    private static long asLong(Object value) {
        if (value instanceof Number number) {
            return number.longValue();
        }
        return Long.parseLong(String.valueOf(value));
    }

    private static Long asNullableLong(Object value) {
        if (value == null || "null".equals(String.valueOf(value))) {
            return null;
        }
        if (value instanceof Number number) {
            return number.longValue();
        }
        String text = String.valueOf(value).trim();
        return text.isBlank() ? null : Long.parseLong(text);
    }

    private static boolean asBoolean(Object value) {
        if (value instanceof Boolean bool) {
            return bool;
        }
        return Boolean.parseBoolean(String.valueOf(value));
    }

    private static String asString(Object value, String defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        String text = String.valueOf(value);
        return text.isBlank() ? defaultValue : text;
    }
}
