# ipfs-feed-translator

ipfs-feed-translator is a utility to convert an rss feed and it's
enclosures to ipfs urls.

It will:
- download rss enclosures
- separates the enclosures by date into folders.
- `add` them to your local ipfs repo
- pick a random from a pool of various public ipfs gateways
    - confirm that a partial download will work.
- rename all enclosures in the rss to an ipfs url.
- set up an `ipns` entry for the archive folder.

This requires you're running an instance `ipfs daemon` on your box.


### `~/.ipfs-feed-translator/config.yml`
```yaml
# Sample config

## List of all the rss url's you'd like to process
RSS_URLS: [
    "http://music.the-erm.com/feed",
]

## Where to store all the enclosures you download
STORAGE_DIR: "~/.ipfs-feed-translator/storage"

## There may be ipfs gateways that never produce a good result for you.
## Blacklist them to save time.
BLACK_LIST: [
    "https://ipfs.work/ipfs/:hash",
    "https://ipfs.works/ipfs/:hash",
    "https://ipfs.macholibre.org/ipfs/:hash",
    "https://siderus.io/ipfs/:hash",
    "https://www.eternum.io/ipfs/:hash",
    "https://gateway.blocksec.com/ipfs/:hash",
    "https://api.wisdom.sh/ipfs/:hash",
    "https://catalunya.network/ipfs/:hash",
    "https://upload.global/ipfs/:hash",
]

## Fallback to your own ipfs gateway as a last resort.
FALLBACK_LOCAL_GATEWAYS: [
]

## Always try to use this list of gateways first.
FIRST_CHOICE_GATEWAYS: [

]

## Number of errors a host can have before it's considered
## Dead
MAX_ERRORS: 2

# Can be CRITICAL, ERROR, WARNING, INFO, DEBUG
LOG_LEVEL: "INFO"

```
