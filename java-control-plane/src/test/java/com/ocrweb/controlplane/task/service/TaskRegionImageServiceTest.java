package com.ocrweb.controlplane.task.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ocrweb.controlplane.task.domain.OcrTaskEntity;
import com.ocrweb.controlplane.task.repository.OcrTaskRepository;
import org.junit.jupiter.api.Test;

import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class TaskRegionImageServiceTest {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void buildRegionImageSupportsSealSnippetContentWithoutStoredBbox() throws Exception {
        OcrTaskRepository taskRepository = mock(OcrTaskRepository.class);
        TaskStorageService storageService = mock(TaskStorageService.class);
        TaskRegionImageService service = new TaskRegionImageService(taskRepository, storageService);

        OcrTaskEntity task = new OcrTaskEntity();
        task.setFilename("seal.jpg");
        task.setResultJson(objectMapper.readTree("""
                [
                  {
                    "page_num": 1,
                    "regions": [
                      {
                        "type": "text",
                        "content": "<div style=\\"text-align: center;\\"><img src=\\"imgs/img_in_seal_box_110_110_230_230.jpg\\" alt=\\"Image\\" width=\\"20%\\" /></div>"
                      }
                    ]
                  }
                ]
                """));

        when(taskRepository.findById(7L)).thenReturn(Optional.of(task));
        when(storageService.loadTaskResource(task)).thenReturn(
                new TaskStorageService.StoredFileResource(buildSealSample(), "image/jpeg", "seal.jpg")
        );

        TaskRegionImageService.RegionImagePayload payload = service.buildRegionImage(7L, 1, 0);

        assertThat(payload.mediaType()).isEqualTo("image/png");
        assertThat(payload.content()).isNotEmpty();

        BufferedImage image = ImageIO.read(new ByteArrayInputStream(payload.content()));
        assertThat(image).isNotNull();
        assertThat(image.getWidth()).isGreaterThan(120);
        assertThat(image.getHeight()).isGreaterThan(120);
        assertThat((image.getRGB(0, 0) >>> 24) & 0xFF).isEqualTo(0);

        int center = image.getRGB(image.getWidth() / 2, image.getHeight() / 2);
        int centerAlpha = (center >>> 24) & 0xFF;
        int centerRed = (center >>> 16) & 0xFF;
        int centerGreen = (center >>> 8) & 0xFF;
        int centerBlue = center & 0xFF;
        assertThat(centerAlpha).isGreaterThan(0);
        assertThat(centerRed).isGreaterThan(centerGreen);
        assertThat(centerRed).isGreaterThan(centerBlue);
    }

    private static byte[] buildSealSample() throws Exception {
        BufferedImage image = new BufferedImage(320, 320, BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics = image.createGraphics();
        try {
            graphics.setColor(Color.WHITE);
            graphics.fillRect(0, 0, 320, 320);
            graphics.setColor(Color.BLACK);
            graphics.fillRect(30, 36, 50, 18);
            graphics.setColor(new Color(225, 35, 45));
            graphics.drawOval(110, 110, 120, 120);
            graphics.drawOval(111, 111, 118, 118);
            graphics.drawOval(112, 112, 116, 116);
            graphics.fillOval(155, 155, 28, 28);
        } finally {
            graphics.dispose();
        }

        ByteArrayOutputStream output = new ByteArrayOutputStream();
        ImageIO.write(image, "jpg", output);
        return output.toByteArray();
    }
}
