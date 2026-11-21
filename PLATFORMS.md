# Platform feeds

Use the [OPML downloads](README.md#browse-by-topic) to find subscriptions the broker offers for import. The [full CSV](directory/feeds.csv) also preserves older and unchecked feed pointers with their recorded status.

## Reddit

Reddit announced that RSS support ended on **November 13, 2026**. The directory keeps legacy Reddit URLs as discovery records. They appear as `advertised` in the catalogue and are excluded from OPML. Reddit says there is no replacement for feed readers following communities they do not moderate. [Reddit Help changelog](https://support.reddithelp.com/hc/en-us/articles/55472297340308-Changelog-November-10-2026)

## Other platforms

| Platform | Feed availability |
| --- | --- |
| Bluesky | Public profiles can expose RSS at `/profile/<handle>/rss`. [Bluesky’s own profile feed](https://bsky.app/profile/bsky.app/rss) |
| Mastodon | Mastodon provides RSS for accounts and hashtags. Use the feed on the instance that hosts the page. [Mastodon syndication documentation](https://docs.joinmastodon.org/user/network/#syndication-feeds) |
| YouTube | YouTube documents channel Atom feeds for video uploads. Our YouTube pointers are under review and currently have no entries in OPML. [YouTube Data API guide](https://developers.google.com/youtube/data/guides/push_notifications) |
| GitHub | Repository releases can be followed via `releases.atom`. Our GitHub pointers are under review. [GitHub CLI releases feed](https://github.com/cli/cli/releases.atom) |
| Substack | Publications can expose RSS at `/feed`. [Example from Substack](https://on.substack.com/feed) |
| Medium | Medium documents RSS for profiles, publications, and topic pages. [Medium Help](https://help.medium.com/hc/en-us/articles/214874118-Using-RSS-feeds-of-profiles-publications-and-topics/) |
