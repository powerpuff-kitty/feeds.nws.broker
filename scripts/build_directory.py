"""Build a GitHub directory from the public nws.broker catalogue and OPML export."""

import argparse
from collections import Counter, defaultdict
import csv
import html
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qsl, quote, urlsplit
import xml.etree.ElementTree as ET


API = 'https://nws.broker/api'
STATUSES = {
    'verified': ('Verified', 'The broker successfully parsed the feed at the recorded check.'),
    'advertised': ('Advertised', 'A source or directory advertised the endpoint. Verification is pending.'),
    'needs_review': ('Needs review', 'The record needs follow-up, for example on access, format, or parsing.'),
    'unavailable': ('Unavailable', 'The endpoint was unavailable at the recorded check.'),
}
TABLES = {
    'topics': 'topic_id', 'formats': 'format_id', 'sources': 'source_id',
    'source_topics': ('source_id', 'topic_id'), 'endpoints': 'endpoint_id',
}
FIELDS = (
    'endpoint_id', 'source_id', 'source_name', 'feed_url', 'primary_topic_id', 'topic_ids',
    'language_tag', 'coverage_country_codes', 'declared_format_id', 'detected_format_id',
    'verification_status', 'last_checked_at', 'listing_status', 'access_model', 'auth_method',
    'admission_status', 'rights_status', 'opml_eligible',
)
PAGE_SIZE = 150
SECRET_QUERY_KEY = re.compile(r'token|secret|password|passwd|signature|apikey|accesskey|clientkey|credential|^sig$|^key$|^auth$|^x-amz|^x-goog')


def download(path):
    return subprocess.run(
        ['curl', '--fail', '--silent', '--show-error', '--max-time', '60', '--retry', '2', f'{API}/{path}'],
        check=True, capture_output=True,
    ).stdout


def snapshot():
    before = json.loads(download('catalogue'))
    tables = {name: json.loads(download(f'export/{name}')) for name in TABLES}
    opml = ET.fromstring(download('subscriptions/opml?prefer=original'))
    after = json.loads(download('catalogue'))
    version = before['import']['version']
    if after['import']['version'] != version or after['counts'] != before['counts']:
        raise ValueError('Production catalogue changed during download. Run the generator again.')
    for name, key in TABLES.items():
        rows = tables[name]
        fields = (key,) if isinstance(key, str) else key
        identities = {tuple(row[field] for field in fields) for row in rows}
        if len(rows) != before['counts'][name] or len(identities) != len(rows):
            raise ValueError(f'The {name} export has missing or duplicate records.')
    return tables, {item.attrib['xmlUrl'] for item in opml.iter('outline') if item.get('xmlUrl')}, version


def public_url(raw):
    if not raw or '\\' in raw or any(char.isspace() or ord(char) < 32 for char in raw):
        return False
    try:
        url = urlsplit(raw)
        host = url.hostname or ''
        if url.scheme not in {'https', 'http'} or url.username is not None or url.password is not None:
            return False
        if url.port not in (None, 443 if url.scheme == 'https' else 80):
            return False
        if not re.fullmatch(r'(?:[a-z0-9-]+\.)+[a-z][a-z0-9-]*', host, flags=re.I):
            return False
        if host.rsplit('.', 1)[-1] in {'localhost', 'local', 'internal', 'test', 'invalid', 'example', 'onion', 'lan'}:
            return False
        return all(not SECRET_QUERY_KEY.search(re.sub(r'[^a-z0-9]', '', key.lower()))
                   for key, _ in parse_qsl(url.query, keep_blank_values=True))
    except (UnicodeError, ValueError):
        return False


def markdown(value):
    escaped = html.escape(' '.join(str(value or '').split())).replace('|', '&#124;')
    return re.sub(r'([\\\[\]`*_~])', r'\\\1', escaped)


