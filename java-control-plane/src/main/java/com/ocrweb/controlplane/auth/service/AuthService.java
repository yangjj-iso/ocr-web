package com.ocrweb.controlplane.auth.service;

import com.ocrweb.controlplane.auth.domain.AppUserEntity;
import com.ocrweb.controlplane.auth.dto.AuthDtos;
import com.ocrweb.controlplane.auth.repository.AppUserRepository;
import com.ocrweb.controlplane.config.AuthProperties;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.transaction.Transactional;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.List;

@Service
public class AuthService {
    private final AppUserRepository appUserRepository;
    private final PasswordHashService passwordHashService;
    private final SessionTokenService sessionTokenService;
    private final AuthProperties authProperties;

    public AuthService(
            AppUserRepository appUserRepository,
            PasswordHashService passwordHashService,
            SessionTokenService sessionTokenService,
            AuthProperties authProperties
    ) {
        this.appUserRepository = appUserRepository;
        this.passwordHashService = passwordHashService;
        this.sessionTokenService = sessionTokenService;
        this.authProperties = authProperties;
    }

    public AuthDtos.AuthStatusResponse getAuthStatus(HttpServletRequest request) {
        CurrentUser user = resolveAuthenticatedUser(request);
        return new AuthDtos.AuthStatusResponse(
                authProperties.isEnabled(),
                user != null,
                user == null ? null : user.username(),
                user != null && user.isAdmin(),
                user == null ? null : user.userStatus(),
                authProperties.isEnabled() ? authProperties.getUsername() : null
        );
    }

    @Transactional
    public AuthDtos.RegisterResponse register(String username, String password) {
        ensureAuthEnabled();
        String normalizedUsername = normalizeUsername(username);
        if (normalizedUsername.equalsIgnoreCase(authProperties.getUsername())) {
            throw conflict("This username is reserved.");
        }

        AppUserEntity existing = appUserRepository.findByUsername(normalizedUsername).orElse(null);
        if (existing != null) {
            if ("pending".equals(existing.getStatus())) {
                throw conflict("This account is pending approval.");
            }
            if ("active".equals(existing.getStatus())) {
                throw conflict("This username is already in use.");
            }
            throw conflict("This account has been rejected.");
        }

        AppUserEntity user = new AppUserEntity();
        user.setUsername(normalizedUsername);
        user.setPasswordHash(passwordHashService.hashPassword(password));
        user.setStatus("pending");
        user.setAdmin(false);
        appUserRepository.save(user);

        return new AuthDtos.RegisterResponse(
                true,
                "pending",
                "Registration submitted. Please wait for administrator approval."
        );
    }

    public AuthLoginResult login(String username, String password) {
        if (!authProperties.isEnabled()) {
            return AuthLoginResult.disabled();
        }
        String normalizedUsername = normalizeUsername(username);
        String normalizedPassword = password == null ? "" : password;
        if (normalizedUsername.isBlank() || normalizedPassword.isBlank()) {
            throw badRequest("Username and password are required.");
        }

        if (authenticateEnvAdmin(normalizedUsername, normalizedPassword)) {
            CurrentUser currentUser = new CurrentUser(normalizedUsername, true, "active", null);
            return AuthLoginResult.authenticated(
                    new AuthDtos.LoginResponse(true, normalizedUsername, true, "active"),
                    buildAuthCookie(currentUser)
            );
        }

        AppUserEntity user = authenticateApplicationUser(normalizedUsername, normalizedPassword);
        CurrentUser currentUser = new CurrentUser(user.getUsername(), user.isAdmin(), user.getStatus(), user.getId());
        return AuthLoginResult.authenticated(
                new AuthDtos.LoginResponse(true, user.getUsername(), user.isAdmin(), user.getStatus()),
                buildAuthCookie(currentUser)
        );
    }

    public String buildLogoutCookie() {
        return ResponseCookie.from(authProperties.getCookieName(), "")
                .path("/")
                .httpOnly(true)
                .secure(authProperties.isCookieSecure())
                .sameSite(authProperties.getCookieSameSite())
                .maxAge(Duration.ZERO)
                .build()
                .toString();
    }

    public AuthDtos.PendingUsersResponse listPendingUsers(HttpServletRequest request) {
        requireAdmin(request);
        List<AuthDtos.PendingUserItem> items = appUserRepository.findByStatusOrderByCreatedAtDesc("pending")
                .stream()
                .map(user -> new AuthDtos.PendingUserItem(user.getId(), user.getUsername(), user.getStatus(), user.getCreatedAt()))
                .toList();
        return new AuthDtos.PendingUsersResponse(items);
    }

    @Transactional
    public AuthDtos.UserStatusResponse approveUser(Long userId, HttpServletRequest request) {
        requireAdmin(request);
        return updateUserStatus(userId, "active");
    }

    @Transactional
    public AuthDtos.UserStatusResponse rejectUser(Long userId, HttpServletRequest request) {
        requireAdmin(request);
        return updateUserStatus(userId, "rejected");
    }

    public AuthDtos.AllUsersResponse listAllUsers(HttpServletRequest request) {
        requireAdmin(request);
        List<AuthDtos.UserItem> items = appUserRepository.findAll()
                .stream()
                .map(user -> new AuthDtos.UserItem(user.getId(), user.getUsername(), user.getStatus(), user.isAdmin(), user.getCreatedAt()))
                .toList();
        return new AuthDtos.AllUsersResponse(items);
    }

