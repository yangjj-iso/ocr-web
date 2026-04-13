package com.ocrweb.controlplane.dev.service;

import com.ocrweb.controlplane.config.DevDashboardProperties;
import com.ocrweb.controlplane.dev.dto.DevDashboardDtos;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.Locale;

@Service
public class DevDashboardAuthService {
    private static final int CODE_DIGITS = 6;
    private static final long CODE_STEP_SECONDS = 30;
    private final DevDashboardProperties properties;

    public DevDashboardAuthService(DevDashboardProperties properties) {
        this.properties = properties;
    }

    public LoginResult login(String username, String password, String twoFactorCode) {
        if (!properties.isEnabled()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Dev dashboard is disabled.");
        }
        if (!secureEquals(properties.getUsername(), safe(username)) || !secureEquals(properties.getPassword(), password == null ? "" : password)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Dashboard username or password is invalid.");
        }
        if (!verifyTwoFactorCode(twoFactorCode)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Dashboard 2FA code is invalid.");
        }
        Instant expiresAt = Instant.now().plusSeconds(Math.max(60, properties.getSessionTtl()));
        String token = createToken(properties.getUsername(), expiresAt);
        return new LoginResult(
                new DevDashboardDtos.LoginResponse(true, properties.getUsername(), expiresAt),
                buildCookie(token, Duration.ofSeconds(Math.max(60, properties.getSessionTtl())))
        );
    }

    public DevDashboardDtos.AuthStatusResponse status(HttpServletRequest request) {
        DevDashboardDtos.Session session = resolveSession(request);
        return new DevDashboardDtos.AuthStatusResponse(
                properties.isEnabled(),
                session != null,
                session == null ? null : session.username(),
                session == null ? null : session.expiresAt()
        );
    }

    public DevDashboardDtos.Session requireSession(HttpServletRequest request) {
        DevDashboardDtos.Session session = resolveSession(request);
        if (session == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Dashboard authentication required.");
        }
        return session;
    }

    public DevDashboardDtos.Session resolveSession(HttpServletRequest request) {
        if (!properties.isEnabled()) {
            return new DevDashboardDtos.Session(properties.getUsername(), Instant.now().plusSeconds(3600));
        }
        String token = extractCookie(request);
        return verifyToken(token);
    }

    public String buildLogoutCookie() {
        return buildCookie("", Duration.ZERO);
    }

    private boolean verifyTwoFactorCode(String twoFactorCode) {
        String normalizedCode = safe(twoFactorCode).replace(" ", "");
        if (!normalizedCode.matches("\\d{6}")) {
            return false;
        }
        byte[] secret = decodeBase32(properties.getTwoFactorSecret());
        long currentCounter = Instant.now().getEpochSecond() / CODE_STEP_SECONDS;
        int window = Math.max(0, properties.getTwoFactorWindowSteps());
        for (long offset = -window; offset <= window; offset++) {
            if (secureEquals(generateAuthenticatorCode(secret, currentCounter + offset), normalizedCode)) {
                return true;
            }
        }
        return false;
    }

    private String generateAuthenticatorCode(byte[] secret, long counter) {
        try {
            Mac mac = Mac.getInstance("HmacSHA1");
            mac.init(new SecretKeySpec(secret, "HmacSHA1"));
            byte[] hash = mac.doFinal(ByteBuffer.allocate(Long.BYTES).putLong(counter).array());
            int offset = hash[hash.length - 1] & 0x0f;
            int binary = ((hash[offset] & 0x7f) << 24)
                    | ((hash[offset + 1] & 0xff) << 16)
                    | ((hash[offset + 2] & 0xff) << 8)
                    | (hash[offset + 3] & 0xff);
            int otp = binary % (int) Math.pow(10, CODE_DIGITS);
            return String.format(Locale.ROOT, "%06d", otp);
        } catch (Exception error) {
            throw new IllegalStateException("Failed to generate dashboard 2FA code.", error);
        }
    }