def spreadsheet(value):
    value = str(value or '')
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def records(tables, subscriptions):
    sources = {row['source_id']: row for row in tables['sources']}
    topic_ids = {row['topic_id'] for row in tables['topics']}
    assignments = defaultdict(set)
    for row in tables['source_topics']:
        if row['topic_id'] not in topic_ids or row['source_id'] not in sources:
            raise ValueError('Invalid source-topic assignment in export.')
        assignments[row['source_id']].add(row['topic_id'])
    for endpoint in tables['endpoints']:
        source_id = endpoint['source_id']
        source = sources[source_id]
        topic = source['primary_topic_id']
        if topic not in topic_ids or endpoint['verification_status'] not in STATUSES:
            raise ValueError(f"Unrecognized topic or status for {endpoint['endpoint_id']}.")
        url = endpoint['url'] if public_url(endpoint['url']) else ''
        eligible = (url in subscriptions and endpoint['verification_status'] == 'verified'
                    and endpoint['auth_method'] == 'none' and url.startswith('https://')
                    and source['admission_status'] not in {'hold', 'retired'}
                    and source['rights_status'] not in {'prohibited', 'restricted'})
        yield {
            **{field: endpoint.get(field) for field in FIELDS if field in endpoint},
            'source_name': source['name'], 'feed_url': url, 'primary_topic_id': topic,
            'topic_ids': '|'.join(sorted(assignments[source_id] | {topic})),
            'coverage_country_codes': '|'.join(sorted(json.loads(source['coverage_country_codes'] or '[]'))),
            **{field: source[field] for field in ('access_model', 'admission_status', 'rights_status')},
            'opml_eligible': 'true' if eligible else 'false',
        }


def append_subscriptions(parent, rows, seen):
    for row in rows:
        url = row['feed_url']
        if row['opml_eligible'] == 'true' and url not in seen:
            seen.add(url)
            name = row['source_name']
            ET.SubElement(parent, 'outline', type='rss', text=name, title=name, xmlUrl=url)


def write_opml(path, title, groups):
    root = ET.Element('opml', version='2.0')
    ET.SubElement(ET.SubElement(root, 'head'), 'title').text = title
    body = ET.SubElement(root, 'body')
    seen = set()
    for label, rows in groups:
        parent = body if label is None else ET.SubElement(body, 'outline', text=label, title=label)
        append_subscriptions(parent, rows, seen)
        if parent is not body and len(parent) == 0:
            body.remove(parent)
    ET.indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding='utf-8', xml_declaration=True)
    ET.parse(path)
    return len(seen)


def write_text(path, lines):
    path.write_text('\n'.join(lines).rstrip('\n') + '\n', encoding='utf-8')


def topic_pages(directory, label, rows, formats, topic):
    directory.mkdir(parents=True)
    index = [f'# {markdown(label)}', '', '[All categories](../../../README.md) · '
             f'[Download OPML](../../opml/{topic}.opml)', '', f'{len(rows):,} endpoint records.', '']
    counts = Counter(row['verification_status'] for row in rows)
    for status, (status_name, description) in STATUSES.items():
        group = [row for row in rows if row['verification_status'] == status]
        if not group:
            continue
        index.extend([f'## {status_name} ({counts[status]:,})', '', description, ''])
        for start in range(0, len(group), PAGE_SIZE):
            page = group[start:start + PAGE_SIZE]
            name = f'{status}-{start // PAGE_SIZE + 1:03}.md'
            index.append(f'- [{start + 1:,}–{start + len(page):,}]({name}) · '
                         f'{markdown(page[0]["source_name"])} to {markdown(page[-1]["source_name"])}')
            lines = [f'# {markdown(label)} · {status_name}', '', '[Back to category](README.md)', '',
                     '| Source | Endpoint | Format | Language | Last checked (UTC) | Subscribe |',
                     '| --- | --- | --- | --- | --- | --- |']
            for row in page:
                endpoint = row['endpoint_id']
                key = row['detected_format_id'] or row['declared_format_id']
                feed_link = '—'
                if row['opml_eligible'] == 'true':
                    url = quote(row['feed_url'], safe=":/?#[]@!$&'()*+,;=%~")
                    feed_link = f'[Feed](<{url}>)'
                values = [markdown(row['source_name']), f'[{endpoint}]({API}/endpoints/{endpoint})',
                          markdown(formats.get(key, key)), markdown(row['language_tag'] or 'und'),
                          markdown((row['last_checked_at'] or '—')[:10]), feed_link]
                lines.append('| ' + ' | '.join(values) + ' |')
            write_text(directory / name, lines)
        index.append('')
    write_text(directory / 'README.md', index)
    return counts


