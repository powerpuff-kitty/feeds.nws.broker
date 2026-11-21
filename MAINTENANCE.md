# About the directory

The directory is generated from the [public nws.broker catalogue API](https://nws.broker/api/catalogue). It includes each endpoint ID from the production export, including draft, unverified and unavailable records. Each GitHub category page uses the source’s primary topic. The CSV retains the secondary assignments. Endpoint links on category pages open the corresponding live catalogue record.

The source catalogue includes syndication feeds, alert streams, and structured-data endpoints. `verification_status` records the broker’s last observation. `listing_status`, `admission_status`, and `rights_status` record distinct catalogue decisions. Check the publisher’s terms before reusing its content. For corrections or removal requests, use the [repository’s issue tracker](https://github.com/powerpuff-kitty/feeds.nws.broker/issues).

## Data files

| File | Contents |
| --- | --- |
| [`directory/feeds.csv`](directory/feeds.csv) | One row per endpoint. Source ID and name, feed URL, primary and secondary topics, language, country coverage, declared and detected formats, verification status and time, listing status, access model, authentication, admission, rights status, and OPML eligibility. |
| [`directory/manifest.json`](directory/manifest.json) | Production catalogue import hash, endpoint and subscription totals, status totals, and per-topic counts. |
| [`directory/opml/`](directory/opml/) | The combined subscription list and one OPML file per primary topic. The source is the broker’s [public subscription export](https://nws.broker/api/subscriptions/opml?prefer=original). |

CSV lists use `|` between values. Country codes describe recorded source coverage. Dates are UTC. Blank cells indicate missing metadata or a feed URL omitted by publication checks. Spreadsheet formula prefixes in text are escaped with a leading apostrophe. The manifest counts how many endpoint records have an omitted URL.

OPML uses original publisher links. It deduplicates exact URLs within each file. Where the same URL belongs to more than one primary topic, it may appear in each of those topic files and appears only once in the combined file.

## Refresh a snapshot

The README is generated with the catalogue. Edit `scripts/build_directory.py` to change its layout or links. The checked-in brand mark mirrors the [nws.broker favicon](https://nws.broker/favicon.svg). GitHub Actions runs the offline tests on pull requests and main pushes, including checks that the published CSV, OPML, and manifest agree.

Use Python 3.9 or later and `curl`. The generator reads the production import hash before and after download, validates table counts and identities, then writes to a new directory. It makes requests to the broker API. It does not request publisher feed bodies.

```sh
python3 -m unittest discover -s tests -v
staging=$(mktemp -d)
python3 scripts/build_directory.py --output "$staging/snapshot"
diff -qr directory "$staging/snapshot/directory"
```

Review the manifest and the diff, then copy the refreshed files into the checkout.

```sh
cp "$staging/snapshot/README.md" README.md
rsync -a --delete "$staging/snapshot/directory/" directory/
git diff --check
```