    private String createToken(String username, Instant expiresAt) {
        String payload = username + "|" + expiresAt.getEpochSecond();
        String encodedPayload = Base64.getUrlEncoder().withoutPadding().encodeToString(payload.getBytes(StandardCharsets.UTF_8));
        return encodedPayload + "." + sign(encodedPayload);
    }

    private DevDashboardDtos.Session verifyToken(String token) {
        if (token == null || token.isBlank() || !token.contains(".")) {
            return null;
        }
        String[] parts = token.split("\\.", 2);
        String encodedPayload = parts[0];
        if (!secureEquals(sign(encodedPayload), parts[1])) {
            return null;
        }
        try {
            String payload = new String(decodeBase64Url(encodedPayload), StandardCharsets.UTF_8);
            int separator = payload.lastIndexOf('|');
            if (separator < 0) {
                return null;
            }
            String username = payload.substring(0, separator);
            Instant expiresAt = Instant.ofEpochSecond(Long.parseLong(payload.substring(separator + 1)));
            if (expiresAt.isBefore(Instant.now()) || !secureEquals(properties.getUsername(), username)) {
                return null;
            }
            return new DevDashboardDtos.Session(username, expiresAt);
        } catch (Exception ignored) {
            return null;
        }
    }

    private String sign(String encodedPayload) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(properties.getSessionSecret().getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] digest = mac.doFinal(encodedPayload.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(digest.length * 2);
            for (byte value : digest) {
                builder.append(String.format("%02x", value));
            }
            return builder.toString();
        } catch (Exception error) {
            throw new IllegalStateException("Failed to sign dashboard session.", error);
        }
    }

    private String buildCookie(String value, Duration maxAge) {
        return ResponseCookie.from(properties.getCookieName(), value)
                .path("/")
                .httpOnly(true)
                .secure(properties.isCookieSecure())
                .sameSite(properties.getCookieSameSite())
                .maxAge(maxAge)
                .build()
                .toString();
    }

    private String extractCookie(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) {
            return null;
        }
        for (Cookie cookie : cookies) {
            if (properties.getCookieName().equals(cookie.getName())) {
                return cookie.getValue();
            }
        }
        return null;
    }

    private static byte[] decodeBase64Url(String value) {
        int remainder = value.length() % 4;
        String padded = remainder == 0 ? value : value + "=".repeat(4 - remainder);
        return Base64.getUrlDecoder().decode(padded);
    }

    private static byte[] decodeBase32(String value) {
        String normalized = safe(value).replace("=", "").replace(" ", "").toUpperCase(Locale.ROOT);
        ByteBuffer buffer = ByteBuffer.allocate(Math.max(1, normalized.length() * 5 / 8));
        int bits = 0;
        int bitCount = 0;
        for (int i = 0; i < normalized.length(); i++) {
            int decoded = decodeBase32Char(normalized.charAt(i));
            bits = (bits << 5) | decoded;
            bitCount += 5;
            if (bitCount >= 8) {
                buffer.put((byte) ((bits >> (bitCount - 8)) & 0xff));
                bitCount -= 8;
            }
        }
        byte[] result = new byte[buffer.position()];
        buffer.flip();
        buffer.get(result);
        return result;
    }

    private static int decodeBase32Char(char value) {
        if (value >= 'A' && value <= 'Z') {
            return value - 'A';
        }
        if (value >= '2' && value <= '7') {
            return value - '2' + 26;
        }
        throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Invalid dashboard 2FA secret.");
    }

    private static boolean secureEquals(String left, String right) {
        byte[] leftBytes = safe(left).getBytes(StandardCharsets.UTF_8);
        byte[] rightBytes = safe(right).getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(leftBytes, rightBytes);
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    public record LoginResult(DevDashboardDtos.LoginResponse payload, String setCookieHeader) {
    }
}
