package com.ocrweb.controlplane.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.servers.Server;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI ocrWebOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("OmniScan Control Plane API")
                        .description("OCR 任务管理、文件上传、批次评估、QA 问答等接口")
                        .version("1.0.0")
                        .contact(new Contact().name("OmniScan Team")))
                .servers(List.of(
                        new Server().url("/").description("当前服务器")));
    }
}
