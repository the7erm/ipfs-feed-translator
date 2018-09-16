
import re
import os
import requests
import time
import sys
import _thread
import shutil

from config import TIME_TO_LIVE, STORAGE_DIR, LOG_LEVEL
from logger import log
from constants import HTTP_OK, HTTP_PARTIAL


def safe_filename(string):
    return re.sub('[^A-Za-z0-9\\.\\ \\_\\-]', '-', string)

def old_name_cache_file(dst_dir, url):
    basename = os.path.basename(url)
    base, ext = os.path.splitext(basename)
    log.debug("base:%s ext:%s" % (base, ext))
    cache_file = os.path.join(dst_dir, safe_filename(url))
    cache_file = "%s.cache%s" % (cache_file, ext)
    return cache_file

def name_cache_file(dst_dir, url):
    basename = os.path.basename(url)
    base, ext = os.path.splitext(basename)
    log.debug("base:%s ext:%s" % (base, ext))
    cache_file = os.path.join(dst_dir, basename)
    # cache_file = "%s.cache%s" % (cache_file, ext)
    return cache_file

def construct_cache_file_name(url, subdir=None):
    dst_dir = STORAGE_DIR
    old_cache_file = old_name_cache_file(dst_dir, url)
    cache_file = name_cache_file(dst_dir, url)

    if subdir is not None:
        src = ""
        if os.path.exists(cache_file):
            src = cache_file
        dst_dir = os.path.join(dst_dir, subdir)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        cache_file = name_cache_file(dst_dir, url)
        old_cache_file = old_name_cache_file(dst_dir, url)
        if src:
            shutil.move(src, cache_file)
            log.debug("Moving to subdir %s => %s" % (src, cache_file))

    if os.path.exists(old_cache_file):
        if not os.path.exists(cache_file):
            shutil.move(old_cache_file, cache_file)
        else:
            os.unlink(old_cache_file)
        log.debug("Renaming old_cache_file %s => %s" % (old_cache_file, cache_file))

    log.debug("old_cache_file:%s" % old_cache_file)
    log.debug("new cache_file:%s" % cache_file)
    log.debug("cache_file:%s" % cache_file)
    return cache_file

def is_cache_stale(cache_file, TTL=None, refresh=True):
    if TTL is None:
        TTL = TIME_TO_LIVE
    exists = os.path.exists(cache_file)
    size = 0
    download = refresh
    if exists:
        size = os.path.getsize(cache_file)
    else:
        download = True

    if not refresh and exists and size > 0:
        return False

    now = time.time()
    expire = now - TTL

    log.debug("now:%s" % now)
    log.debug("expire:%s" % expire)

    if exists and size > 0:
        mtime = os.path.getmtime(cache_file)
        log.debug("cache_file:%s mtime:%s" % (cache_file, mtime))
        if mtime <= expire:
            log.debug("cache_file is stale")
        else:
            download = False
            log.debug("cache_file isn't stale stale")

    return download

def download(url, refresh=True,
             TTL=None,
             success_callback=None,
             fail_callback=None,
             subdir=None,
             return_cache_file=False):

    basename = os.path.basename(url)


    cache_file = construct_cache_file_name(url, subdir)

    result = {
        "RESULT": "FAIL",
        "errors": [],
        "cache_file": cache_file,
        "TTL": TTL
    }

    download = is_cache_stale(cache_file=cache_file,
                              TTL=TTL,
                              refresh=refresh)
    if not download:
        log.debug("Already downloaded:%s" % cache_file)
        return cache_file

    if download:
        tmp_cache_file = "%s.tmp" % cache_file
        response = requests.get(url, stream=True)
        if response.status_code not in (HTTP_OK, HTTP_PARTIAL):
            msg = "http code not OK download failed"
            if fail_callback:
                result['errors'].append(msg)
                fail_callback(result)
            log.error(msg)
            return ""
        with open(tmp_cache_file, "wb") as fp:
            log.info("Downloading: %s" % url)
            log.info("Destination: %s" % tmp_cache_file)
            total_length = response.headers.get('content-length')

            if total_length is None: # no content length header
                fp.write(response.content)
            else:
                dl = 0
                total_length = int(total_length)
                for data in response.iter_content(chunk_size=1024 * 10):
                    dl += len(data)
                    fp.write(data)
                    done_int = int(50 * dl / total_length)
                    done_float = float(100 * dl / total_length)
                    ### CRITICAL    50
                    ### ERROR   40
                    ### WARNING 30
                    ### INFO    20
                    ### DEBUG   10
                    ### NOTSET  0
                    if LOG_LEVEL <= log.INFO:
                        sys.stdout.write("\rDownload progress: %s [%s%s] %0.1f%%" % (
                            basename,
                            '=' * done_int,
                            ' ' * (50-done_int),
                            done_float
                        ) )
                        sys.stdout.flush()
                    if response.status_code not in (HTTP_OK, HTTP_PARTIAL):
                        break
        if response.status_code not in (HTTP_OK, HTTP_PARTIAL):
            if os.path.exist(tmp_cache_file):
                os.remove(tmp_cache_file)
            msg = "http code not OK download failed"
            if fail_callback:
                result['errors'].append(msg)
                fail_callback(result)
            log.error(msg)
            return ""

        if LOG_LEVEL <= log.INFO:
            sys.stdout.write("\n")
            sys.stdout.flush()

        tmp_exists = os.path.exists(tmp_cache_file)
        tmp_size = os.path.getsize(tmp_cache_file)
        if tmp_exists and tmp_size > 0:
            os.rename(tmp_cache_file, cache_file)
            if os.path.exists(cache_file):
                log.info("%s => %s" % (tmp_cache_file, cache_file))
            else:
                log.error("Error moving: %s => %s" % (tmp_cache_file,
                                                      cache_file))
                result["errors"].append(
                    "Error moving: %s => %s" % (tmp_cache_file,
                                                          cache_file)
                )
        elif not tmp_exists:
            result["errors"].append(
                "tmp_cache_file: `%s` didn't exist." % tmp_cache_file
            )
        elif tmp_size <= 0:
            result["errors"].append(
                "tmp_cache_file: `%s` was empty." % tmp_cache_file
            )

        if not result["errors"] and success_callback:
            result["RESULT"] = "OK"
            result["cache_file"] = cache_file
            success_callback(result)
        elif fail_callback:
            fail_callback(result)


    return cache_file

