package com.ocrweb.controlplane.task.service;

import com.ocrweb.controlplane.archive.service.PathAccessService;
import com.ocrweb.controlplane.config.StorageProperties;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class TaskStorageService {
    private static final byte[] EMPTY_BYTES = new byte[0];
    private static final String EMPTY_SHA256 = sha256Hex(EMPTY_BYTES);
    private static final DateTimeFormatter AMZ_DATE_FORMAT =
            DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC);
    private static final DateTimeFormatter DATE_STAMP_FORMAT =
            DateTimeFormatter.ofPattern("yyyyMMdd").withZone(ZoneOffset.UTC);

    private final StorageProperties properties;
    private final PathAccessService pathAccessService;
    private final HttpClient httpClient;
    private final Path uploadRoot;

    public TaskStorageService(StorageProperties properties, PathAccessService pathAccessService) throws IOException {
        this.properties = properties;
        this.pathAccessService = pathAccessService;
        this.httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(30)).build();
        if (isLocalBackend()) {
            this.uploadRoot = Path.of(properties.getUploadDir()).toAbsolutePath().normalize();
            Files.createDirectories(this.uploadRoot);
        } else {
            this.uploadRoot = null;
        }
    }

    public StoredFileHandle saveUpload(MultipartFile file, String relativePath) throws IOException {
        String filename = StringUtils.cleanPath(
                StringUtils.hasText(file.getOriginalFilename()) ? file.getOriginalFilename() : "upload.bin"
        );
        String folderHint = extractRelativeFolder(relativePath);
        String logicalPath = joinLogicalPath(folderHint, filename);
        String objectKey = buildObjectKey(folderHint, filename);
        byte[] content = file.getBytes();
        String contentType = StringUtils.hasText(file.getContentType())
                ? file.getContentType()
                : guessContentType(filename);
        return storeBytes(content, logicalPath, objectKey, contentType);
    }

    public StoredFileHandle saveExistingPath(String rawPath) throws IOException {
        Path source = pathAccessService.ensureAllowedPath(rawPath, true, false);
        String filename = source.getFileName().toString();
        String relativeHint = relativePathWithinAllowedRoots(source.getParent());
        String objectKey = buildObjectKey(relativeHint, filename);
        byte[] content = Files.readAllBytes(source);
        String contentType = Files.probeContentType(source);
        return storeBytes(
                content,
                source.toString(),
                objectKey,
                StringUtils.hasText(contentType) ? contentType : guessContentType(filename)
        );
    }

    public StoredFileResource loadTaskResource(OcrTaskEntity task) throws IOException {
        String filename = StringUtils.hasText(task.getFilename()) ? task.getFilename() : "task-" + task.getId();
        String contentType = guessContentType(filename);

        if (!StringUtils.hasText(task.getStorageObjectKey())) {
            Path legacyPath = Path.of(task.getFilePath()).toAbsolutePath().normalize();
            return new StoredFileResource(
                    Files.readAllBytes(legacyPath),
                    probeContentType(legacyPath, filename),
                    filename
            );
        }

        if ("local".equalsIgnoreCase(safe(task.getStorageProvider()))) {
            Path localPath = Path.of(task.getStorageObjectKey()).toAbsolutePath().normalize();
            return new StoredFileResource(
                    Files.readAllBytes(localPath),
                    probeContentType(localPath, filename),
                    filename
            );
        }

        byte[] bytes = downloadRemoteObject(
                safe(task.getStorageBucket(), properties.getBucket()),
                task.getStorageObjectKey()
        );
        return new StoredFileResource(bytes, contentType, filename);
    }

    private StoredFileHandle storeBytes(
            byte[] content,
            String logicalPath,
            String objectKey,
            String contentType
    ) throws IOException {
        String sha256 = sha256Hex(content);
        long sizeBytes = content.length;
        if (isLocalBackend()) {
            Path target = uploadRoot.resolve(objectKey).normalize();
            if (!target.startsWith(uploadRoot)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Resolved upload path is outside storage root.");
            }
            Path targetParent = target.getParent() == null ? uploadRoot : target.getParent();
            Files.createDirectories(targetParent);
            Files.write(target, content);
            return new StoredFileHandle(
                    logicalPath,
                    "local",
                    "",
                    target.toString(),
                    contentType,
                    sha256,
                    sizeBytes
            );
        }

        uploadRemoteObject(properties.getBucket(), objectKey, contentType, content);
        return new StoredFileHandle(
                logicalPath,
                "s3",
                properties.getBucket(),
                objectKey,
                contentType,
                sha256,
                sizeBytes
        );
    }

    private void uploadRemoteObject(String bucket, String objectKey, String contentType, byte[] content) throws IOException {
        ensureRemoteConfigured();
        URI uri = buildObjectUri(bucket, objectKey);
        HttpRequest request = signedRequest("PUT", uri, content, contentType);
        sendExpectingSuccess(request, "Failed to upload object to MinIO/OSS.");
    }

    private byte[] downloadRemoteObject(String bucket, String objectKey) throws IOException {
        ensureRemoteConfigured();
        URI uri = buildObjectUri(bucket, objectKey);
        HttpRequest request = signedRequest("GET", uri, EMPTY_BYTES, null);
        return sendForBytes(request, "Failed to download object from MinIO/OSS.");
    }

    private HttpRequest signedRequest(String method, URI uri, byte[] payload, String contentType) {
        Instant now = Instant.now();
        String amzDate = AMZ_DATE_FORMAT.format(now);
        String dateStamp = DATE_STAMP_FORMAT.format(now);
        byte[] safePayload = payload == null ? EMPTY_BYTES : payload;
        String payloadHash = "GET".equalsIgnoreCase(method) ? EMPTY_SHA256 : sha256Hex(safePayload);

        String hostHeader = hostHeader(uri);
        String canonicalHeaders = "host:" + hostHeader + "\n"
                + "x-amz-content-sha256:" + payloadHash + "\n"
                + "x-amz-date:" + amzDate + "\n";
        String signedHeaders = "host;x-amz-content-sha256;x-amz-date";
        String credentialScope = dateStamp + "/" + safe(properties.getRegion(), "us-east-1") + "/s3/aws4_request";
        String canonicalRequest = method.toUpperCase(Locale.ROOT) + "\n"
                + safe(uri.getRawPath()) + "\n"
                + safe(uri.getRawQuery()) + "\n"
                + canonicalHeaders + "\n"
                + signedHeaders + "\n"
                + payloadHash;
        String stringToSign = "AWS4-HMAC-SHA256\n"
                + amzDate + "\n"
                + credentialScope + "\n"
                + sha256Hex(canonicalRequest.getBytes(StandardCharsets.UTF_8));
        byte[] signingKey = signingKey(dateStamp, safe(properties.getRegion(), "us-east-1"));
        String signature = HexFormat.of().formatHex(hmacSha256(signingKey, stringToSign));
        String authorization = "AWS4-HMAC-SHA256 Credential=" + properties.getAccessKey() + "/" + credentialScope
                + ", SignedHeaders=" + signedHeaders
                + ", Signature=" + signature;

        HttpRequest.Builder builder = HttpRequest.newBuilder(uri)
                .timeout(Duration.ofSeconds(300))
                .header("x-amz-content-sha256", payloadHash)
                .header("x-amz-date", amzDate)
                .header("Authorization", authorization);
        if (StringUtils.hasText(contentType)) {
            builder.header("Content-Type", contentType);
        }
        if ("PUT".equalsIgnoreCase(method)) {
            return builder.PUT(HttpRequest.BodyPublishers.ofByteArray(safePayload)).build();
        }
        return builder.GET().build();
    }

    private void sendExpectingSuccess(HttpRequest request, String message) throws IOException {
        try {
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY,
                        message + " status=" + response.statusCode()
                );
            }
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IOException(message, error);
        }
    }

    private byte[] sendForBytes(HttpRequest request, String message) throws IOException {
        try {
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new ResponseStatusException(
                        HttpStatus.BAD_GATEWAY,
                        message + " status=" + response.statusCode()
                );
            }
            return response.body();
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IOException(message, error);
        }
    }

    private URI buildObjectUri(String bucket, String objectKey) {
        String endpoint = safe(properties.getEndpoint()).replaceAll("/+$", "");
        if (!StringUtils.hasText(endpoint)) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "S3 storage endpoint is not configured.");
        }
        String encodedKey = encodeObjectKey(objectKey);
        if (properties.isPathStyle()) {
            return URI.create(endpoint + "/" + encodePathSegment(bucket) + "/" + encodedKey);
        }
        URI baseUri = URI.create(endpoint);
        String authority = encodePathSegment(bucket) + "." + baseUri.getHost()
                + (baseUri.getPort() > 0 ? ":" + baseUri.getPort() : "");
        return URI.create(baseUri.getScheme() + "://" + authority + "/" + encodedKey);
    }

    private void ensureRemoteConfigured() {
        List<String> missing = List.of(
                missing("ocr.storage.endpoint", properties.getEndpoint()),
                missing("ocr.storage.bucket", properties.getBucket()),
                missing("ocr.storage.access-key", properties.getAccessKey()),
                missing("ocr.storage.secret-key", properties.getSecretKey())
        ).stream().filter(StringUtils::hasText).toList();
        if (!missing.isEmpty()) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "S3 storage backend is incomplete: missing " + String.join(", ", missing)
            );
        }
    }

    private boolean isLocalBackend() {
        return !"s3".equalsIgnoreCase(safe(properties.getBackend(), "local"));
    }

    private String buildObjectKey(String relativePath, String filename) {
        String normalizedRelative = safe(relativePath)
                .replace('\\', '/')
                .replaceAll("^/+", "")
                .replaceAll("/+$", "");
        String prefix = safe(properties.getKeyPrefix(), "uploads")
                .replace('\\', '/')
                .replaceAll("^/+", "")
                .replaceAll("/+$", "");
        String safeFilename = UUID.randomUUID() + "_" + StringUtils.cleanPath(filename);
        String joined = prefix;
        if (StringUtils.hasText(normalizedRelative)) {
            joined = joined + "/" + normalizedRelative;
        }
        return joined + "/" + safeFilename;
    }

    private static String joinLogicalPath(String relativePath, String filename) {
        String cleanedRelative = safe(relativePath)
                .replace('\\', '/')
                .replaceAll("^/+", "")
                .replaceAll("/+$", "");
        if (!StringUtils.hasText(cleanedRelative)) {
            return filename;
        }
        return cleanedRelative + "/" + filename;
    }

    private static String extractRelativeFolder(String relativePath) {
        String normalized = safe(relativePath).replace('\\', '/');
        List<String> segments = java.util.Arrays.stream(normalized.split("/"))
                .filter(StringUtils::hasText)
                .toList();
        if (segments.size() <= 1) {
            return "";
        }
        return String.join("/", segments.subList(0, segments.size() - 1));
    }

    private String relativePathWithinAllowedRoots(Path sourceParent) {
        if (sourceParent == null) {
            return "";
        }
        for (Path root : pathAccessService.getAllowedRoots()) {
            if (sourceParent.startsWith(root)) {
                return root.relativize(sourceParent).toString();
            }
        }
        return "";
    }

    private static String probeContentType(Path path, String filename) throws IOException {
        String contentType = Files.probeContentType(path);
        return StringUtils.hasText(contentType) ? contentType : guessContentType(filename);
    }

    private static String guessContentType(String filename) {
        String lower = safe(filename).toLowerCase(Locale.ROOT);
        if (lower.endsWith(".pdf")) {
            return "application/pdf";
        }
        if (lower.endsWith(".png")) {
            return "image/png";
        }
        if (lower.endsWith(".bmp")) {
            return "image/bmp";
        }
        if (lower.endsWith(".tiff") || lower.endsWith(".tif")) {
            return "image/tiff";
        }
        return "image/jpeg";
    }

    private static String missing(String name, String value) {
        return StringUtils.hasText(value) ? "" : name;
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private static String safe(String value, String fallback) {
        return StringUtils.hasText(value) ? value.trim() : fallback;
    }

    private static String encodeObjectKey(String objectKey) {
        return List.of(safe(objectKey).split("/"))
                .stream()
                .filter(StringUtils::hasText)
                .map(TaskStorageService::encodePathSegment)
                .collect(Collectors.joining("/"));
    }

    private static String encodePathSegment(String value) {
        return URLEncoder.encode(safe(value), StandardCharsets.UTF_8)
                .replace("+", "%20")
                .replace("%2F", "/");
    }

    private static String hostHeader(URI uri) {
        int port = uri.getPort();
        if (port < 0) {
            return uri.getHost();
        }
        if (("http".equalsIgnoreCase(uri.getScheme()) && port == 80)
                || ("https".equalsIgnoreCase(uri.getScheme()) && port == 443)) {
            return uri.getHost();
        }
        return uri.getHost() + ":" + port;
    }

    private byte[] signingKey(String dateStamp, String region) {
        byte[] kDate = hmacSha256(("AWS4" + properties.getSecretKey()).getBytes(StandardCharsets.UTF_8), dateStamp);
        byte[] kRegion = hmacSha256(kDate, region);
        byte[] kService = hmacSha256(kRegion, "s3");
        return hmacSha256(kService, "aws4_request");
    }

    private static byte[] hmacSha256(byte[] key, String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
        } catch (Exception error) {
            throw new IllegalStateException("Failed to calculate HMAC-SHA256.", error);
        }
    }

    private static String sha256Hex(byte[] content) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(content));
        } catch (Exception error) {
            throw new IllegalStateException("Failed to calculate SHA-256.", error);
        }
    }

    public record StoredFileHandle(
            String logicalPath,
            String storageProvider,
            String bucket,
            String objectKey,
            String contentType,
            String sha256,
            long sizeBytes
    ) {
    }

    public record StoredFileResource(byte[] content, String contentType, String filename) {
    }
}
