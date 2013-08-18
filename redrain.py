"""This is the main collection of functions that redrain uses to do basically
everything.
"""

import string
import time
import re
import os
import urllib
from feedparser import parse
from re import search, match
from datetime import datetime

# globals
config = dict()     # basic config file, for bootstrapping everything else
podcasts = list()   # podcast list
old_urls = set()    # urls of old episodes
old_guids = set()   # guids of old episodes
new_urls = set()    # urls of episodes that need to be comitted to file
new_guids = set()   # urls of episodes that need to be comitted to file

default_config = { \
                    'f_oldshows': '~/.redrain/oldshows', \
                    'f_podcasts': '~/.redrain/podcasts', \
                    'd_download_dir': '~/.redrain/download/', \
                    'f_lastrun': '~/.redrain/lastrun'}

lastrun = datetime(2013, 8, 18, 0, 0)

# Small hack to make sure that redrain identifies itself by user-agent
class RRopener(urllib.FancyURLopener):
    version = "Redrain/0.4.3"

urllib._urlopener = RRopener()

def load_config(cfg_name='~/.redrain/config'):
    """Loads all needed config files for the program to run

    Arguments -- cfg_name (default='~/.redrain/config')

    Reads the base configuration file, then loads the oldshows and lastrun
    files.
    """
    global lastrun

    path = fixpath(cfg_name)

    # if we don't have a config file, create it
    if os.path.exists(path) == False:
        make_config()

    # open and load the config file
    f = open(path, 'rU')
    for line in f.readlines():
        # match a comment
        m = match(r'#', line)
        if m is not None:
            continue

        m = match(r'(.+)=(.+)', line)
        if m is not None:
            config[m.group(1)] = m.group(2)

    # straighten up paths in the config
    for n in config.keys():
        m = match(r'(f_)', n)
        if m is not None:
            config[n] = fixpath(config[n])

    # check for the 'oldshows' file; if it's not there, create it.
    if os.path.exists(config['f_oldshows']) == False:
        # create an empty file
        open(config['f_oldshows'], 'w').close()

    load_oldshows(config['f_oldshows'])

    # check for the lastrun file and load or create it
    if os.path.exists(config['f_lastrun']) == False:
        f = open(config['f_lastrun'], 'w')
        lastrun = datetime(2009, 11, 15, 0, 0)
        for k in range(5):
            f.write(str(lastrun.timetuple()[k]) + '\n')
        f.flush()
        f.close()

    # load up the lastrun file
    f = open(config['f_lastrun'], 'rU')
    d = list()
    for k in range(5):
        d.append(int(f.readline()))

    lastrun = datetime(d[0], d[1], d[2], d[3], d[4])

    # make sure that any directories in the configuration actually exist.
    # if they don't exist, create them.
    for n in config.keys():
        m = match(r'd_', n)
        if m is not None:
            p = fixpath(config[n])
            if os.path.exists(p) == False:
                print p + " not found, creating path."
                os.makedirs(p)


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
    if os.path.exists(default_config['d_download_dir']) == False:
        os.mkdir(fixpath(default_config['d_download_dir']) + '/')

    # create the core config file and write defaults to it
    f = open(fixpath('~/.redrain/config'), 'w')
    for k in default_config.keys():
        f.write(k + '=' + default_config[k] + '\n')

    f.flush()
    f.close()


def fixpath(u):
    """Normalizes a given path to a file or directory.

    Arguments - A string that should point to a file or directory.

    This is really just a simple wrapper around a couple functions in os.path
    """
    return os.path.normpath(os.path.expanduser(u))


def load_oldshows(filename):
    """Loads the oldshows file.

    Arguments -- a filename.

    Scans the oldshows files for lines that start with either 'url=' or
    'guid=' and loads them into old_urls and old_guids respectively.  Each
    line is loaded as a key and the value in the dictionaries is set to 1.
    """
    f = open(filename, 'rU')

    for line in f.readlines():
        # discard a comment
        m = match(r'#', line)
        if m is not None:
            continue

        m = match(r'(guid|url)=(.+)', line)
        if m is not None:
            if m.group(1) == 'url':
                old_urls.add(m.group(2))
            if m.group(1) == 'guid':
                old_guids.add(m.group(2))


def load_remote_oldshows(url):
    """Grabs an oldshows file from a remote location and adds it locally.

    Arguments -- a url that points to an oldshows file on the web.

    Downloads a remote oldshows file and scans it just like a standard file.
    Items new to the local state are added to *both* old_* (because the files
    shouldn't be downloaded) and new_* (so that they're marked as old for the
    next run.)
    """
    # global data
    global old_guids, old_urls
    global new_guids, new_urls

    # fresh sets for the data pulled from the remote file
    r_urls = set()
    r_guids = set()

    # open the url
    f = urllib.urlopen(url)

    # iterate over the url
    for line in f.readlines():
        # discard comments
        m = match(r'#', line)
        if m is not None:
            continue

        m = match(r'(guid|url)=(.+)', line)
        if m is not None:
            if m.group(1) == 'url':
                r_urls.add(m.group(2))
            if m.group(1) == 'guid':
                r_guids.add(m.group(2))

    # determine which entries are new and put them in the new_* sets
    new_urls = new_urls | (r_urls - old_urls)
    new_guids = new_guids | (r_guids - old_guids)

    # add the remote urls to the old_* sets
    old_urls = old_urls | r_urls
    old_guids = old_guids | r_guids


