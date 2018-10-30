
import subprocess
import os
import re
import json

from logger import log
from config import STORAGE_DIR, FIRST_CHOICE_GATEWAYS, PUBLIC_GATEWAYS_URL, \
                   BLACK_LIST
from downloader import download
from pprint import pformat
from urllib.parse import urlparse

public_gateways_fallback = [
    "https://ipfs.io/ipfs/:hash",
    "https://gateway.ipfs.io/ipfs/:hash",
    "https://ipfs.infura.io/ipfs/:hash",
    "https://rx14.co.uk/ipfs/:hash",
    "https://xmine128.tk/ipfs/:hash",
    "https://upload.global/ipfs/:hash",
    "https://ipfs.jes.xxx/ipfs/:hash",
    "https://catalunya.network/ipfs/:hash",
    "https://siderus.io/ipfs/:hash",
    "https://www.eternum.io/ipfs/:hash",
    "https://hardbin.com/ipfs/:hash",
    "https://ipfs.macholibre.org/ipfs/:hash",
    "https://ipfs.works/ipfs/:hash",
    "https://ipfs.work/ipfs/:hash",
    "https://ipfs.wa.hle.rs/ipfs/:hash",
    "https://api.wisdom.sh/ipfs/:hash",
    "https://gateway.blocksec.com/ipfs/:hash",
    "https://ipfs.renehsz.com/ipfs/:hash",
    "https://cloudflare-ipfs.com/ipfs/:hash",
    "https://ipns.co/:hash",
    "https://ipfs.netw0rk.io/ipfs/:hash",
    "https://gateway.swedneck.xyz/ipfs/:hash",
    "http://10.139.105.114:8080/ipfs/:hash"
]

def get_public_gateways():
    test_file = os.path.join(STORAGE_DIR, "test_gateway_file")
    test_string = "Hello from rss-processor.py"
    with open(test_file, "w") as fp:
        fp.write(test_string)
    pub_key, test_pub_key = publish(test_file)

    gateways = FIRST_CHOICE_GATEWAYS + []
    for url in PUBLIC_GATEWAYS_URL:
        gateways_cache_file = download(url, refresh=True, TTL=60)
        log.debug("gateways_cache_file:%s" % gateways_cache_file)
        with open(gateways_cache_file,'r') as fp:
            public_gateways = []
            contents = fp.read()
            log.debug("contents:%s" % contents)
            try:
                public_gateways = json.loads(contents)
                log.debug("public_gateways:%s" % pformat(public_gateways))
            except Exception as e:
                log.error("Error reading %s" % gateways_cache_file)
                log.error("error.__doc__ %s" % e.__doc__)
                if hasattr(e, 'message'):
                    log.error("error.message %s" % e.message)
                continue
            for _url in public_gateways:
                if _url in BLACK_LIST:
                    log.debug("BLACK_LISTED:%s" % _url)
                    continue
                blacklisted = False
                for host in BLACK_LIST:
                    url_info = urlparse(_url)
                    if url_info.netloc == host:
                        blacklisted = True
                        break;
                if blacklisted:
                    log.debug("BLACK_LISTED:%s" % _url)
                    continue
                if _url not in gateways:
                    try:
                        cache_file = download(_url.replace(":hash", pub_key))
                        with open(cache_file,'r') as fp:
                            file_contents = fp.read()
                            if file_contents == test_string:
                                log.debug("IS GOOD ADDING:%s" % _url)
                                gateways.append(_url)
                            else:
                                log.error("IS BAD GATEWAY:%s" % _url)

                    except Exception as e:
                        log.error("IS BAD GATEWAY:%s" % _url)
                        log.error("error.__doc__ %s" % e.__doc__)
                        if hasattr(e, 'message'):
                            log.error("error.message %s" % e.message)
                        continue

    if not gateways:
        gateways = public_gateways_fallback
        log.error("gateways was empty using fallback")
    log.info(pformat(gateways))
    return gateways

def publish(file):
    if not file:
        return '', ''
    # ipfs add /home/erm/disk2/ipfs-storage/http---xml.nfowars.net-Alex.rss.cache.rss
    published_file = "%s.published" % file
    test_file = "%s.test.published" % file
    if os.path.exists(published_file) and os.path.exists(test_file):
        pub_key = ""
        test_pub_key = ""
        with open(published_file,'r') as fp:
            pub_key = "%s" % fp.read()

        with open(test_file,'r') as fp:
            test_pub_key = "%s" % fp.read()
    else:
        pub_key = add_file(file, published_file)
        test_pub_key = add_file(published_file, test_file)

    log.debug("pub_key:%s test_pub_key:%s" % (pub_key, test_pub_key))
    return pub_key, test_pub_key

def publish_folder(folder):
    if not folder or not os.path.exists(folder):
        return ''

    cmd = [
        'ipfs',
        'add',
        '-r',
        folder
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    while True:
      line = p.stdout.readline()
      if line != b'':
        print("OUTPUT:%s" % line.rstrip())
      else:
        break

def add_file(file, published_file, recursive=False):
    if not file or not os.path.exists(file):
        return ""
    cmd = [
        'ipfs',
        'add',
        file
    ]
    pub_key = ""
    if os.path.isdir(file):
        log.debug("IS DIR:%s" % file)
        cmd = [
            'ipfs',
            'add',
            '-r',
            file
        ]
        p = subprocess.Popen(cmd)
        p.wait()
        sys.exit()
        return ""
    result = subprocess.check_output(cmd)
    result = result.decode("utf-8")
    log.debug("result:%s" % result)

    # added QmVn4y8PnmTLw6qU8wWdSMG5v8LPk6eSY4Eh1oCMf3ZmRs
    m = re.match("added (Qm[0-9A-Za-z]{44})", result)

    if m:
        log.debug("m.groups():%s" % pformat(m.groups()))
        pub_key = m.group(1)
        log.debug("published_file:%s" % published_file)

        if published_file:
            with open(published_file, "w") as fp:
                fp.write(pub_key)

    return pub_key