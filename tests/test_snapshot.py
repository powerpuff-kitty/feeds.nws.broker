import csv
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def subscription_urls(path):
    tree = ET.parse(path)
    return [item.attrib['xmlUrl'] for item in tree.findall('.//outline[@xmlUrl]')]


class PublishedSnapshotTest(unittest.TestCase):
    def test_opml_and_manifest_match_the_published_csv(self):
        directory = ROOT / 'directory'
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        with (directory / 'feeds.csv').open(newline='', encoding='utf-8') as file:
            records = list(csv.DictReader(file))
        self.assertEqual(len({row['endpoint_id'] for row in records}), len(records))
        self.assertEqual(manifest['endpoint_count'], len(records))
        eligible = [row for row in records if row['opml_eligible'] == 'true']
        combined = subscription_urls(directory / 'opml/all.opml')
        self.assertEqual(manifest['opml_count'], len(combined))
        self.assertCountEqual({row['feed_url'] for row in eligible}, combined)
        for topic, totals in manifest['topics'].items():
            with self.subTest(topic=topic):
                expected = {row['feed_url'] for row in eligible if row['primary_topic_id'] == topic}
                published = subscription_urls(directory / 'opml' / f'{topic}.opml')
                self.assertEqual(totals['opml_count'], len(published))
                self.assertCountEqual(expected, published)
