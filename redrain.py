"""This is the main collection of functions that redrain uses to do basically
everything.
"""

import time
import re
import os
import urllib
from feedparser import parse
from re import search, match
from datetime import datetime

# globals
CONFIG = dict()     # basic config file, for bootstrapping everything else
PODCASTS = list()   # podcast list
OLD_URLS = set()    # urls of old episodes
OLD_GUIDS = set()   # guids of old episodes
NEW_URLS = set()    # urls of episodes that need to be comitted to file
NEW_GUIDS = set()   # urls of episodes that need to be comitted to file

DEFAULT_CONFIG = { \
                    'f_oldshows': '~/.redrain/oldshows', \
                    'f_podcasts': '~/.redrain/podcasts', \
                    'd_download_dir': '~/.redrain/download/', \
                    'f_lastrun': '~/.redrain/lastrun'}

LASTRUN = datetime(2013, 8, 24, 0, 0)

# Small hack to make sure that redrain identifies itself by user-agent
class RRopener(urllib.FancyURLopener):
    """Hack -- improve later."""
    version = "Redrain/0.4.3"

urllib._urlopener = RRopener()


def load_config(cfg_name='~/.redrain/config'):
    """Loads all needed config files for the program to run

    Arguments -- cfg_name (default='~/.redrain/config')

    Reads the base configuration file, then loads the oldshows and lastrun
    files.
    """
    global LASTRUN

    path = fixpath(cfg_name)

    # if we don't have a config file, create it
    if os.path.exists(path) == False:
        make_config()

    # open and load the config file
    f_config = open(path, 'rU')
    for line in f_config.readlines():
        # match a comment
        rex = match(r'#', line)
        if rex is not None:
            continue

        rex = match(r'(.+)=(.+)', line)
        if rex is not None:
            CONFIG[rex.group(1)] = rex.group(2)

    # straighten up paths in the config
    for path in CONFIG.keys():
        rex = match(r'(f_)', path)
        if rex is not None:
            CONFIG[path] = fixpath(CONFIG[path])

    # check for the 'oldshows' file; if it's not there, create it.
    if os.path.exists(CONFIG['f_oldshows']) == False:
        # create an empty file
        open(CONFIG['f_oldshows'], 'w').close()

    load_oldshows(CONFIG['f_oldshows'])

    # check for the lastrun file and load or create it
    if os.path.exists(CONFIG['f_lastrun']) == False:
        f_last = open(CONFIG['f_lastrun'], 'w')
        LASTRUN = datetime(2013, 8, 24, 0, 0)
        for k in range(5):
            f_last.write(str(LASTRUN.timetuple()[k]) + '\n')
        f_last.flush()
        f_last.close()

    # load up the lastrun file
    f_last = open(CONFIG['f_lastrun'], 'rU')
    dnt = list()
    for k in range(5):
        dnt.append(int(f_last.readline()))

    LASTRUN = datetime(dnt[0], dnt[1], dnt[2], dnt[3], dnt[4])

    # make sure that any directories in the configuration actually exist.
    # if they don't exist, create them.
    for directory in CONFIG.keys():
        rex = match(r'd_', directory)
        if rex is not None:
            path = fixpath(CONFIG[directory])
            if os.path.exists(path) == False:
                print path + " not found, creating path."
                os.makedirs(path)


def make_config():
    """Creates a simple defaut config directory, file, and download dir.

    Arguments -- none.

    Creates a typical default config directory (~/.redrain) and the regular
    download directory (~/.redrain/download) for the user.  Also dumps the
    keys and values from default_config to ~/.redrain/config .
    """

    # create the ~/.redrain directory if it's not there
    if os.path.exists(fixpath('~/.redrain')) == False:
        os.mkdir(fixpath('~/.redrain/'))

    # create the default download dir if it's not there
    if os.path.exists(DEFAULT_CONFIG['d_download_dir']) == False:
        os.mkdir(fixpath(DEFAULT_CONFIG['d_download_dir']) + '/')

    # create the core config file and write defaults to it
    f_config = open(fixpath('~/.redrain/config'), 'w')
    for k in DEFAULT_CONFIG.keys():
        f_config.write(k + '=' + DEFAULT_CONFIG[k] + '\n')

    f_config.flush()
    f_config.close()


def fixpath(user):
    """Normalizes a given path to a file or directory.

    Arguments - A string that should point to a file or directory.

    This is really just a simple wrapper around a couple functions in os.path
    """
    return os.path.normpath(os.path.expanduser(user))


