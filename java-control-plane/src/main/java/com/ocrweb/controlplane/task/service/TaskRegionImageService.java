package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class TaskRegionImageService {
    private static final Pattern SEAL_BOX_PATH_RE = Pattern.compile(
            "img_in_(?:seal|stamp)_box_(\\d+)_(\\d+)_(\\d+)_(\\d+)\\.(?:png|jpe?g|bmp|webp|tiff?)",
            Pattern.CASE_INSENSITIVE
    );

    private final OcrTaskRepository taskRepository;
    private final TaskStorageService storageService;

    public TaskRegionImageService(OcrTaskRepository taskRepository, TaskStorageService storageService) {
        this.taskRepository = taskRepository;
        this.storageService = storageService;
    }

    public RegionImagePayload buildRegionImage(Long taskId, Integer pageNum, Integer regionIndex) throws IOException {
        if (pageNum == null || pageNum < 1) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "page_num must be greater than 0.");
        }
        if (regionIndex == null || regionIndex < 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "region_index must be greater than or equal to 0.");
        }

        OcrTaskEntity task = taskRepository.findById(taskId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Task not found."));
        JsonNode region = findRegion(task.getResultJson(), pageNum, regionIndex);
        double[] bbox = resolveRegionRect(region);
        if (bbox.length < 4) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Region bbox not found.");
        }

        TaskStorageService.StoredFileResource resource = storageService.loadTaskResource(task);
        BufferedImage source = ImageIO.read(new ByteArrayInputStream(resource.content()));
        if (source == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Task file is not a supported raster image.");
        }

        BufferedImage cropped = cropImage(source, bbox);
        if (shouldIsolateSeal(region)) {
            cropped = isolateRedForeground(cropped);
        } else if (cropped.getType() != BufferedImage.TYPE_INT_ARGB) {
            BufferedImage converted = new BufferedImage(cropped.getWidth(), cropped.getHeight(), BufferedImage.TYPE_INT_ARGB);
            converted.getGraphics().drawImage(cropped, 0, 0, null);
            cropped = converted;
        }

        ByteArrayOutputStream output = new ByteArrayOutputStream();
        ImageIO.write(cropped, "png", output);
        return new RegionImagePayload(output.toByteArray(), "image/png");
    }

    private static JsonNode findRegion(JsonNode rawResultJson, int pageNum, int regionIndex) {
        ArrayNode pages = normalizePages(rawResultJson);
        int pageIndex = pageNum - 1;
        if (pageIndex < 0 || pageIndex >= pages.size()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Page not found.");
        }

        JsonNode page = pages.get(pageIndex);
        JsonNode regions = page.path("regions");
        if (!regions.isArray() || regionIndex >= regions.size()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Region not found.");
        }
        return regions.get(regionIndex);
    }

    private static ArrayNode normalizePages(JsonNode rawResultJson) {
        if (rawResultJson == null || rawResultJson.isNull()) {
            return JsonNodeFactory.instance.arrayNode();
        }
        if (rawResultJson.isArray()) {
            return (ArrayNode) rawResultJson;
        }
        JsonNode pagesNode = rawResultJson.path("pages");
        if (pagesNode.isArray()) {
            return (ArrayNode) pagesNode;
        }
        ArrayNode single = JsonNodeFactory.instance.arrayNode();
        if (rawResultJson.isObject() && rawResultJson.has("page_num")) {
            single.add(rawResultJson);
        }
        return single;
    }

    private static double[] resolveRegionRect(JsonNode region) {
        double[] layoutRect = bboxToRect(region.path("layout_bbox"));
        if (layoutRect.length >= 4) {
            return layoutRect;
        }
        double[] bboxRect = bboxToRect(region.path("bbox"));
        if (bboxRect.length >= 4) {
            return bboxRect;
        }

        for (String value : candidateSnippetSources(region)) {
            double[] parsed = parseSealSnippetRect(value);
            if (parsed.length >= 4) {
                return parsed;
            }
        }
        return new double[0];
    }

    private static List<String> candidateSnippetSources(JsonNode region) {
        List<String> values = new ArrayList<>();
        if (region.hasNonNull("content")) {
            values.add(region.path("content").asText(""));
        }
        if (region.hasNonNull("html")) {
            values.add(region.path("html").asText(""));
        }
        JsonNode regionLines = region.path("region_lines");
        if (regionLines.isArray()) {
            for (JsonNode line : regionLines) {
                if (line.hasNonNull("text")) {
                    values.add(line.path("text").asText(""));
                }
            }
        }
        return values;
    }

    private static double[] bboxToRect(JsonNode node) {
        if (!node.isArray() || node.isEmpty()) {
            return new double[0];
        }
        JsonNode first = node.get(0);
        if (first != null && (first.isArray() || first.isObject())) {
            return rectFromPoints(node);
        }
        if (node.size() >= 4) {
            return new double[]{
                    node.get(0).asDouble(),
                    node.get(1).asDouble(),
                    node.get(2).asDouble(),
                    node.get(3).asDouble(),
            };
        }
        return new double[0];
    }

    private static double[] rectFromPoints(JsonNode pointsNode) {
        List<Double> xs = new ArrayList<>();
        List<Double> ys = new ArrayList<>();
        collectPoints(pointsNode, xs, ys);
        if (xs.isEmpty() || ys.isEmpty()) {
            return new double[0];
        }

        double minX = xs.stream().mapToDouble(Double::doubleValue).min().orElse(0.0);
        double minY = ys.stream().mapToDouble(Double::doubleValue).min().orElse(0.0);
        double maxX = xs.stream().mapToDouble(Double::doubleValue).max().orElse(0.0);
        double maxY = ys.stream().mapToDouble(Double::doubleValue).max().orElse(0.0);
        return maxX > minX && maxY > minY ? new double[]{minX, minY, maxX, maxY} : new double[0];
    }

    private static void collectPoints(JsonNode node, List<Double> xs, List<Double> ys) {
        if (node == null || node.isNull()) {
            return;
        }
        if (node.isObject()) {
            if (node.has("x") && node.has("y")) {
                xs.add(node.path("x").asDouble());
                ys.add(node.path("y").asDouble());
                return;
            }
            node.elements().forEachRemaining(child -> collectPoints(child, xs, ys));
            return;
        }
        if (!node.isArray()) {
            return;
        }
        if (node.size() >= 2 && node.get(0).isNumber() && node.get(1).isNumber()) {
            xs.add(node.get(0).asDouble());
            ys.add(node.get(1).asDouble());
            return;
        }
        node.elements().forEachRemaining(child -> collectPoints(child, xs, ys));
    }

    private static double[] parseSealSnippetRect(String value) {
        Matcher matcher = SEAL_BOX_PATH_RE.matcher(Optional.ofNullable(value).orElse(""));
        if (!matcher.find()) {
            return new double[0];
        }
        return new double[]{
                Double.parseDouble(matcher.group(1)),
                Double.parseDouble(matcher.group(2)),
                Double.parseDouble(matcher.group(3)),
                Double.parseDouble(matcher.group(4)),
        };
    }

    private static boolean shouldIsolateSeal(JsonNode region) {
        String type = region.path("type").asText("").trim().toLowerCase(Locale.ROOT);
        if ("seal".equals(type) || "stamp".equals(type)) {
            return true;
        }
        return candidateSnippetSources(region).stream().anyMatch(value -> SEAL_BOX_PATH_RE.matcher(value).find());
    }

    private static BufferedImage cropImage(BufferedImage image, double[] rect) {
        int imageWidth = image.getWidth();
        int imageHeight = image.getHeight();
        double paddingX = Math.max(12.0, imageWidth * 0.01);
        double paddingY = Math.max(12.0, imageHeight * 0.01);

        int left = Math.max(0, (int) Math.round(rect[0] - paddingX));
        int top = Math.max(0, (int) Math.round(rect[1] - paddingY));
        int right = Math.min(imageWidth, (int) Math.round(rect[2] + paddingX));
        int bottom = Math.min(imageHeight, (int) Math.round(rect[3] + paddingY));

        if (right <= left || bottom <= top) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Region bbox is outside the preview image.");
        }

        BufferedImage sourceSubImage = image.getSubimage(left, top, right - left, bottom - top);
        BufferedImage cropped = new BufferedImage(sourceSubImage.getWidth(), sourceSubImage.getHeight(), BufferedImage.TYPE_INT_ARGB);
        cropped.getGraphics().drawImage(sourceSubImage, 0, 0, null);
        return cropped;
    }

    private static BufferedImage isolateRedForeground(BufferedImage image) {
        int width = image.getWidth();
        int height = image.getHeight();
        int totalPixels = width * height;
        int requiredMaskPixels = Math.max(36, (int) (totalPixels * 0.008));

        BufferedImage isolated = new BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB);
        int matchedPixels = 0;
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int argb = image.getRGB(x, y);
                int red = (argb >> 16) & 0xFF;
                int green = (argb >> 8) & 0xFF;
                int blue = argb & 0xFF;

                boolean dominantRed = red >= 72;
                boolean redBias = red - Math.max(green, blue) >= 18;
                boolean warmRed = red >= 92 && red >= green + 10 && red >= blue + 10;
                boolean keep = dominantRed && (redBias || warmRed);
                if (keep) {
                    matchedPixels += 1;
                    isolated.setRGB(x, y, (0xFF << 24) | (red << 16) | (green << 8) | blue);
                } else {
                    isolated.setRGB(x, y, (red << 16) | (green << 8) | blue);
                }
            }
        }

        return matchedPixels >= requiredMaskPixels ? isolated : image;
    }

    public record RegionImagePayload(byte[] content, String mediaType) {
    }
}