def build_directory(root, tables, subscriptions, version):
    data = root / 'directory'
    (data / 'opml').mkdir(parents=True)
    rows = sorted(records(tables, subscriptions), key=lambda item: (item['source_name'].casefold(), item['endpoint_id']))
    by_topic = defaultdict(list)
    for row in rows:
        by_topic[row['primary_topic_id']].append(row)
    topics = sorted(tables['topics'], key=lambda row: row['label'].casefold())
    labels = {row['topic_id']: row['label'] for row in topics}
    formats = {row['format_id']: row['label'] for row in tables['formats']}
    with (data / 'feeds.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, FIELDS, lineterminator='\n')
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item['endpoint_id']):
            writer.writerow({key: spreadsheet(row.get(key)) for key in FIELDS})
    total_opml = write_opml(data / 'opml/all.opml', 'nws.broker subscriptions',
                            [(row['label'], by_topic[row['topic_id']]) for row in topics])
    index = ['# nws.broker feed directory', '',
             f'Browse **{len(rows):,} endpoint records** from {len({row["source_id"] for row in rows}):,} sources '
             f'across {len(topics)} topics.', '',
             f'[Full catalogue CSV](directory/feeds.csv) · [Import all {total_opml:,} subscriptions](directory/opml/all.opml) · '
             '[Snapshot manifest](directory/manifest.json) · [Live catalogue](https://nws.broker/catalogue/)', '',
             '## Browse by topic', '',
             '| Category | Parent | Verified | Advertised | Needs review | Unavailable | OPML |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    summaries = {}
    for topic in topics:
        key, label = topic['topic_id'], topic['label']
        if not re.fullmatch(r'[a-z0-9_-]+(?:\.[a-z0-9_-]+)*', key):
            raise ValueError('Invalid topic ID in export.')
        entries = by_topic[key]
        counts = topic_pages(data / 'topics' / key, label, entries, formats, key)
        count_opml = write_opml(data / 'opml' / f'{key}.opml', f'nws.broker · {label}', [(None, entries)])
        values = [f'[{markdown(label)}](directory/topics/{key}/README.md)', markdown(labels.get(topic['parent_id'])),
                  *(f'{counts[status]:,}' for status in STATUSES), f'[{count_opml:,}](directory/opml/{key}.opml)']
        index.append('| ' + ' | '.join(values) + ' |')
        summaries[key] = {'endpoint_count': len(entries), 'opml_count': count_opml,
                          'status_counts': {status: counts[status] for status in STATUSES}}
    index.extend(['', '## Feed status', '', *(f'- **{label}**. {description}' for label, description in STATUSES.values()),
                  '', 'These are catalogue observations at the recorded check date. The CSV also records listing, access, '
                  'admission, and rights status. Each record appears under its primary topic. The CSV includes secondary topics.',
                  '', 'The OPML files contain original publisher URLs from the broker’s public subscription export. '
                  'The combined file groups them by topic and includes each exact URL once. '
                  'Use GitHub’s **Raw** button to save a file and import it into your reader. JSON Feed support depends on the reader.',
                  '', 'See [data fields, source, and refresh instructions](MAINTENANCE.md).'])
    write_text(root / 'README.md', index)
    manifest = {'source': API, 'catalogue_import': version, 'endpoint_count': len(rows),
                'opml_count': total_opml, 'withheld_url_count': sum(not row['feed_url'] for row in rows),
                'status_counts': dict(Counter(row['verification_status'] for row in rows)), 'topics': summaries}
    write_text(data / 'manifest.json', [json.dumps(manifest, indent=2, sort_keys=True)])
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory for the generated snapshot')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('--output must be a new directory')
    tables, subscriptions, version = snapshot()
    manifest = build_directory(args.output, tables, subscriptions, version)
    print(f"Built {manifest['endpoint_count']:,} endpoint records and {manifest['opml_count']:,} subscriptions.")


if __name__ == '__main__':
    main()
