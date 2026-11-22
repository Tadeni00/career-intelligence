"""Regression guard: Compose must not publish unauthenticated services to LAN.

Run with: python -m unittest discover -s deployment_checks -v
This test needs no database, Docker daemon, or third-party modules.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"


class LocalPortBindingTests(unittest.TestCase):
    def test_all_published_ports_are_loopback_only(self):
        text = COMPOSE.read_text(encoding="utf-8")
        # Only inspect published port mappings, excluding comments.
        port_lines = [
            line.strip()
            for line in text.splitlines()
            if re.match(r'^\s*-\s*["\']?[^#\n]*:\d+["\']?\s*$', line)
            and not line.lstrip().startswith("#")
        ]
        self.assertEqual(3, len(port_lines), port_lines)
        self.assertTrue(all('127.0.0.1:' in line for line in port_lines), port_lines)
        self.assertIn('127.0.0.1:8011:8011', text)
        self.assertIn('127.0.0.1:4173:4173', text)
        self.assertIn('127.0.0.1:${POSTGRES_PORT:-5433}:5432', text)


if __name__ == "__main__":
    unittest.main()
