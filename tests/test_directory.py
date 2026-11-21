import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from scripts.build_directory import build_directory, public_url


class DirectoryTest(unittest.TestCase):
    def test_publishes_every_record_and_limits_opml_to_public_subscriptions(self):
        url = 'https://news.example.org/rss?a=1&b=2'
        topics = [{'topic_id': 'news', 'label': 'News', 'parent_id': None}]
        sources = [{
            'source_id': 'S001', 'name': '[The | Press]', 'primary_topic_id': 'news',
            'coverage_country_codes': '["BE"]', 'access_model': 'public',
            'admission_status': 'candidate', 'rights_status': 'review_required',
        }]
        endpoints = []
        for number, target, status in [(1, url, 'verified'), (2, 'https://news.example.org/unverified', 'advertised'),
                                       (3, 'https://news.example.org/rss?token=hidden', 'needs_review')]:
            endpoints.append({
                'endpoint_id': f'F{number:04}', 'source_id': 'S001', 'url': target,
                'verification_status': status, 'listing_status': 'draft', 'language_tag': 'en',
                'declared_format_id': 'rss', 'detected_format_id': 'rss' if number == 1 else None,
                'auth_method': 'none', 'last_checked_at': '2026-11-20T12:00:00Z' if number == 1 else None,
            })
        tables = dict(topics=topics, sources=sources, endpoints=endpoints, source_topics=[{
            'source_id': 'S001', 'topic_id': 'news', 'is_primary': 'true',
        }], formats=[{'format_id': 'rss', 'label': 'RSS'}])
        with TemporaryDirectory() as directory:
            root = Path(directory)
            build_directory(root, tables, {url}, 'a' * 64)
            with (root / 'directory/feeds.csv').open(newline='') as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(['F0001', 'F0002', 'F0003'], [row['endpoint_id'] for row in rows])
            self.assertEqual(['true', 'false', 'false'], [row['opml_eligible'] for row in rows])
            self.assertEqual('', rows[2]['feed_url'])
            self.assertEqual('BE', rows[0]['coverage_country_codes'])
            page = (root / 'directory/topics/news/advertised-001.md').read_text()
            self.assertIn('F0002', page)
            self.assertIn('&#124;', page)
            self.assertFalse((root / 'directory/topics/news/README.md').read_text().endswith('\n\n'))
            for file in ('all.opml', 'news.opml'):
                opml = ET.parse(root / 'directory/opml' / file)
                self.assertEqual([url], [item.attrib['xmlUrl'] for item in opml.findall('.//outline[@xmlUrl]')])
            manifest = json.loads((root / 'directory/manifest.json').read_text())
            self.assertEqual(3, manifest['endpoint_count'])
            self.assertEqual(1, manifest['withheld_url_count'])

    def test_accepts_public_http_and_rejects_credentials_and_nonpublic_hosts(self):
        self.assertTrue(public_url('http://publisher.org/rss?format=xml'))
        for url in ('https://user:pass@publisher.org/rss', 'https://127.0.0.1/rss',
                    'https://publisher.internal/rss', 'https://publisher.org/rss?%61pi_key=hidden',
                    'https://publisher.org/rss?X-Amz-Signature=hidden', 'javascript:alert(1)',
                    'https://publisher.org:8443/rss'):
            with self.subTest(url=url):
                self.assertFalse(public_url(url))
