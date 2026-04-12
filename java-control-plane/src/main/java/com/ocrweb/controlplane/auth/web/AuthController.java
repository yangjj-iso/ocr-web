package com.ocrweb.controlplane.auth.web;

import com.ocrweb.controlplane.auth.dto.AuthDtos;
import com.ocrweb.controlplane.auth.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @GetMapping("/me")
    public AuthDtos.AuthStatusResponse me(HttpServletRequest request) {
        return authService.getAuthStatus(request);
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody(required = false) AuthDtos.LoginRequest request) {
        String username = request == null ? "" : request.username();
        String password = request == null ? "" : request.password();
        AuthService.AuthLoginResult result = authService.login(username, password);
        if (!result.enabled()) {
            return ResponseEntity.status(HttpStatus.NO_CONTENT).build();
        }
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, result.setCookieHeader())
                .body(result.payload());
    }

    @PostMapping("/register")
    public AuthDtos.RegisterResponse register(@Valid @RequestBody AuthDtos.RegisterRequest request) {
        return authService.register(request.username(), request.password(), request.realName(), request.requestedRole());
    }

    @PostMapping("/change-password")
    public Map<String, Object> changePassword(
            @Valid @RequestBody AuthDtos.ChangePasswordRequest request,
            HttpServletRequest httpRequest) {
        return authService.changePassword(httpRequest, request.currentPassword(), request.newPassword());
    }

    @PutMapping("/me/display-name")
    public Map<String, Object> updateDisplayName(
            @RequestBody AuthDtos.UpdateDisplayNameRequest request,
            HttpServletRequest httpRequest) {
        return authService.updateDisplayName(httpRequest, request.displayName());
    }

    @PostMapping("/logout")
    public ResponseEntity<Map<String, Object>> logout() {
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, authService.buildLogoutCookie())
                .body(Map.of("authenticated", false));
    }

    @GetMapping("/pending-users")
    public AuthDtos.PendingUsersResponse pendingUsers(HttpServletRequest request) {
        return authService.listPendingUsers(request);
    }

    @PostMapping("/users/{userId}/approve")
    public AuthDtos.UserStatusResponse approveUser(@PathVariable Long userId, HttpServletRequest request) {
        return authService.approveUser(userId, request);
    }

    @PostMapping("/users/{userId}/reject")
    public AuthDtos.UserStatusResponse rejectUser(@PathVariable Long userId, HttpServletRequest request) {
        return authService.rejectUser(userId, request);
    }

    @PostMapping("/users/{userId}/reset-password")
    public Map<String, Object> resetUserPassword(
            @PathVariable Long userId,
            @Valid @RequestBody AuthDtos.ResetPasswordRequest body,
            HttpServletRequest request) {
        return authService.resetUserPassword(userId, body.newPassword(), request);
    }

    @DeleteMapping("/users/{userId}")
    public Map<String, Object> deleteUser(@PathVariable Long userId, HttpServletRequest request) {
        return authService.deleteUser(userId, request);
    }
}