def load_oldshows(filename):
    """Loads the oldshows file.

    Arguments -- a filename.

    Scans the oldshows files for lines that start with either 'url=' or
    'guid=' and loads them into OLD_URLS and OLD_GUIDS respectively.  Each
    line is loaded as a key and the value in the dictionaries is set to 1.
    """
    f_old = open(filename, 'rU')

    for line in f_old.readlines():
        # discard a comment
        rex = match(r'#', line)
        if rex is not None:
            continue

        rex = match(r'(guid|url)=(.+)', line)
        if rex is not None:
            if rex.group(1) == 'url':
                OLD_URLS.add(rex.group(2))
            if rex.group(1) == 'guid':
                OLD_GUIDS.add(rex.group(2))


def load_podcasts():
    """Scans the podcasts file in the config and loads it.

    Arguments -- none.

    Scans the file in CONFIG['f_podcasts'] for entries.  Each entry is a
    series of key=value pairs, and each entry is seperated by a percent
    sign ('%').  At an absolute minimum, an entry needs to contain a feedurl
    key.  At present, the only other keys supported are 'skip' and 'nicename'.
    """

    if os.path.exists(CONFIG['f_podcasts']) == False:
        return

    f_pods = open(CONFIG['f_podcasts'], 'rU')
    show = dict()
    for line in f_pods.readlines():
        # match a key=value line
        rex = match(r'(.+?)=(.+)', line)
        if rex is not None:
            show[rex.group(1)] = rex.group(2)
            continue

        # match a comment
        rex = match(r'#', line)
        if rex is not None:
            continue

        # match a % and start the next show
        rex = match(r'%', line)
        if rex is not None:
            # skip the show if the entry contains "skip=true"
            if show.get('skip', 'false') == 'true':
                show = dict()
                continue

            # if there is a feedurl, we can use it.  append it.
            if 'feedurl' in show:
                PODCASTS.append(show)

            # if there isn't, warn the user
            elif not 'feedurl' in show:
                print 'Error: show did not have a feedurl.'

            show = dict()
            continue


def scrape_feed_url(url, nicename='NoneProvided'):
    """Downloads a given URL and scrapes it for episodes.

    Arguments - a url (or even a file) that points to a XML feed.
    Optionally, the 'nicename' parameter is passed along here.

    Uses feedparser to examine a given feed and take the relevant bits of the
    'entries' array and turn it into a list of dictionaries that is
    returned to the end user.  Six keys are in each 'episode' :
    'url', 'title', 'guid', 'date', 'showname', and 'nicename'.
    """
    showlist = []
    fp_data = parse(url)

    # This warning is badly placed; shouldn't print to console in redrain.py
    if fp_data.bozo == 1:
        print '[error]',

    # iterate over the entries within the feed
    for entry in fp_data.entries:
        tmp = dict()
        tmp['title'] = entry.title
        tmp['guid'] = entry.guid
        tmp['showname'] = fp_data.feed.title
        tmp['nicename'] = nicename

        # prep updated_parsed for conversion datetime object
        dnt = list(entry.published_parsed[0:5])

        tmp['date'] = datetime(dnt[0], dnt[1], dnt[2], dnt[3], dnt[4])

        # within each entry is a list of enclosures (hopefully of length 1)
        for enclosure in entry.enclosures:
            tmp['url'] = enclosure['href']

        # temp hack, but this fixes enclosures that lack certain attributes.
        if valid_item(tmp) == True:
            showlist.append(tmp)

    return showlist


def valid_item(item):
    """Debug function: test to see if an item is up to spec."""
    for key in ['title', 'guid', 'showname', 'nicename', 'date', 'url']:
        if item.get(key, 'FAIL') == 'FAIL':
            return False
    return True


def filter_list(item):
    """Determines if a given episode is new enough to be downloaded.

    Arguments - a dict. containing at least three keys: guid, url, and date.

    Examines the provided dictionary and checks to see if the episode is new.
    This is determined by checking to see if the guid or the url provided
    already exist in the old_* hashes.  It also compares the provided date
    to the last time the program was run.
    """
    count = 0

    # check guids
    if item['guid'] in OLD_GUIDS:
        count = count + 1

    # check urls
    if item['url'] in OLD_URLS:
        count = count + 1

    # compare date
    if (LASTRUN - item['date']).days >= 0:
        count = count + 1

    if count > 1:
        return False

    return True


def save_state():
    """Dumps urls and guids to the oldshow file and updates the lastrun file.

    Arguments -- None.

    Appends the keys in NEW_URLS and NEW_GUIDS to the oldshows file, with each
    key prepended by guid= and url=.  Also updates the lastrun file with the
    current time.
    """
    global NEW_URLS
    global NEW_GUIDS

    # open up 'oldshows'
    f_old = open(CONFIG['f_oldshows'], 'a')

    # save the urls
    for url in NEW_URLS:
        f_old.write('url=' + url + '\n')

    # save the guids
    for url in NEW_GUIDS:
        f_old.write('guid=' + url + '\n')

    # clean up
    f_old.flush()
    f_old.close()

    # save datetime
    f_last = open(CONFIG['f_lastrun'], 'w')
    for k in time.gmtime()[0:5]:
        f_last.write(str(k) + '\n')

    f_last.flush()
    f_last.close()

    NEW_URLS = set()
    NEW_GUIDS = set()


