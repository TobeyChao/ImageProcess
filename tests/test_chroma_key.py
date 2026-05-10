"""Tests for chroma key background removal."""
import numpy as np
import pytest
from PIL import Image

# Import the skill module
from core import skills

chroma_key = skills.load("chroma-key")


class TestParseHexColor:
    def test_standard_hex(self):
        assert chroma_key.parse_hex_color("#FF0000") == (255, 0, 0)
        assert chroma_key.parse_hex_color("#00FF00") == (0, 255, 0)
        assert chroma_key.parse_hex_color("#0000FF") == (0, 0, 255)
        assert chroma_key.parse_hex_color("#FFFFFF") == (255, 255, 255)
        assert chroma_key.parse_hex_color("#000000") == (0, 0, 0)

    def test_hex_without_hash(self):
        assert chroma_key.parse_hex_color("FF0000") == (255, 0, 0)

    def test_short_hex(self):
        assert chroma_key.parse_hex_color("#F00") == (255, 0, 0)
        assert chroma_key.parse_hex_color("#FFF") == (255, 255, 255)
        assert chroma_key.parse_hex_color("000") == (0, 0, 0)

    def test_invalid_hex_raises(self):
        with pytest.raises(ValueError):
            chroma_key.parse_hex_color("not a color")
        with pytest.raises(ValueError):
            chroma_key.parse_hex_color("#GGGGGG")


class TestAutoDetectColor:
    def test_solid_color_image(self):
        """An image with a single solid color should detect that color."""
        img = Image.new("RGB", (100, 100), (128, 64, 200))
        color = chroma_key.auto_detect_color(img)
        assert color == (128, 64, 200)

    def test_image_with_corners_same_color(self):
        """Image where corners share the same background color."""
        img = Image.new("RGB", (200, 200), (0, 255, 0))
        # Draw a non-background rectangle in center
        arr = np.array(img)
        arr[50:150, 50:150] = (255, 0, 0)
        img = Image.fromarray(arr)
        color = chroma_key.auto_detect_color(img)
        assert color == (0, 255, 0)


class TestChromaKeyRemove:
    def test_solid_background_fully_removed(self):
        """Pure red image on pure blue background: all blue pixels become transparent."""
        img = Image.new("RGB", (50, 50), (0, 0, 255))  # blue background
        arr = np.array(img)
        # Red rectangle in center (NOT touching any edge)
        arr[10:40, 10:40] = (255, 0, 0)
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (0, 0, 255), tolerance=10)

        # Center pixel (red, foreground) should be opaque
        r, g, b, a = result.getpixel((25, 25))
        assert a == 255
        assert (r, g, b) == (255, 0, 0)

        # Edge pixel (blue, background) should be transparent
        r, g, b, a = result.getpixel((0, 0))
        assert a == 0

    def test_foreground_same_color_as_background_preserved(self):
        """Foreground has same color as background but not connected to edge."""
        img = Image.new("RGB", (50, 50), (0, 255, 0))  # green bg
        arr = np.array(img)
        # Red shape touching edges --- will NOT be flood-filled for green target
        arr[0:10, :] = (255, 0, 0)
        arr[40:50, :] = (255, 0, 0)
        arr[:, 0:10] = (255, 0, 0)
        arr[:, 40:50] = (255, 0, 0)
        # Isolated green block in center (same green as bg, but not connected)
        arr[20:30, 20:30] = (0, 255, 0)
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (0, 255, 0), tolerance=10)

        # The isolated green block should be opaque (not connected to edge)
        _, _, _, a = result.getpixel((25, 25))
        assert a == 255

    def test_tolerance_affects_result(self):
        """Higher tolerance causes more area to be reachable via flood fill."""
        # Background (100,100,100), center (115,115,115)
        # Euclidean distance ≈ 26: >10 but <40
        img = Image.new("RGB", (50, 50), (100, 100, 100))
        arr = np.array(img)
        arr[10:40, 10:40] = (115, 115, 115)
        img = Image.fromarray(arr)

        # Low tolerance: center pixels NOT candidates (26 > 10), so not flooded
        result_low = chroma_key.chroma_key_remove(img, (100, 100, 100), tolerance=10)
        # Higher tolerance: center pixels ARE candidates (26 < 40), so flooded
        result_high = chroma_key.chroma_key_remove(img, (100, 100, 100), tolerance=40)

        _, _, _, a_low = result_low.getpixel((25, 25))
        _, _, _, a_high = result_high.getpixel((25, 25))
        assert a_low == 255  # center fully opaque with low tolerance
        assert a_high < 255  # center partially transparent with high tolerance

    def test_white_background_common_case(self):
        """Common use case: white background UI element."""
        # White background with blue button
        img = Image.new("RGB", (100, 60), (255, 255, 255))
        arr = np.array(img)
        arr[15:45, 20:80] = (70, 130, 250)  # blue button
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (255, 255, 255), tolerance=20)

        # Button center should be fully opaque
        _, _, _, a_btn = result.getpixel((50, 30))
        assert a_btn == 255

        # Corner should be fully transparent
        _, _, _, a_corner = result.getpixel((0, 0))
        assert a_corner == 0

    def test_auto_color_detection(self):
        """Pass 'auto' as color should auto-detect background."""
        img = Image.new("RGB", (50, 50), (0, 255, 0))
        arr = np.array(img)
        arr[10:40, 10:40] = (255, 0, 0)
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, "auto", tolerance=10)

        _, _, _, a = result.getpixel((25, 25))
        assert a == 255  # foreground preserved
        _, _, _, a = result.getpixel((0, 0))
        assert a == 0  # background removed

    def test_output_is_rgba(self):
        img = Image.new("RGB", (20, 20), (255, 0, 0))
        result = chroma_key.chroma_key_remove(img, (255, 0, 0), tolerance=10)
        assert result.mode == "RGBA"

    def test_image_with_no_edges_to_flood(self):
        """Image where the target color only exists in isolated center region (not touching edges)."""
        img = Image.new("RGB", (50, 50), (255, 255, 255))
        arr = np.array(img)
        arr[20:30, 20:30] = (255, 0, 0)  # red square NOT touching edges
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (255, 0, 0), tolerance=10)

        # Red is not connected to edges, so it should all remain opaque
        _, _, _, a = result.getpixel((25, 25))
        assert a == 255

    def test_tolerance_zero(self):
        """tolerance=0 should only remove exact color matches (and not crash)."""
        img = Image.new("RGB", (30, 30), (100, 200, 50))
        arr = np.array(img)
        arr[5:25, 5:25] = (100, 200, 60)  # slightly different
        img = Image.fromarray(arr)

        result = chroma_key.chroma_key_remove(img, (100, 200, 50), tolerance=0)

        # Should not crash and should produce RGBA output
        assert result.mode == "RGBA"
        # Slightly different color at center should be opaque (not matching)
        _, _, _, a = result.getpixel((15, 15))
        assert a == 255
