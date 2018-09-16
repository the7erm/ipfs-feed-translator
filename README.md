# ipfs-feed-translator

ipfs-feed-translator is a utility to convert an rss feed and it's
enclosures to ipfs urls.

It will:
- Respect an rss ttl.
  - minimum 30 minutes before it tries a rss feed again.
- download rss enclosures
- separates the enclosures by date into folders.
- `add` them to your local ipfs repo
- pick a random from a pool of various public ipfs gateways
    - confirm that a partial download will work.
- rename all enclosures in the rss to an ipfs url.
- set up an `ipns` entry for the archive folder.


This requires you're running an instance `ipfs daemon` on your box.


## Quickstart

### Install `requirements.txt`
Alternatively you can set up a virtualenv - covered in the advanced section -
and from there use pip to install requirements.
```
# This should install all the requirements globally.
pip install -r requirements.txt
```

### Create config file `~/.ipfs-feed-translator/config.yml`

Add all the rss urls you'd like to add to ipfs.

```yaml
# Sample config

## List of all the rss url's you'd like to process
RSS_URLS: [
    "http://music.the-erm.com/feed",
]

## Where to store all the enclosures you download
STORAGE_DIR: "~/.ipfs-feed-translator/storage"

## There may be ipfs gateways that never produce a good result for you.
## Blacklist them to save time/cpu.
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

### Execute the program
```
./ipfs-feed-translator.py
```

If you want to run forever:
```
./ipfs-feed-translator.py --loop
```

If you want to use a different config file:
```
./ipfs-feed-translator.py --loop --config ~/path-to-config.yml
```


### Advanced

#### Supervisor
Supervisor is a program that will continually run a program and if it
crashes restart it.  This section will go over a basic configuration.

##### Set up your virtual env
```
virtualenv -p python3 ipfs-feed-translator-env
# Activate the venv
. ./ipfs-feed-translator-env/bin/activate
pip install -r requirements.txt
```

#### supervisor `ipfs-feed-translator.conf`
```
[program:ipfs-feed-translator]
user=<username>
command = /home/<user>/ipfs-feed-translator-env/bin/python /home/<user>/ipfs-feed-translator-env/ipfs-feed-translator.py --loop
directory = /home/<user>/
user = <user>
group = <group>
environment=HOME="/home/<user>/",USER="<user>",GROUP="<group>"
priority = 1
```

