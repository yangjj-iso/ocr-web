package com.ocrweb.controlplane.auth.service;

import org.springframework.stereotype.Service;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Base64;

@Service
public class PasswordHashService {
    private static final String ALGORITHM = "pbkdf2_sha256";
    private static final int DEFAULT_ITERATIONS = 240_000;
    private static final int SALT_BYTES = 16;

    private final SecureRandom secureRandom = new SecureRandom();

    public String hashPassword(String password) {
        byte[] salt = new byte[SALT_BYTES];
        secureRandom.nextBytes(salt);
        byte[] digest = pbkdf2(password, salt, DEFAULT_ITERATIONS);
        return ALGORITHM
                + "$" + DEFAULT_ITERATIONS
                + "$" + encode(salt)
                + "$" + encode(digest);
    }

    public boolean verifyPassword(String password, String passwordHash) {
        if (passwordHash == null || passwordHash.isBlank()) {
            return false;
        }
        try {
            String[] parts = passwordHash.split("\\$", 4);
            if (parts.length != 4 || !ALGORITHM.equals(parts[0])) {
                return false;
            }
            int iterations = Integer.parseInt(parts[1]);
            byte[] salt = decode(parts[2]);
            byte[] expected = decode(parts[3]);
            byte[] actual = pbkdf2(password, salt, iterations);
            return java.security.MessageDigest.isEqual(actual, expected);
        } catch (RuntimeException error) {
            return false;
        }
    }

    private static byte[] pbkdf2(String password, byte[] salt, int iterations) {
        try {
            PBEKeySpec spec = new PBEKeySpec(password.toCharArray(), salt, iterations, 256);
            return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded();
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException("Failed to hash password.", error);
        }
    }

    private static String encode(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private static byte[] decode(String value) {
        int remainder = value.length() % 4;
        String padded = remainder == 0 ? value : value + "=".repeat(4 - remainder);
        return Base64.getUrlDecoder().decode(padded);
    }
}
