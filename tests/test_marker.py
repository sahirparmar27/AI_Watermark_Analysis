import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from app import detect_watermark, embed_watermark


class MarkerTests(unittest.TestCase):
    def test_plain_image_has_no_demo_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'plain.png'
            Image.new('RGB', (320, 240), (90, 140, 200)).save(path)
            self.assertEqual(detect_watermark(path), 'No Prototype Watermark Detected')

    def test_embedded_marker_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source.png'
            marked = Path(temp) / 'marked.png'
            image = Image.new('RGB', (320, 240), (90, 140, 200))
            ImageDraw.Draw(image).text((20, 20), 'Test image', fill='white')
            image.save(source)
            embed_watermark(source, marked)
            self.assertEqual(detect_watermark(marked), 'Prototype Watermark Detected')


if __name__ == '__main__':
    unittest.main(verbosity=2)
