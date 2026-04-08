package com.ocrweb.controlplane.archive.service;

import com.ocrweb.controlplane.config.LocalPathProperties;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ResponseStatusException;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

@Service
public class PathAccessService {
    private final List<Path> allowedRoots;

    public PathAccessService(LocalPathProperties localPathProperties) {
        this.allowedRoots = localPathProperties.getRoots().stream()
                .filter(StringUtils::hasText)
                .map(Path::of)
                .map(path -> path.toAbsolutePath().normalize())
                .toList();
    }

    public Path ensureAllowedPath(String rawPath, boolean expectFile, boolean expectDir) {
        if (!StringUtils.hasText(rawPath)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Path is required.");
        }
        Path candidate = Path.of(rawPath).toAbsolutePath().normalize();
        if (!candidate.isAbsolute()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Only absolute paths are allowed.");
        }
        if (!isWithinRoots(candidate)) {
            String allowed = String.join(", ", allowedRoots.stream().map(Path::toString).toList());
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Path is outside allowed roots: " + allowed);
        }
        if (expectFile && (!candidate.toFile().exists() || !candidate.toFile().isFile())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "File does not exist: " + candidate);
        }
        if (expectDir && (!candidate.toFile().exists() || !candidate.toFile().isDirectory())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Directory does not exist: " + candidate);
        }
        return candidate;
    }

    public List<Path> getAllowedRoots() {
        return new ArrayList<>(allowedRoots);
    }

    private boolean isWithinRoots(Path candidate) {
        for (Path root : allowedRoots) {
            if (candidate.startsWith(root)) {
                return true;
            }
        }
        return false;
    }
}