def load_podcasts():
    """Scans the podcasts file in the config and loads it.

    Arguments -- none.

    Scans the file in config['f_podcasts'] for entries.  Each entry is a
    series of key=value pairs, and each entry is seperated by a percent
    sign ('%').  At an absolute minimum, an entry needs to contain a feedurl
    key.  At present, the only other keys supported are 'skip' and 'nicename'.
    """

    if os.path.exists(config['f_podcasts']) == False:
        return

    f = open(config['f_podcasts'], 'rU')
    show = dict()
    for line in f.readlines():
        # match a key=value line
        m = match(r'(.+?)=(.+)', line)
        if m is not None:
            show[m.group(1)] = m.group(2)
            continue

        # match a comment
        m = match(r'#', line)
        if m is not None:
            continue

        # match a % and start the next show
        m = match(r'%', line)
        if m is not None:
            # skip the show if the entry contains "skip=true"
            if show.get('skip', 'false') == 'true':
                show = dict()
                continue

            # if there is a feedurl, we can use it.  append it.
            if 'feedurl' in show:
                podcasts.append(show)

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
    f = parse(url)

    # This warning is badly placed; shouldn't print to console in redrain.py
    if f.bozo == 1:
        print '[error]',

    # iterate over the entries within the feed
    for entry in f.entries:
        tmp = dict()
        tmp['title'] = entry.title
        tmp['guid'] = entry.guid
        tmp['showname'] = f.feed.title
        tmp['nicename'] = nicename

        # prep updated_parsed for conversion datetime object
        d = list(entry.published_parsed[0:5])

        tmp['date'] = datetime(d[0], d[1], d[2], d[3], d[4])

        # within each entry is a list of enclosures (hopefully of length 1)
        for enclosure in entry.enclosures:
            tmp['url'] = enclosure['href']

        # temp hack, but this fixes enclosures that lack certain attributes.
        if valid_item(tmp) == True:
            showlist.append(tmp)

    return showlist

def valid_item(item):
    """Debug function: test to see if an item is up to spec."""
    for x in ['title', 'guid', 'showname', 'nicename', 'date', 'url']:
        if item.get(x, 'FAIL') == 'FAIL':
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
    if item['guid'] in old_guids:
        count = count + 1

    # check urls
    if item['url'] in old_urls:
        count = count + 1

    # compare date
    if (lastrun - item['date']).days >= 0:
        count = count + 1

    if count > 1:
        return False

    return True


def save_state():
    """Dumps urls and guids to the oldshow file and updates the lastrun file.

    Arguments -- None.

    Appends the keys in new_urls and new_guids to the oldshows file, with each
    key prepended by guid= and url=.  Also updates the lastrun file with the
    current time.
    """
    global new_urls
    global new_guids

    # open up 'oldshows'
    f = open(config['f_oldshows'], 'a')

    # save the urls
    for n in new_urls:
        f.write('url=' + n + '\n')

    # save the guids
    for n in new_guids:
        f.write('guid=' + n + '\n')

    # clean up
    f.flush()
    f.close()

    # save datetime
    f = open(config['f_lastrun'], 'w')
    for k in time.gmtime()[0:5]:
        f.write(str(k) + '\n')

    f.flush()
    f.close()

    new_urls = set()
    new_guids = set()


def is_ascii(n):
    """Checks to make sure that a given character is ASCII

    Arguments -- one byte.

    Returns True if the ordinal value of n is >= 32 and <= 128, False
    otherwise.  Used as a helper function to sanitize_filename.
    """
    k = ord(n)
    if k < 32 or k > 128:
        return False

    return True


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
        fname = ''.join([x for x in fname if is_ascii(x) == True])

    # turn into a string, reduce to 250 characters
    fname = str(fname)[0:250]

    # clean 'naughty' characters
    fname = string.translate(fname, None, ':;*?"|\/<>')

    return fname


def download_episode(episode, custom=None):
    """Downloads a podcast episode to the download directory.

    Arguments : episode -- a small dictionary that contains the keys 'url'
    and 'title'.

    Simply downloads a specified episode to the configured download directory.
    Makes a call to sanitize_filename to make the file safe to save anywhere.
    """
    global config

    # construct filename
    # - get extension from url
    ext = sanitize_filename(search('(.+)(\..+?)$', episode['url']).group(2))

    # clean up title, concatenate with extension and use it as the filename
    fname = sanitize_filename(episode['title']) + ext

    # skip downloading and bail if the user asked for it
    if config.get('skipdl', 'false') == 'true':
        mark_as_old(episode)
        return

    # download the file
    if 'dl_file_name' in episode:
        urllib.urlretrieve(episode['url'], fixpath(config['d_download_dir'] + custom))
    else:
        urllib.urlretrieve(episode['url'], fixpath(config['d_download_dir'] + fname))

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

    old_urls.add(episode['url'])
    old_guids.add(episode['guid'])

    new_urls.add(episode['url'])
    new_guids.add(episode['guid'])


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
    for n in replacements.keys():
        allkeys = allkeys + n + '|'
    allkeys = allkeys[:-1] + ')}'

    # replace the user-specified tokens
    for x in xrange(fstring.count('%')):
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
