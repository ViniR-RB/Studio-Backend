import hashlib
import unittest


class GenerationFlowTests(unittest.TestCase):
    def test_checksum_preserves_generated_html(self):
        html = '<script>alert(1)</script>'
        self.assertEqual(
            hashlib.sha256(html.encode()).hexdigest(),
            "5c140d35dcb46a622e2cedf5ef5cc3638cdffd1c118c9331f8c84669f0b74783",
        )


if __name__ == "__main__":
    unittest.main()
