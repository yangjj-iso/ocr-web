package com.ocrweb.controlplane.web;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Set;

/**
 * Double-submit cookie CSRF protection filter.
 *
 * On every response, sets a CSRF token cookie (XSRF-TOKEN).
 * On state-changing requests (POST/PUT/PATCH/DELETE), validates
 * that the X-XSRF-TOKEN header matches the cookie value.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class CsrfTokenFilter extends OncePerRequestFilter {

    private static final String CSRF_COOKIE_NAME = "XSRF-TOKEN";
    private static final String CSRF_HEADER_NAME = "X-XSRF-TOKEN";
    private static final Set<String> SAFE_METHODS = Set.of("GET", "HEAD", "OPTIONS", "TRACE");
    private static final int TOKEN_BYTE_LENGTH = 32;

    private final SecureRandom secureRandom = new SecureRandom();

    @Value("${ocr.csrf.enabled:true}")
    private boolean csrfEnabled;

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        if (!csrfEnabled) {
            filterChain.doFilter(request, response);
            return;
        }

        String csrfToken = getTokenFromCookie(request);

        // Generate token if not present
        if (csrfToken == null || csrfToken.isBlank()) {
            csrfToken = generateToken();
            setCsrfCookie(response, csrfToken);
        }

        // Validate on state-changing methods
        if (!SAFE_METHODS.contains(request.getMethod().toUpperCase())) {
            String headerToken = request.getHeader(CSRF_HEADER_NAME);
            if (headerToken == null || !headerToken.equals(csrfToken)) {
                response.setStatus(HttpServletResponse.SC_FORBIDDEN);
                response.setContentType("application/json");
                response.getWriter().write("{\"error\":\"CSRF token missing or invalid\"}");
                return;
            }
        }

        // Refresh cookie on every response to keep it alive
        setCsrfCookie(response, csrfToken);
        filterChain.doFilter(request, response);
    }

    private String getTokenFromCookie(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) return null;
        for (Cookie cookie : cookies) {
            if (CSRF_COOKIE_NAME.equals(cookie.getName())) {
                return cookie.getValue();
            }
        }
        return null;
    }

    private void setCsrfCookie(HttpServletResponse response, String token) {
        Cookie cookie = new Cookie(CSRF_COOKIE_NAME, token);
        cookie.setPath("/");
        cookie.setHttpOnly(false); // Must be readable by JavaScript
        cookie.setSecure(false);   // Set to true in production with HTTPS
        cookie.setMaxAge(86400);   // 24 hours
        response.addCookie(cookie);
    }

    private String generateToken() {
        byte[] bytes = new byte[TOKEN_BYTE_LENGTH];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
