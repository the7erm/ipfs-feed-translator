
import feedparser
import os
import os
import re
import requests
import subprocess
import sys
import time

from multiprocessing import Queue, Process
from multiprocessing.queues import Empty
from requests import head, get
from copy import deepcopy
from pprint import pformat
from logger import log
from downloader import download, safe_filename, construct_cache_file_name, \
                       is_cache_stale
from publisher import publish, get_public_gateways, publish_folder
from random import shuffle
from config import MAX_ERRORS, TEST_DOWNLOAD_TIMEOUT, FIRST_CHOICE_GATEWAYS, \
                   FALLBACK_LOCAL_GATEWAYS, STORAGE_DIR, TIME_TO_LIVE, \
                   LOG_LEVEL
from constants import HTTP_OK, HTTP_PARTIAL

public_gateways = get_public_gateways()
log.debug("public_gateways:%s" % pformat(public_gateways))

error_tracker = {}
reliablity_tracker = {}

def _req(url, queue, expected_hash):
    a = get(url)
    content = a.content.decode("utf-8")
    log.debug("a.content:%s" % content)
    if a.status_code == 200 and content == expected_hash:
        log.debug("Matched expected_hash:%s" % expected_hash)
        queue.put(a)
    return


def get_first_hash(urls, expected_hash):
    jobs = []
    q = Queue()
    for url in urls:
        p = Process(target=_req, args=(url, q, expected_hash))
        jobs.append(p)
    for p in jobs:
        p.start()
    try:
        ret = q.get(timeout=20)  # blocking get - wait at most 20 seconds for a return
    except Empty:  # thrown if the timeout is exceeded
        ret = None
    for p in jobs:
        p.terminate()
    return ret