def sanitize_filename(fname):
    """Makes a given name safe for FAT32

    Arguments : fname -- a string or unicode string.

    Since FAT32 is the "lowest common denominator" of filesystems and is the
    most likely one to be found on a mp3 player, this function changes unicode
    strings to plain strings, truncates them to 250 characters and strips
    "bad" characters out.
    """
    # if fname is unicode, strip it first
    if type(fname) == unicode:
        fname = ''.join([x for x in fname if ord(x) > 31 and ord(x) < 129])

    # turn into a string, reduce to 250 characters
    fname = str(fname)[0:250]

    # clean 'naughty' characters
    naughty = ':;*?"|\/<>'
    trans = dict(zip([x for x in naughty], ['' for x in xrange(len(naughty))]))
    for key, value in trans.iteritems():
        fname = fname.replace(key, value)

    return fname


def download_episode(episode, custom=None):
    """Downloads a podcast episode to the download directory.

    Arguments : episode -- a small dictionary that contains the keys 'url'
    and 'title'.

    Simply downloads a specified episode to the configured download directory.
    Makes a call to sanitize_filename to make the file safe to save anywhere.
    """

    # construct filename
    # - get extension from url
    ext = sanitize_filename(search('(.+)(\..+?)$', episode['url']).group(2))

    # clean up title, concatenate with extension and use it as the filename
    fname = sanitize_filename(episode['title']) + ext

    # skip downloading and bail if the user asked for it
    if CONFIG.get('skipdl', 'false') == 'true':
        mark_as_old(episode)
        return

    # download the file
    if 'dl_file_name' in episode:
        urllib.urlretrieve(episode['url'], \
            fixpath(CONFIG['d_download_dir'] + custom))
    else:
        urllib.urlretrieve(episode['url'], \
            fixpath(CONFIG['d_download_dir'] + fname))

    # mark episode as old
    mark_as_old(episode)


def mark_as_old(episode):
    """Registers a specified episode as "old".

    Arguments : episode -- A small dictionary that contains at least two
    keys : 'url', and 'guid'.

    The data in these keys added to both the new urls/guids and the old
    urls/guids dictionaries.  They're added to "old" so that the same episode
    isn't downloaded multiple times and "new" so that they get written to
    file later.
    """

    OLD_URLS.add(episode['url'])
    OLD_GUIDS.add(episode['guid'])

    NEW_URLS.add(episode['url'])
    NEW_GUIDS.add(episode['guid'])


def custom_name(podcast, fstring):
    """Creates a custom episode name for a downloaded show.

    Agruments : podcast -- a dict with particular keys and string - the string
    that will be used to create the filename.

    The string should contain items to be replaced as marked by percent signs
    with braces indicate what the token should be replaced with.  An example:

    '%{show}-%{episode}.mp3' -- might come out as 'Metalcast- pisode 19.mp3'
    """

    # copy the original hash
    replacements = podcast.copy()

    # expand the hash and make sure that everything in it is a string
    # - create filename from url
    replacements['ext'] = search('(.+)(\..+?)$', podcast['url']).group(2)

    # - replace date and time with strings
    tmp = replacements['date']
    replacements['date'] = replacements['date'].strftime('%Y-%m-%d')
    replacements['time'] = tmp.strftime('%H%M')

    # - today's date and time strings (as opposed to 'updated' time/date)
    tmp = time.localtime()
    now = datetime(tmp[0], tmp[1], tmp[2], tmp[3], tmp[4])
    replacements['ltime'] = now.strftime('%H%M')
    replacements['ldate'] = now.strftime('%Y-%m-%d')

    # construct the regular expression from the keys of 'replacements'
    allkeys = '%{('
    for key in replacements.keys():
        allkeys = allkeys + key + '|'
    allkeys = allkeys[:-1] + ')}'

    # replace the user-specified tokens
    for _ in xrange(fstring.count('%')):
        result = search(allkeys, fstring)
        if result is not None:
            fstring = re.sub('%{' + result.group(1) + '}', \
                replacements[result.group(1)], fstring)

    # clean it up, just in case
    fstring = sanitize_filename(fstring)

    # add in the extension
    #fstring = fstring + replacements['ext']

    # we're done, return the string
    return fstring

