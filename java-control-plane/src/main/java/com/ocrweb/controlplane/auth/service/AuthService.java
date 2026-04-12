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
import java.util.Locale;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class AuthService {
    private static final Set<String> OPERATOR_ROLES = Set.of("admin", "operator");
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
        String displayName = null;
        if (user != null) {
            if (user.userId() != null) {
                AppUserEntity entity = appUserRepository.findById(user.userId()).orElse(null);
                if (entity != null) displayName = entity.getDisplayName();
            } else if (user.isAdmin()) {
                displayName = "系统管理员";
            }
        }
        return new AuthDtos.AuthStatusResponse(
                authProperties.isEnabled(),
                user != null,
                user == null ? null : user.username(),
                user != null && user.isAdmin(),
                user == null ? null : user.userStatus(),
                authProperties.isEnabled() ? authProperties.getUsername() : null,
                user == null ? null : user.effectiveRole(),
                displayName
        );
    }

    private static final java.util.Set<String> ALLOWED_REGISTER_ROLES = java.util.Set.of("operator", "searcher");

    @Transactional
    public AuthDtos.RegisterResponse register(String username, String password, String realName, String requestedRole) {
        ensureAuthEnabled();
        String normalizedUsername = normalizeUsername(username);
        if (normalizedUsername.isBlank()) {
            throw badRequest("工号不能为空。");
        }
        if (normalizedUsername.equalsIgnoreCase(authProperties.getUsername())) {
            throw conflict("该工号为系统管理员账号，不允许自行注册。");
        }

        AppUserEntity existing = appUserRepository.findByUsername(normalizedUsername).orElse(null);
        if (existing != null) {
            if ("pending".equals(existing.getStatus())) {
                throw conflict("该工号已提交注册申请，请等待管理员审核。");
            }
            if ("active".equals(existing.getStatus())) {
                throw conflict("该工号已被注册，如有疑问请联系管理员。");
            }
            throw conflict("该工号的申请已被拒绝，请联系管理员。");
        }

        String trimmedRealName = (realName == null) ? "" : realName.strip();
        if (trimmedRealName.isEmpty()) {
            throw badRequest("真实姓名不能为空。");
        }

        String role = (requestedRole != null && ALLOWED_REGISTER_ROLES.contains(requestedRole)) ? requestedRole : "operator";

        AppUserEntity user = new AppUserEntity();
        user.setUsername(normalizedUsername);
        user.setPasswordHash(passwordHashService.hashPassword(password));
        user.setStatus("pending");
        user.setAdmin(false);
        user.setRole(role);
        user.setDisplayName(trimmedRealName);
        appUserRepository.save(user);

        String roleLabel = "operator".equals(role) ? "签录员" : "检索者";
        return new AuthDtos.RegisterResponse(
                true,
                "pending",
                "注册申请已提交（申请角色：" + roleLabel + "），请等待管理员审核。"
        );
    }

    public AuthLoginResult login(String username, String password) {
        if (!authProperties.isEnabled()) {
            return AuthLoginResult.disabled();
        }
        String normalizedUsername = normalizeUsername(username);
        String normalizedPassword = password == null ? "" : password;
        if (normalizedUsername.isBlank() || normalizedPassword.isBlank()) {
            throw badRequest("工号和密码不能为空。");
        }

        if (authenticateEnvAdmin(normalizedUsername, normalizedPassword)) {
            CurrentUser currentUser = new CurrentUser(normalizedUsername, true, "active", null, "admin");
            return AuthLoginResult.authenticated(
                    new AuthDtos.LoginResponse(true, normalizedUsername, true, "active", "admin"),
                    buildAuthCookie(currentUser)
            );
        }

        AppUserEntity user = authenticateApplicationUser(normalizedUsername, normalizedPassword);
        CurrentUser currentUser = new CurrentUser(user.getUsername(), user.isAdmin(), user.getStatus(), user.getId(), user.getRole());
        return AuthLoginResult.authenticated(
                new AuthDtos.LoginResponse(true, user.getUsername(), user.isAdmin(), user.getStatus(), user.getRole()),
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
                .map(user -> new AuthDtos.PendingUserItem(user.getId(), user.getUsername(), user.getDisplayName(), user.getRole(), user.getStatus(), user.getCreatedAt()))
                .toList();
        return new AuthDtos.PendingUsersResponse(items);
    }

    @Transactional
    public Map<String, Object> changePassword(HttpServletRequest request, String currentPassword, String newPassword) {
        ensureAuthEnabled();
        CurrentUser current = requireAuthenticatedUser(request);
        if (current.userId() == null) {
            throw badRequest("系统管理员账号的密码通过环境变量配置，无法在线修改。");
        }
        AppUserEntity user = appUserRepository.findByUsername(current.username())
                .orElseThrow(() -> unauthorized("用户不存在。"));
        if (!passwordHashService.verifyPassword(currentPassword, user.getPasswordHash())) {
            throw badRequest("当前密码错误。");
        }
        user.setPasswordHash(passwordHashService.hashPassword(newPassword));
        appUserRepository.save(user);
        return Map.of("ok", true, "message", "密码已修改，请重新登录。");
    }

    @Transactional
    public Map<String, Object> updateDisplayName(HttpServletRequest request, String displayName) {
        CurrentUser current = requireAuthenticatedUser(request);
        if (current.userId() == null) {
            throw badRequest("系统管理员账号的显示名无法修改。");
        }
        AppUserEntity user = appUserRepository.findByUsername(current.username())
                .orElseThrow(() -> unauthorized("用户不存在。"));
        String trimmed = displayName == null ? null : displayName.strip();
        user.setDisplayName(trimmed == null || trimmed.isEmpty() ? null : trimmed);
        appUserRepository.save(user);
        return Map.of("ok", true, "display_name", trimmed == null ? "" : trimmed);
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

    @Transactional
    public Map<String, Object> resetUserPassword(Long userId, String newPassword, HttpServletRequest request) {
        requireAdmin(request);
        AppUserEntity user = appUserRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在。"));
        user.setPasswordHash(passwordHashService.hashPassword(newPassword));
        appUserRepository.save(user);
        return Map.of("ok", true, "message", "已重置 " + user.getUsername() + " 的密码。");
    }

    @Transactional
    public Map<String, Object> deleteUser(Long userId, HttpServletRequest request) {
        requireAdmin(request);
        AppUserEntity user = appUserRepository.findById(userId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "用户不存在。"));
        String username = user.getUsername();
        appUserRepository.delete(user);
        return Map.of("ok", true, "message", "已删除用户 " + username + "。");
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

    public CurrentUser requireOperatorOrAdmin(HttpServletRequest request) {
        return requireAnyRole(request, OPERATOR_ROLES, "Operator permission required.");
    }

    public CurrentUser requireAnyRole(HttpServletRequest request, Set<String> allowedRoles, String detail) {
        CurrentUser currentUser = requireAuthenticatedUser(request);
        String effectiveRole = currentUser.effectiveRole().toLowerCase(Locale.ROOT);
        if (currentUser.isAdmin() || allowedRoles.contains(effectiveRole)) {
            return currentUser;
        }
        throw forbidden(detail);
    }

    private CurrentUser resolveAuthenticatedUserInternal(HttpServletRequest request) {
        if (!authProperties.isEnabled()) {
            return new CurrentUser(authProperties.getUsername(), true, "active", null, "admin");
        }

        String cookieToken = extractCookie(request, authProperties.getCookieName());
        CurrentUser fromCookie = sessionTokenService.verifySessionToken(cookieToken);
        if (fromCookie != null) {
            return fromCookie;
        }

        BasicCredentials basicCredentials = extractBasicCredentials(request);
        if (basicCredentials != null && authenticateEnvAdmin(basicCredentials.username(), basicCredentials.password())) {
            return new CurrentUser(basicCredentials.username(), true, "active", null, "admin");
        }
        return null;
    }

    private AppUserEntity authenticateApplicationUser(String username, String password) {
        AppUserEntity user = appUserRepository.findByUsername(username).orElse(null);
        if (user == null || !passwordHashService.verifyPassword(password, user.getPasswordHash())) {
            throw unauthorized("工号或密码错误。");
        }
        if ("pending".equals(user.getStatus())) {
            throw forbidden("该账号正在等待管理员审核，请耐心等待。");
        }
        if ("rejected".equals(user.getStatus())) {
            throw forbidden("该账号已被驳回，请联系管理员。");
        }
        if (!"active".equals(user.getStatus())) {
            throw forbidden("该账号不可用，请联系管理员。");
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
                                currentUser.userStatus(),
                                currentUser.effectiveRole()
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