class RssFeed:
    rss_url = None
    cache_file = None
    final_file = None
    rss_pub_key = None
    rss_test_pub_key = None

    def __init__(self, rss_url=None):
        self.cache_file_downloaded = False
        self.rss_url = rss_url
        self.key = safe_filename(self.rss_url)
        self.rss_folder = os.path.join(STORAGE_DIR, self.key)
        self.ipns_file = os.path.join(STORAGE_DIR, "%s.pns" % self.key)
        self.replacements = []
        self.cache_file = construct_cache_file_name(
            self.rss_url, subdir="%s.orig" % self.key)

        self.text = ''
        self.load_text()

        self.feed = None
        self.parent_hash = ""
        self.ipns_hash = ""

        if os.path.exists(self.ipns_file):
            self.ipns_hash = open(self.ipns_file,'r').read()
        # self.cache_file = download(self.rss_url, subdir="%s.orig" % self.key)


        if not os.path.exists(self.rss_folder):
            os.makedirs(self.rss_folder)
        dirname = os.path.dirname(self.cache_file)
        basename = os.path.basename(self.cache_file)
        final_filename = "%s.final.xml" %  basename
        self.final_file = os.path.join(self.rss_folder, final_filename)
        self.pub_key, self.test_pub_key = publish(self.cache_file)
        log.debug("Initialized rss_url:%s" % rss_url)

    def process(self):
        self.process_feed()
        if self.cache_file_downloaded:
            self.process_image()
            self.process_enclosures()
            self.process_replacements()
            self.write_final_file()
            self.publish_ipns()

    def process_feed(self):

        self.cache_file_downloaded = False
        if not os.path.exists(self.cache_file):
            self.cache_file = download(self.rss_url, subdir="%s.orig" % self.key)
            self.cache_file_downloaded = True
            self.load_text()

        log.info("parsing:%s" % self.cache_file)
        self.feed = feedparser.parse(self.cache_file)
        log.debug("feed:%s" % pformat(self.feed))
        if self.cache_file_downloaded:
            log.debug("cache file already downloaded")
            return
        ttl = TIME_TO_LIVE
        log.debug("checking ttl:%s" % self.rss_url)
        if 'ttl' in self.feed.feed:
            log.debug("feed.ttl:%s" % self.feed.feed['ttl'])
            try:
                ttl_min = int(self.feed.feed['ttl'])
                ttl = ttl_min * 60
            except:
                pass
        if is_cache_stale(self.cache_file, TTL=ttl, refresh=True):
            log.debug("cache is stale:%s" % self.rss_url)
            self.cache_file = download(self.rss_url,
                                       subdir="%s.orig" % self.key,
                                       TTL=ttl)
            self.cache_file_downloaded = True
            self.load_text()
        else:
            log.debug("cache is not stale:%s" % self.rss_url)
            self.load_text()


    def load_text(self):
        if os.path.exists(self.cache_file):
            self.text = open(self.cache_file, 'r').read()
            if not self.text:
                log.error("cache_file `%s` is empty" % self.cache_file)

        else:
            log.error("cache_file `%s` is missing" % self.cache_file)

    def process_image(self):
        try:
            log.debug("feed.feed.image:%s" % self.feed.feed.image)
            self.image = self.feed.feed.image
            subdir = safe_filename(self.rss_url)
            self.image_cache_file = download(self.image.href, TTL=(60 * 60 * 24),
                                             subdir=subdir)
            if not self.image_cache_file:
                return
            dirname = os.path.dirname(self.image_cache_file)
            basename = os.path.basename(self.image_cache_file)
            folder_basename = os.path.basename(dirname)
            pub_key, test_pub_key = publish(self.image_cache_file)
            hashes = self.full_publish_folder(dirname)
            parent_hash = ""
            for name, h in hashes:
                if name == folder_basename:
                    log.debug("--------------")
                log.debug("hash:%s" % h)
                log.debug("name:%s" % name)
                if name == folder_basename:
                    parent_hash = deepcopy(h)
                    log.debug("--------------")
            enclosure_replacement = os.path.join(parent_hash,
                                                 basename)
            log.debug("parent_hash:%s" % parent_hash)
            log.debug("basename:%s" % basename)
            log.debug("image enclosure_replacement:%s" % enclosure_replacement)
            self.replacements.append((enclosure.href, enclosure_replacement,
                                      pub_key, test_pub_key))
        except:
            pass

    def process_enclosures(self):
        for entry in self.feed['entries']:
            log.debug("entry:%s" % pformat(entry))
            subdir = safe_filename(self.rss_url)
            published_parsed = entry.get("published_parsed")
            if published_parsed:
                # 'published_parsed': time.struct_time(tm_year=2009, tm_mon=7, tm_mday=30, tm_hour=10, tm_min=52, tm_sec=31, tm_wday=3, tm_yday=211, tm_isdst=0),
                pub_subdir = time.strftime("%Y/%m-%b/%Y-%m-%d %a", published_parsed)
                subdir = os.path.join(subdir, pub_subdir)

            for enclosure in entry['enclosures']:
                log.debug("enclosure:%s" % enclosure)
                enclosure_cache_file = download(enclosure.href, False,
                                                subdir=subdir)
                if not enclosure_cache_file:
                    continue
                log.debug("enclosure_cache_file:%s" % enclosure_cache_file)
                pub_key, test_pub_key = publish(enclosure_cache_file)
                if not pub_key or not test_pub_key:
                    continue
                dirname = os.path.dirname(enclosure_cache_file)
                basename = os.path.basename(enclosure_cache_file)
                folder_basename = os.path.basename(dirname)
                hashes = self.full_publish_folder(dirname)
                parent_hash = ""
                for name, h in hashes:
                    if name == folder_basename:
                        log.debug("--------------")
                    log.debug("hash:%s" % h)
                    log.debug("name:%s" % name)
                    if name == folder_basename:
                        parent_hash = deepcopy(h)
                        log.debug("--------------")
                enclosure_replacement = os.path.join(parent_hash,
                                                     basename)
                log.debug("parent_hash:%s" % parent_hash)
                log.debug("basename:%s" % basename)
                log.debug("enclosure_replacement:%s" % enclosure_replacement)

                self.replacements.append((enclosure.href, enclosure_replacement,
                                          pub_key, test_pub_key))

    def max_errors_reached(self):
        max_errors_reached_for_all = True
        if not error_tracker:
            return False
        for url, count in error_tracker.items():
            if count < MAX_ERRORS:
                max_errors_reached_for_all = False
                break
        return max_errors_reached_for_all

    def process_replacements(self):
        for href, enclosure_replacement, pub_key, test_pub_key in self.replacements:
            log.debug("href:`%s` enclosure_replacement:`%s` pub_key:`%s` test_pub_key:`%s`" % (
                href, enclosure_replacement, pub_key, test_pub_key
            ))
            errors = []
            if not href:
                errors.append("href null or empty")
                continue

            if not enclosure_replacement:
                errors.append("enclosure_replacement null or empty")

            if not pub_key:
                errors.append("pub_key null or empty")

            if not test_pub_key:
                errors.append("test_pub_key null or empty")

            if errors:
                log.error("Skipping:%s for: href:%s enclosure_replacement:%s "
                          "pub_key:%s test_pub_key:%s" % (
                                ",".join(errors),
                                href,
                                enclosure_replacement,
                                pub_key,
                                test_pub_key))
                continue

            if self.max_errors_reached():
                log.critical("Max errors as been reached for all urls %s" %
                             pformat(error_tracker))
                return

            while not self.max_errors_reached():
                find = href
                good_url = self.get_first_test_result(test_pub_key, pub_key)
                if not good_url:
                    log.error("Unable to get a good url for test_pub_key:%s "
                              "pub_key:%s" % (test_pub_key, pub_key))
                    break
                log.debug("******* MADE IT good_url:%s" % good_url)

                hash_url = good_url.replace(test_pub_key, ":hash")
                replace = good_url.replace(test_pub_key, enclosure_replacement)
                log.debug("replace:%s" % replace)
                if hash_url not in error_tracker:
                    error_tracker[hash_url] = 0

                if hash_url not in reliablity_tracker:
                    reliablity_tracker[hash_url] = 0

                if self.test_download(replace):
                    reliablity_tracker[hash_url] += 1
                    self.text = self.text.replace(find, replace)
                    break
                error_tracker[hash_url] += 1

    def test_download(self, url):
        result = False
        log.info("TESTING: %s" % url)
        if '/home/' in url:
            log.error("/home/ is in url")
            sys.exit()
        TEST_RANGE = 256000
        try:
            headers = {
                "Range": "bytes=0-%s" % TEST_RANGE
            }
            response = requests.get(url, stream=True,
                                    timeout=TEST_DOWNLOAD_TIMEOUT,
                                    headers=headers)
        except requests.exceptions.ReadTimeout as e:
            log.debug("BAD URL:%s" % url)
            log.error("Error reading %s" % url)
            log.error("error.__doc__ %s" % e.__doc__)
            if hasattr(e, 'message'):
                log.error("error.message %s" % e.message)
            log.info("TEST RESULT: %s" % result)
            return result
        except requests.exceptions.ChunkedEncodingError as e:
            log.debug("BAD URL:%s" % url)
            log.error("Error reading %s" % url)
            log.error("error.__doc__ %s" % e.__doc__)
            if hasattr(e, 'message'):
                log.error("error.message %s" % e.message)
            log.info("TEST RESULT: %s" % result)
            return result


        if response.status_code not in (HTTP_OK, HTTP_PARTIAL):
            log.debug("BAD URL:%s" % url)
            log.info("TEST RESULT: %s" % result)
            return result

        total_length = response.headers.get('content-length')

        done_float = 0
        if total_length is None: # no content length header
            # fp.write(response.content)
            log.info("total_length was None")
            content = ""
            try:
                dl = 0
                for data in response.iter_content(chunk_size=1024 * 1):
                    dl += len(data)
                    done_float = float(100 * dl / TEST_RANGE)
                    if LOG_LEVEL <= log.INFO:
                        sys.stdout.write("\rTEST %s %0.2f%% dl:%s" % (
                            url,
                            done_float,
                            dl
                        ) )
                        sys.stdout.flush()
                    if dl >= TEST_RANGE:
                        if LOG_LEVEL <= log.INFO:
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                        result = True
                        response.close()
                        return result
                # content = response.content
                log.info("len(content):%s" % len(content))
            except requests.exceptions.ConnectionError as e:
                log.error("BAD URL:%s" % url)
                log.error("Error reading %s" % url)
                log.error("error.__doc__ %s" % e.__doc__)
                if hasattr(e, 'message'):
                    log.error("error.message %s" % e.message)
                response.close()
                return result
            except requests.exceptions.ChunkedEncodingError as e:
                log.error("BAD URL:%s" % url)
                log.error("Error reading %s" % url)
                log.error("error.__doc__ %s" % e.__doc__)
                if hasattr(e, 'message'):
                    log.error("error.message %s" % e.message)
                response.close()
                log.info("TEST RESULT: %s" % result)
                return result
            except requests.exceptions.ReadTimeout as e:
                log.debug("BAD URL:%s" % url)
                log.error("Error reading %s" % url)
                log.error("error.__doc__ %s" % e.__doc__)
                if hasattr(e, 'message'):
                    log.error("error.message %s" % e.message)
                log.info("TEST RESULT: %s" % result)
                return result

            if not content:
                log.error("No content BAD URL:%s" % url)
                log.info("TEST RESULT: %s" % result)
                return result
            else:
                result = True
        else:
            dl = 0
            total_length = int(total_length)
            log.debug("total_length:%s" % total_length)
            try:
                for data in response.iter_content(chunk_size=1024 * 1):
                    dl += len(data)
                    done_float = float(100 * dl / TEST_RANGE)
                    ### CRITICAL    50
                    ### ERROR   40
                    ### WARNING 30
                    ### INFO    20
                    ### DEBUG   10
                    ### NOTSET  0
                    if LOG_LEVEL <= log.INFO:
                        sys.stdout.write("\rTEST %s %0.2f%% dl:%s" % (
                            url,
                            done_float,
                            dl
                        ) )
                        sys.stdout.flush()
                    if response.status_code not in (HTTP_OK, HTTP_PARTIAL):
                        log.error("BAD URL:%s STATUS:%s" % (url, response.status_code))
                        response.close()
                        log.info("TEST RESULT: %s" % result)
                        return result
                    if dl >= TEST_RANGE:
                        if LOG_LEVEL <= log.INFO:
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                        result = True
                        if dl > total_length:
                            result = False
                            log.error("BAD URL:%s %% too much" % url)
                            response.close()
                            break
                        else:
                            if LOG_LEVEL <= log.INFO:
                                sys.stdout.write("\n")
                                sys.stdout.flush()
                            log.debug("GOOD URL:%s" % url)
                            response.close()
                        break

            except requests.exceptions.ConnectionError as e:
                log.error("BAD URL:%s" % url)
                log.error("Error reading %s" % url)
                log.error("error.__doc__ %s" % e.__doc__)
                if hasattr(e, 'message'):
                    log.error("error.message %s" % e.message)
                response.close()
                log.info("TEST RESULT: %s" % result)
                return result
            except requests.exceptions.ChunkedEncodingError as e:
                log.error("BAD URL:%s" % url)
                log.error("Error reading %s" % url)
                log.error("error.__doc__ %s" % e.__doc__)
                if hasattr(e, 'message'):
                    log.error("error.message %s" % e.message)
                response.close()
                log.info("TEST RESULT: %s" % result)
                return result

        if LOG_LEVEL <= log.INFO:
            sys.stdout.write("\n")
            sys.stdout.flush()

        log.info("TEST RESULT: %s" % result)
        return result

    def get_urls_to_process(self, urls, test_hash):
        urls_to_process = []
        for i, public_url in enumerate(urls):
            if public_url not in error_tracker:
                error_tracker[public_url] = 0
            if error_tracker.get(public_url, 0) >= MAX_ERRORS:
                log.debug("MAX_ERRORS reached for %s" % public_url)
                continue
            hash_url = public_url.replace(":hash", test_hash)
            log.debug("opening:%s" % hash_url)
            # requests[hash_url] = session.get(hash_url, background_callback=bg_cb)
            urls[i] = hash_url
            urls_to_process.append(hash_url)

        shuffle(urls_to_process)
        return urls_to_process

    def get_first_test_result(self, test_hash, result_hash):

        urls = deepcopy(public_gateways)
        if FIRST_CHOICE_GATEWAYS:
            for url in FIRST_CHOICE_GATEWAYS:
                if url in urls:
                    urls.remove(url)
            urls_to_process = self.get_urls_to_process(
                FIRST_CHOICE_GATEWAYS, test_hash)
            log.debug("FIRST_CHOICE_GATEWAYS:%s" % pformat(urls_to_process))
            res = get_first_hash(urls_to_process, result_hash)
            if res:
                log.debug("res:%s" % pformat(res))
                return res.url

        urls_to_process = self.get_urls_to_process(urls, test_hash)
        log.debug("urls_to_process:%s" % pformat(urls_to_process))
        res = get_first_hash(urls_to_process, result_hash)

        if res is None and FALLBACK_LOCAL_GATEWAYS:
            urls_to_process = self.get_urls_to_process(FALLBACK_LOCAL_GATEWAYS, test_hash)
            res = get_first_hash(urls_to_process, result_hash)

        log.debug("res:%s" % pformat(res))
        if not res:
            return None
        # log.debug("res dir() %s" % pformat(dir(res)))
        return res.url

    def write_final_file(self):
        if self.text:
            with open(self.final_file,'w') as fp:
                fp.write(self.text)
                if LOG_LEVEL <= log.INFO:
                    print("== final file ==")
                    print(self.text)
        else:
            log.error("Final xml is empty")

        log.debug("error_tracker:%s" % pformat(error_tracker))
        log.debug("reliablity_tracker:%s" % pformat(reliablity_tracker))


    def get_keys(self):
      cmd = ["ipfs", "key", "list", "-l"]
      p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
      keys = {}
      while True:
          line = p.stdout.readline()
          if line != b'':
            line = line.decode("utf8")
            line = line.rstrip()
            _hash, name = line.split(" ", 1)
            keys[name] = _hash
          else:
            break
      return keys

    def get_last_line_of_output(self, cmd):
        log.debug("cmd:%s" % pformat(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        last_line = ""
        while True:
          line = p.stdout.readline()
          if line != b'':
            line = line.decode("utf8")
            last_line = line.rstrip()
            log.debug("OUTPUT:%s" % last_line)
          else:
            break
        return last_line

    def full_publish_folder(self, folder):
        if not folder:
            return
        cmd = [
            'ipfs',
            'add',
            '-r',
            folder
        ]
        log.debug("cmd:%s" % pformat(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        hashes = []
        while True:
          line = p.stdout.readline()
          if line != b'':
            line = line.decode("utf8")
            m = re.match("added (Qm[0-9A-Za-z]{44}) (.*)", line)
            if m:
                parent_hash = m.group(1)
                name = m.group(2)
                hashes.append((name, parent_hash))
            log.debug("OUTPUT:%s" % line)
          else:
            break

        log.debug("hashes:%s" % pformat(hashes))
        return hashes

    def gen_key(self, key_name):
      # ipfs key gen --type=rsa --size=2048 mykey
        cmd = [
          "ipfs",
          "key",
          "gen",
          "--type=rsa",
          "--size=2048",
          key_name
        ]
        last_line = self.get_last_line_of_output(cmd)
        log.debug("gen_key last_line:%s" % last_line)

    def publish_folder(self, folder):
        if not folder or not os.path.exists(folder):
            return '', ''
        parent_hash = ""
        folder_name = ""
        cmd = [
            'ipfs',
            'add',
            '-r',
            folder
        ]
        last_line = self.get_last_line_of_output(cmd)
        m = re.match("added (Qm[0-9A-Za-z]{44}) (.*)", last_line)
        if m:
            parent_hash = m.group(1)
            folder_name = m.group(2)
        else:
            log.error("Unable to match regex with:%s" % last_line)
        log.debug("parent_hash:%s" % parent_hash)

        return parent_hash, folder_name

    def publish_rss_folder(self):
        parent_hash, folder_name = self.publish_folder(self.rss_folder)
        return parent_hash

    def publish_ipns(self):
        keys = self.get_keys()
        if self.key not in keys:
          self.gen_key(self.key)

        self.parent_hash = self.publish_rss_folder()
        if not self.parent_hash:
            log.error("parent_hash empty or null.  Unable to publish ipns")
            return

        self.ipns_hash = self.publish_ipns_name()
        if not self.ipns_hash:
            log.error("ipns_hash empty or null.  ipns publish failed")
            return
        else:
            with open(self.ipns_file, 'w') as fp:
                fp.write(self.ipns_hash)

        log.info("http://localhost:8080/ipns/%s" % self.ipns_hash)

    def publish_ipns_name(self):
        log.info("Publishing to ipns, this might take a while.")
        cmd = [
          "ipfs",
          "name",
          "publish",
          "--key=%s" % self.key,
          "%s" % self.parent_hash,
        ]
        last_line = self.get_last_line_of_output(cmd)
        ipns_hash = ""
        m = re.match("Published to (Qm[0-9A-Za-z]{44}): /ipfs/(Qm[0-9A-Za-z]{44})",
                     last_line)

        if m:
            ipns_hash = m.group(1)
        else:
            log.error("Unable to match ipns regex with:%s" % last_line)

        log.debug("ipns_hash:%s" % ipns_hash)
        return ipns_hash

