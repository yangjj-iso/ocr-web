package com.ocrweb.controlplane.health;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/health")
public class HealthController {
    private final ControlPlaneHealthService controlPlaneHealthService;

    public HealthController(ControlPlaneHealthService controlPlaneHealthService) {
        this.controlPlaneHealthService = controlPlaneHealthService;
    }

    @GetMapping("/live")
    public Map<String, Object> live() {
        return controlPlaneHealthService.live();
    }

    @GetMapping("/ready")
    public ResponseEntity<Map<String, Object>> ready() {
        return buildDependencyResponse(controlPlaneHealthService.readiness());
    }

    @GetMapping("/deps")
    public ResponseEntity<Map<String, Object>> deps() {
        return buildDependencyResponse(controlPlaneHealthService.readiness());
    }

    private static ResponseEntity<Map<String, Object>> buildDependencyResponse(ControlPlaneHealthService.ReadinessReport report) {
        return ResponseEntity.status(report.ready() ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE)
                .body(report.payload());
    }
}