    @Transactional
    public AuthDtos.UserStatusResponse setAdmin(Long userId, boolean admin, HttpServletRequest request) {
        requireAdmin(request);
        AppUserEntity user = appUserRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found."));
        user.setAdmin(admin);
        appUserRepository.save(user);
        return new AuthDtos.UserStatusResponse(user.getId(), user.getUsername(), user.getStatus());
    }

    public CurrentUser resolveAuthenticatedUser(HttpServletRequest request) {
        Object existing = request.getAttribute(CurrentUser.REQUEST_ATTRIBUTE);
        if (existing instanceof CurrentUser currentUser) {
            return currentUser;
        }
        CurrentUser resolved = resolveAuthenticatedUserInternal(request);
        if (resolved != null) {
            request.setAttribute(CurrentUser.REQUEST_ATTRIBUTE, resolved);
        }
        return resolved;
    }

    public CurrentUser requireAuthenticatedUser(HttpServletRequest request) {
        CurrentUser currentUser = resolveAuthenticatedUser(request);
        if (currentUser != null) {
            return currentUser;
        }
        throw unauthorized("Authentication required");
    }

    public CurrentUser requireAdmin(HttpServletRequest request) {
        CurrentUser currentUser = requireAuthenticatedUser(request);
        if (currentUser.isAdmin()) {
            return currentUser;
        }
        throw forbidden("Admin permission required.");
    }

    private CurrentUser resolveAuthenticatedUserInternal(HttpServletRequest request) {
        if (!authProperties.isEnabled()) {
            return new CurrentUser(authProperties.getUsername(), true, "active", null);
        }

        String cookieToken = extractCookie(request, authProperties.getCookieName());
        CurrentUser fromCookie = sessionTokenService.verifySessionToken(cookieToken);
        if (fromCookie != null) {
            return fromCookie;
        }

        BasicCredentials basicCredentials = extractBasicCredentials(request);
        if (basicCredentials != null && authenticateEnvAdmin(basicCredentials.username(), basicCredentials.password())) {
            return new CurrentUser(basicCredentials.username(), true, "active", null);
        }
        return null;
    }

    private AppUserEntity authenticateApplicationUser(String username, String password) {
        AppUserEntity user = appUserRepository.findByUsername(username).orElse(null);
        if (user == null || !passwordHashService.verifyPassword(password, user.getPasswordHash())) {
            throw unauthorized("Invalid username or password.");
        }
        if ("pending".equals(user.getStatus())) {
            throw forbidden("Account pending approval. Please contact administrator.");
        }
        if ("rejected".equals(user.getStatus())) {
            throw forbidden("Account rejected. Please contact administrator.");
        }
        if (!"active".equals(user.getStatus())) {
            throw forbidden("Account is unavailable.");
        }
        return user;
    }

    private AuthDtos.UserStatusResponse updateUserStatus(Long userId, String status) {
        AppUserEntity user = appUserRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found."));
        user.setStatus(status);
        appUserRepository.save(user);
        return new AuthDtos.UserStatusResponse(user.getId(), user.getUsername(), user.getStatus());
    }

    private String buildAuthCookie(CurrentUser currentUser) {
        return ResponseCookie.from(
                        authProperties.getCookieName(),
                        sessionTokenService.createSessionToken(
                                currentUser.username(),
                                currentUser.userId(),
                                currentUser.isAdmin(),
                                currentUser.userStatus()
                        )
                )
                .path("/")
                .httpOnly(true)
                .secure(authProperties.isCookieSecure())
                .sameSite(authProperties.getCookieSameSite())
                .maxAge(Duration.ofSeconds(authProperties.getSessionTtl()))
                .build()
                .toString();
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

    private BasicCredentials extractBasicCredentials(HttpServletRequest request) {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith("Basic ")) {
            return null;
        }
        try {
            String decoded = new String(Base64.getDecoder().decode(header.substring(6)), StandardCharsets.UTF_8);
            int separator = decoded.indexOf(':');
            if (separator < 0) {
                return null;
            }
            return new BasicCredentials(decoded.substring(0, separator), decoded.substring(separator + 1));
        } catch (IllegalArgumentException error) {
            return null;
        }
    }

    private void ensureAuthEnabled() {
        if (authProperties.isEnabled()) {
            return;
        }
        throw badRequest("Auth is disabled.");
    }

    private boolean authenticateEnvAdmin(String username, String password) {
        return authProperties.getUsername().equals(username) && authProperties.getPassword().equals(password);
    }

    private String normalizeUsername(String username) {
        return username == null ? "" : username.trim();
    }

    private static ResponseStatusException badRequest(String detail) {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, detail);
    }

    private static ResponseStatusException unauthorized(String detail) {
        return new ResponseStatusException(HttpStatus.UNAUTHORIZED, detail);
    }

    private static ResponseStatusException forbidden(String detail) {
        return new ResponseStatusException(HttpStatus.FORBIDDEN, detail);
    }

    private static ResponseStatusException conflict(String detail) {
        return new ResponseStatusException(HttpStatus.CONFLICT, detail);
    }

    private record BasicCredentials(String username, String password) {
    }

    public record AuthLoginResult(boolean enabled, AuthDtos.LoginResponse payload, String setCookieHeader) {
        static AuthLoginResult disabled() {
            return new AuthLoginResult(false, null, null);
        }

        static AuthLoginResult authenticated(AuthDtos.LoginResponse payload, String setCookieHeader) {
            return new AuthLoginResult(true, payload, setCookieHeader);
        }
    }
}
