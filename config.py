
import os
import sys
import yaml
import traceback
import logging

from pprint import pformat
from working_dir import WORKING_DIR

thismodule = sys.modules[__name__]

TIME_TO_LIVE = 60 * 30 # 30 minutes
TEST_DOWNLOAD_TIMEOUT = (60 * 3)
LOOP_SLEEP_TIME = 60
RSS_URLS = []

PUBLIC_GATEWAYS_URL = [
    "https://ipfs.github.io/public-gateway-checker/gateways.json"
]

USER_DIR = os.path.join(os.path.expanduser('~'), ".ipfs-feed-translator")
USER_CONFIG_FILE = os.path.join(USER_DIR, "config.yml")

STORAGE_DIR = os.path.join(USER_DIR, "storage")

LOG_LEVEL = "DEBUG"

FALLBACK_LOCAL_GATEWAYS = []
FIRST_CHOICE_GATEWAYS = []
BLACK_LIST = []
MAX_ERRORS = 2
DEFAULT_LEVEL = "INFO"
PUBLIC_GATEWAYS_URL = [
    "https://ipfs.github.io/public-gateway-checker/gateways.json"
]

SAMPLE_CONFIG = """
# Sample config

## List of all the rss url's you'd like to process
RSS_URLS: [
    "http://music.the-erm.com/feed",
]

## Where to store all the enclosures you download
## Default: ~/.ipfs-feed-translator/storage
STORAGE_DIR: "{STORAGE_DIR}"

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

# How long should --loop sleep before it tries again.
LOOP_SLEEP_TIME: 60

""".format(STORAGE_DIR=STORAGE_DIR)

HELP = """
Usage: ipfs-feed-translator.py [OPTION]

  -l, --loop                 Go into an endless loop and repeat check every
                             60 seconds.

  -c <filename.yml>,         Use a specific config file.
  --config <filename.yml>    Default:~/.ipfs-feed-translator/config.yml

  -s, --sample-config        Display a sample config and exit

  -h, --help, -help, -?      Display this and exit.
"""

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}

if "--help" in sys.argv or "-help" in sys.argv or "-h" in sys.argv or\
   "-?" in sys.argv:
    print(HELP)
    sys.exit(1)

if "-s" in sys.argv or "--sample-config" in sys.argv:
    print(SAMPLE_CONFIG)
    sys.exit(1)

if "--config" in sys.argv or "-c" in sys.argv:
    idx = -1
    try:
        idx = sys.argv.index("--config")
    except ValueError:
        try:
            idx = sys.argv.index("-c")
        except ValueError:
            pass

    if idx == -1:
        print(SAMPLE_CONFIG)
        print("Error unable get argument --config from command line.\n")
        sys.exit(1)

    try:
        USER_CONFIG_FILE = os.path.expanduser(sys.argv[idx+1])
    except IndexError:
        print(SAMPLE_CONFIG)
        print("Error unable get argument --config from command line.\n")
        sys.exit(1)

    if not os.path.exists(USER_CONFIG_FILE):
        print(SAMPLE_CONFIG)
        print("Config file does not exist:%s\n" % USER_CONFIG_FILE)
        sys.exit(1)

if os.path.exists(USER_CONFIG_FILE):
    try:
        data = {}
        with open(USER_CONFIG_FILE, 'r') as fp:
            try:
                data = yaml.load_all(fp)
                for doc in data:
                    for name, value in doc.items():
                        if not hasattr(thismodule, name):
                            print("invalid config option")
                            continue
                        default_value = getattr(thismodule, name)
                        if isinstance(value, (list, dict)):
                            if default_value and value != default_value:
                                print("default: %s = %s" % (name, pformat(default_value) ))
                            print("set:     %s = %s" % (name, pformat(value)))
                            setattr(thismodule, name, value)
                        else:
                            if default_value and value != default_value:
                                print("default: %s = %s" % (name, pformat(default_value) ))
                            print("set:     %s = %s" % (name, value))
                            setattr(thismodule, name, value)

            except Exception as e:
                print("Error Decoding:%s" % USER_CONFIG_FILE)
                print("yaml seems to be malformed")
                sys.exit(1)

            if not data:
                print("No data, Error loading config file:%s" % USER_CONFIG_FILE)
                sys.exit(1)

    except Exception as e:
        logging.error(traceback.format_exc())


if not os.path.exists(USER_DIR):
    os.makedirs(USER_DIR)

if "~" in STORAGE_DIR:
    STORAGE_DIR = os.path.expanduser(STORAGE_DIR)

if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

_LOG_LEVEL = LOG_LEVELS.get(LOG_LEVEL)
if _LOG_LEVEL is None:
    logging.error("Invalid LOG_LEVEL:%s using DEFAULT:%s" % (LOG_LEVEL, DEFAULT_LEVEL))
    LOG_LEVEL = LOG_LEVELS.get(DEFAULT_LEVEL)
else:
    LOG_LEVEL = _LOG_LEVEL

if not RSS_URLS:
    print ("No urls to process")
    print ("Edit %s and add the section `rss_urls`." % USER_CONFIG_FILE)
    print (SAMPLE_CONFIG)
