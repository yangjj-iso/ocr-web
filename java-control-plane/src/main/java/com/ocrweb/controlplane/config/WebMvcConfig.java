package com.ocrweb.controlplane.config;

import com.ocrweb.controlplane.dev.web.DevDashboardAuthInterceptor;
import com.ocrweb.controlplane.web.PublicApiAuthInterceptor;
import com.ocrweb.controlplane.web.RequestRateLimitingInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {
    private final ControlPlaneSecurityProperties securityProperties;
    private final PublicApiAuthInterceptor publicApiAuthInterceptor;
    private final DevDashboardAuthInterceptor devDashboardAuthInterceptor;
    private final RequestRateLimitingInterceptor requestRateLimitingInterceptor;

    public WebMvcConfig(
            ControlPlaneSecurityProperties securityProperties,
            PublicApiAuthInterceptor publicApiAuthInterceptor,
            DevDashboardAuthInterceptor devDashboardAuthInterceptor,
            RequestRateLimitingInterceptor requestRateLimitingInterceptor
    ) {
        this.securityProperties = securityProperties;
        this.publicApiAuthInterceptor = publicApiAuthInterceptor;
        this.devDashboardAuthInterceptor = devDashboardAuthInterceptor;
        this.requestRateLimitingInterceptor = requestRateLimitingInterceptor;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOriginPatterns(securityProperties.getCorsAllowedOrigins().toArray(String[]::new))
                .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .exposedHeaders(HttpHeaders.LOCATION, "X-Trace-Id")
                .allowCredentials(securityProperties.isCorsAllowCredentials())
                .maxAge(securityProperties.getCorsMaxAgeSeconds());
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(publicApiAuthInterceptor);
        registry.addInterceptor(devDashboardAuthInterceptor);
        registry.addInterceptor(requestRateLimitingInterceptor);
    }
}
