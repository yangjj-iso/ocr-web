package com.ocrweb.controlplane.dev.service;

import com.ocrweb.controlplane.config.AiServiceProperties;
import com.ocrweb.controlplane.config.AuthProperties;
import com.ocrweb.controlplane.config.ControlPlaneSecurityProperties;
import com.ocrweb.controlplane.config.DevDashboardProperties;
import com.ocrweb.controlplane.config.DotenvFileSupport;
import com.ocrweb.controlplane.config.InternalApiProperties;
import com.ocrweb.controlplane.dev.dto.DevDashboardDtos;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class DevDashboardRuntimeService {
    private static final List<RuntimeFieldDefinition> DEFINITIONS = List.of(
            new RuntimeFieldDefinition("DEV_DASHBOARD_ENABLED", "开发后台开关", "dashboard", "开发后台路由和登录入口。", "boolean", false, true),
            new RuntimeFieldDefinition("DEV_DASHBOARD_USERNAME", "后台账号", "dashboard", "用于 /dev/dashboard 登录。", "text", false, true),
            new RuntimeFieldDefinition("DEV_DASHBOARD_PASSWORD", "后台密码", "dashboard", "修改后新登录立即生效。", "password", true, true),
            new RuntimeFieldDefinition("DEV_DASHBOARD_COOKIE_NAME", "后台 Cookie 名", "dashboard", "开发后台会话 Cookie。", "text", false, true),
            new RuntimeFieldDefinition("DEV_DASHBOARD_SESSION_TTL", "后台会话时长", "dashboard", "单位秒。", "number", false, true),
            new RuntimeFieldDefinition("DEV_DASHBOARD_PYTHON_METRICS_PATH", "Python 指标路径", "dashboard", "控制面拉取 Python 指标的路径。", "text", false, true),
            new RuntimeFieldDefinition("CELERY_TASK_QUEUE", "Celery 队列名", "dashboard", "监控面板展示的 Python 侧队列。", "text", false, true),

            new RuntimeFieldDefinition("OCR_AI_BASE_URL", "AI 服务地址", "ai", "Java 控制面请求 Python AI 的根地址。", "url", false, true),
            new RuntimeFieldDefinition("OCR_AI_HEALTH_PATH", "AI 健康检查路径", "ai", "健康探测使用的接口路径。", "text", false, true),
            new RuntimeFieldDefinition("OCR_AI_CONNECT_TIMEOUT_SECONDS", "AI 连接超时", "ai", "单位秒。", "number", false, true),
            new RuntimeFieldDefinition("OCR_AI_READ_TIMEOUT_SECONDS", "AI 读取超时", "ai", "单位秒。", "number", false, true),

            new RuntimeFieldDefinition("OCR_INTERNAL_API_TOKEN", "内部 API Token", "internal", "Java 调 Python 内部指标接口使用。", "password", true, true),
            new RuntimeFieldDefinition("OCR_CONTROL_PLANE_BASE_URL", "控制面基地址", "internal", "内部回调与链路引用使用。", "url", false, true),

            new RuntimeFieldDefinition("OCR_REQUIRE_USER_AUTH", "强制业务登录", "auth", "关闭后业务接口不再要求主系统登录。", "boolean", false, true),
            new RuntimeFieldDefinition("AUTH_ENABLED", "业务认证开关", "auth", "主系统登录模块开关。", "boolean", false, true),
            new RuntimeFieldDefinition("AUTH_USERNAME", "业务管理员账号", "auth", "主系统默认管理员账号。", "text", false, true),
            new RuntimeFieldDefinition("AUTH_PASSWORD", "业务管理员密码", "auth", "主系统默认管理员密码。", "password", true, true),
            new RuntimeFieldDefinition("AUTH_SECRET", "业务会话密钥", "auth", "修改后旧会话会失效。", "password", true, true),
            new RuntimeFieldDefinition("AUTH_COOKIE_NAME", "业务 Cookie 名", "auth", "主系统登录 Cookie 名。", "text", false, true),
            new RuntimeFieldDefinition("AUTH_COOKIE_SECURE", "业务 Cookie Secure", "auth", "HTTPS 环境建议开启。", "boolean", false, true),
            new RuntimeFieldDefinition("AUTH_COOKIE_SAMESITE", "业务 Cookie SameSite", "auth", "lax / strict / none。", "text", false, true),
            new RuntimeFieldDefinition("AUTH_SESSION_TTL", "业务会话时长", "auth", "单位秒。", "number", false, true)
    );

    private static final List<GroupDefinition> GROUPS = List.of(
            new GroupDefinition("dashboard", "开发后台运行环境", "影响 /dev/dashboard 的登录、指标抓取和队列展示。"),
            new GroupDefinition("ai", "AI 服务连接", "面板更新后，新请求会立即使用新的 AI 连接配置。"),
            new GroupDefinition("internal", "内部调用", "控制面与 Python 内部接口通信使用的配置。"),
            new GroupDefinition("auth", "业务认证", "修改后新登录和新请求立即按最新规则执行。")
    );

    private final ConfigurableEnvironment environment;
    private final DevDashboardProperties devDashboardProperties;
    private final AiServiceProperties aiServiceProperties;
    private final InternalApiProperties internalApiProperties;
    private final AuthProperties authProperties;
    private final ControlPlaneSecurityProperties securityProperties;

    public DevDashboardRuntimeService(
            ConfigurableEnvironment environment,
            DevDashboardProperties devDashboardProperties,
            AiServiceProperties aiServiceProperties,
            InternalApiProperties internalApiProperties,
            AuthProperties authProperties,
            ControlPlaneSecurityProperties securityProperties
    ) {
        this.environment = environment;
        this.devDashboardProperties = devDashboardProperties;
        this.aiServiceProperties = aiServiceProperties;
        this.internalApiProperties = internalApiProperties;
        this.authProperties = authProperties;
        this.securityProperties = securityProperties;
    }

    public DevDashboardDtos.RuntimeEnvironmentSnapshot snapshot() {
        Path envPath = DotenvFileSupport.resolveWritableDotenvPath();
        Map<String, String> fileValues = DotenvFileSupport.parseDotenv(envPath);
        List<DevDashboardDtos.EnvironmentGroup> groups = GROUPS.stream()
                .map(group -> new DevDashboardDtos.EnvironmentGroup(
                        group.key(),
                        group.label(),
                        group.description(),
                        DEFINITIONS.stream()
                                .filter(definition -> group.key().equals(definition.group()))
                                .map(definition -> toField(definition, fileValues))
                                .toList()
                ))
                .toList();
        return new DevDashboardDtos.RuntimeEnvironmentSnapshot(
                envPath.toString(),
                OffsetDateTime.now(ZoneOffset.UTC),
                groups
        );
    }

    public DevDashboardDtos.RuntimeEnvironmentSnapshot update(DevDashboardDtos.EnvironmentUpdateRequest request) {
        Map<String, String> normalized = normalizeUpdates(request);
        if (normalized.isEmpty()) {
            return snapshot();
        }
        Path envPath = DotenvFileSupport.resolveWritableDotenvPath();
        try {
            DotenvFileSupport.upsertValues(envPath, normalized);
        } catch (IOException error) {
            throw new IllegalStateException("Failed to write .env file.", error);
        }
        refreshPropertySource();
        applyUpdates(normalized);
        return snapshot();
    }

    private DevDashboardDtos.EnvironmentField toField(RuntimeFieldDefinition definition, Map<String, String> fileValues) {
        String value = environment.getProperty(definition.key());
        if (value == null) {
            value = fileValues.getOrDefault(definition.key(), "");
        }
        boolean configured = switch (definition.type()) {
            case "boolean", "number" -> value != null;
            default -> StringUtils.hasText(value);
        };
        return new DevDashboardDtos.EnvironmentField(
                definition.key(),
                definition.label(),
                definition.description(),
                definition.type(),
                definition.sensitive(),
                configured,
                definition.runtimeApplied(),
                definition.sensitive() ? "" : (value == null ? "" : value),
                definition.sensitive()
                        ? (configured ? "已配置，留空表示保持不变" : "未配置，输入后保存")
                        : ""
        );
    }

    private Map<String, String> normalizeUpdates(DevDashboardDtos.EnvironmentUpdateRequest request) {
        Map<String, RuntimeFieldDefinition> definitionsByKey = new LinkedHashMap<>();
        for (RuntimeFieldDefinition definition : DEFINITIONS) {
            definitionsByKey.put(definition.key(), definition);
        }
        Map<String, String> updates = new LinkedHashMap<>();
        if (request == null || request.values() == null) {
            return updates;
        }
        for (DevDashboardDtos.EnvironmentValueUpdate valueUpdate : request.values()) {
            if (valueUpdate == null || !StringUtils.hasText(valueUpdate.key())) {
                continue;
            }
            RuntimeFieldDefinition definition = definitionsByKey.get(valueUpdate.key());
            if (definition == null) {
                continue;
            }
            String value = valueUpdate.value() == null ? "" : valueUpdate.value().trim();
            if (definition.sensitive() && !StringUtils.hasText(value)) {
                continue;
            }
            updates.put(definition.key(), value);
        }
        return updates;
    }

    private void refreshPropertySource() {
        Map<String, Object> values = DotenvFileSupport.loadDotenvValues();
        MapPropertySource propertySource = new MapPropertySource(DotenvFileSupport.PROPERTY_SOURCE_NAME, values);
        if (environment.getPropertySources().contains(DotenvFileSupport.PROPERTY_SOURCE_NAME)) {
            environment.getPropertySources().replace(DotenvFileSupport.PROPERTY_SOURCE_NAME, propertySource);
            return;
        }
        if (environment.getPropertySources().contains(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME)) {
            environment.getPropertySources().addAfter(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME, propertySource);
        } else {
            environment.getPropertySources().addFirst(propertySource);
        }
    }

    private void applyUpdates(Map<String, String> updates) {
        for (Map.Entry<String, String> entry : updates.entrySet()) {
            switch (entry.getKey()) {
                case "DEV_DASHBOARD_ENABLED" -> devDashboardProperties.setEnabled(parseBoolean(entry.getValue()));
                case "DEV_DASHBOARD_USERNAME" -> devDashboardProperties.setUsername(entry.getValue());
                case "DEV_DASHBOARD_PASSWORD" -> devDashboardProperties.setPassword(entry.getValue());
                case "DEV_DASHBOARD_COOKIE_NAME" -> devDashboardProperties.setCookieName(entry.getValue());
                case "DEV_DASHBOARD_SESSION_TTL" -> devDashboardProperties.setSessionTtl(parseInt(entry.getValue(), devDashboardProperties.getSessionTtl()));
                case "DEV_DASHBOARD_PYTHON_METRICS_PATH" -> devDashboardProperties.setPythonMetricsPath(entry.getValue());
                case "CELERY_TASK_QUEUE" -> devDashboardProperties.setCeleryQueue(entry.getValue());

                case "OCR_AI_BASE_URL" -> aiServiceProperties.setBaseUrl(entry.getValue());
                case "OCR_AI_HEALTH_PATH" -> aiServiceProperties.setHealthPath(entry.getValue());
                case "OCR_AI_CONNECT_TIMEOUT_SECONDS" -> aiServiceProperties.setConnectTimeoutSeconds(parseInt(entry.getValue(), aiServiceProperties.getConnectTimeoutSeconds()));
                case "OCR_AI_READ_TIMEOUT_SECONDS" -> aiServiceProperties.setReadTimeoutSeconds(parseInt(entry.getValue(), aiServiceProperties.getReadTimeoutSeconds()));

                case "OCR_INTERNAL_API_TOKEN" -> internalApiProperties.setToken(entry.getValue());
                case "OCR_CONTROL_PLANE_BASE_URL" -> internalApiProperties.setBaseUrl(entry.getValue());

                case "OCR_REQUIRE_USER_AUTH" -> securityProperties.setRequireUserAuth(parseBoolean(entry.getValue()));
                case "AUTH_ENABLED" -> authProperties.setEnabled(parseBoolean(entry.getValue()));
                case "AUTH_USERNAME" -> authProperties.setUsername(entry.getValue());
                case "AUTH_PASSWORD" -> authProperties.setPassword(entry.getValue());
                case "AUTH_SECRET" -> authProperties.setSecret(entry.getValue());
                case "AUTH_COOKIE_NAME" -> authProperties.setCookieName(entry.getValue());
                case "AUTH_COOKIE_SECURE" -> authProperties.setCookieSecure(parseBoolean(entry.getValue()));
                case "AUTH_COOKIE_SAMESITE" -> authProperties.setCookieSameSite(entry.getValue());
                case "AUTH_SESSION_TTL" -> authProperties.setSessionTtl(parseInt(entry.getValue(), authProperties.getSessionTtl()));
                default -> {
                }
            }
        }
    }

    private static boolean parseBoolean(String value) {
        return "true".equalsIgnoreCase(value) || "1".equals(value) || "yes".equalsIgnoreCase(value) || "on".equalsIgnoreCase(value);
    }

    private static int parseInt(String value, int fallback) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException error) {
            return fallback;
        }
    }

    private record RuntimeFieldDefinition(
            String key,
            String label,
            String group,
            String description,
            String type,
            boolean sensitive,
            boolean runtimeApplied
    ) {
    }

    private record GroupDefinition(String key, String label, String description) {
    }
}
