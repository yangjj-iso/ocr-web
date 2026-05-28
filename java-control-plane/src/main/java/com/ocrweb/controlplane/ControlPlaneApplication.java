package com.ocrweb.controlplane;

import com.ocrweb.controlplane.config.AiServiceProperties;
import com.ocrweb.controlplane.config.AuthProperties;
import com.ocrweb.controlplane.config.ControlPlaneSecurityProperties;
import com.ocrweb.controlplane.config.InternalApiProperties;
import com.ocrweb.controlplane.config.LocalPathProperties;
import com.ocrweb.controlplane.config.RateLimitProperties;
import com.ocrweb.controlplane.config.RabbitMqProperties;
import com.ocrweb.controlplane.config.StorageProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
@EnableConfigurationProperties({
        RabbitMqProperties.class,
        StorageProperties.class,
        InternalApiProperties.class,
        AiServiceProperties.class,
        AuthProperties.class,
        LocalPathProperties.class,
        ControlPlaneSecurityProperties.class,
        RateLimitProperties.class
})
public class ControlPlaneApplication {

    public static void main(String[] args) {
        SpringApplication.run(ControlPlaneApplication.class, args);
    }
}
