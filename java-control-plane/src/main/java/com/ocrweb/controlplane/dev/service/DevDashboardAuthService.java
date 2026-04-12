package com.ocrweb.controlplane.dev.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.config.AuthProperties;
import com.ocrweb.controlplane.config.DevDashboardProperties;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class DevDashboardAuthService {
    private static final String ROLE = "dev_dashboard";
    private final DevDashboardProperties properties;
    private final AuthProperties authProperties;
    private final ObjectMapper objectMapper;

    public DevDashboardAuthService(
            DevDashboardProperties properties,
            AuthProperties authProperties,
            ObjectMapper objectMapper
    ) {
        this.properties = properties;
        this.authProperties = authProperties;
        this.objectMapper = objectMapper;
    }

    public boolean isConfigured() {
        return properties.isEnabled()
                && StringUtils.hasText(properties.getUsername())
                && StringUtils.hasText(properties.getPassword());
    }

    public String authenticate(String username, String password) {
        if (!isConfigured()) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Dev dashboard credentials are not configured.");
        }
        if (!constantEquals(properties.getUsername(), username) || !constantEquals(properties.getPassword(), password)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid credentials.");
        }
        return buildCookie(username);
    }

    public String buildLogoutCookie() {
        return ResponseCookie.from(properties.getCookieName(), "")
                .path("/")
                .httpOnly(true)
                .secure(authProperties.isCookieSecure())
                .sameSite(authProperties.getCookieSameSite())
                .maxAge(Duration.ZERO)
                .build()
                .toString();
    }

    public String resolveUsername(HttpServletRequest request) {
        String token = extractCookie(request, properties.getCookieName());
        Map<String, Object> payload = verifyToken(token);
        if (payload == null) {
            return "";
        }
        String role = String.valueOf(payload.getOrDefault("role", ""));
        if (!ROLE.equals(role)) {
            return "";
        }
        return String.valueOf(payload.getOrDefault("sub", ""));
    }

    public String requireAuthenticated(HttpServletRequest request) {
        if (!isConfigured()) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Dev dashboard credentials are not configured.");
        }
        String username = resolveUsername(request);
        if (!StringUtils.hasText(username)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Dev dashboard login required.");
        }
        return username;
    }

    private String buildCookie(String username) {
        String token = createToken(username);
        return ResponseCookie.from(properties.getCookieName(), token)
                .path("/")
                .httpOnly(true)
                .secure(authProperties.isCookieSecure())
                .sameSite(authProperties.getCookieSameSite())
                .maxAge(Duration.ofSeconds(Math.max(1, properties.getSessionTtl())))
                .build()
                .toString();
    }

    private String createToken(String username) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("sub", username);
        payload.put("exp", Instant.now().getEpochSecond() + Math.max(1, properties.getSessionTtl()));
        payload.put("role", ROLE);
        String encodedPayload = Base64.getUrlEncoder().withoutPadding().encodeToString(writeJson(payload));
        return encodedPayload + "." + sign(encodedPayload);
    }

    private Map<String, Object> verifyToken(String token) {
        if (!StringUtils.hasText(token) || !token.contains(".")) {
            return null;
        }
        String[] parts = token.split("\\.", 2);
        if (!constantEquals(sign(parts[0]), parts[1])) {
            return null;
        }
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> payload = objectMapper.readValue(
                    new String(decodeBase64Url(parts[0]), StandardCharsets.UTF_8),
                    Map.class
            );
            long exp = asLong(payload.get("exp"));
            return exp >= Instant.now().getEpochSecond() ? payload : null;
        } catch (Exception error) {
            return null;
        }
    }

    private byte[] writeJson(Map<String, Object> payload) {
        try {
            return objectMapper.writeValueAsBytes(payload);
        } catch (JsonProcessingException error) {
            throw new IllegalStateException("Failed to serialize dev dashboard session.", error);
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
            throw new IllegalStateException("Failed to sign dev dashboard session.", error);
        }
    }

    private String extractCookie(HttpServletRequest request, String cookieName) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) {
            return null;
        }
        for (Cookie cookie : cookies) {
            if (cookieName.equals(cookie.getName())) {
                return cookie.getValue();
            }
        }
        return null;
    }

    private static boolean constantEquals(String expected, String actual) {
        byte[] expectedBytes = String.valueOf(expected).getBytes(StandardCharsets.UTF_8);
        byte[] actualBytes = String.valueOf(actual).getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(expectedBytes, actualBytes);
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
}
