#!/usr/bin/env python3

import config
import sys
import time

from rss_feed import RssFeed, public_gateways
from logger import log

log.debug("import complete")

while True:
    ipns_urls = []
    cache_file_downloaded = False
    for url in config.RSS_URLS:
        feed = RssFeed(url)
        feed.process()
        if feed.ipns_hash and feed.cache_file_downloaded:
            ipns_urls.append(("http://localhost:8080/ipns/%s" % feed.ipns_hash,
                              url))
            for hash_url in public_gateways:
                hash_url = hash_url.replace("/ipfs/:hash", "/ipns/%s" % feed.ipns_hash)
                ipns_urls.append((hash_url, url))


    for ipns_url, rss_url in ipns_urls:
        print("*"*80)
        print("rss_url:%s" % rss_url)
        print("published to:%s" % ipns_url)
    if "--loop" not in sys.argv and "-l" not in sys.argv:
        break
    log.debug("sleeping for a minute")
    time.sleep(60)
