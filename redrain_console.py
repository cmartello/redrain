#!/usr/bin/env python2.7

"""Console version of the redrain podcast downloader.  Ideal for automated
downloads and non-interactive terminal usage.  See the README."""


import redrain
from re import match
from sys import argv
from feedparser import parse


def query_podcasts():
    """Interactively create a podcasts file by querying the user.

    Arguments -- none.

    Asks the user for a series of podcast feed urls and dumps them to the
    podcasts file.  Uses feedparser to find the "nicename" of the show
    for the user and adds that to the file.
    """
    print "No podcasts found in " + redrain.config['f_podcasts']
    print "Please enter some feed URLs below."
    print "(Enter a blank line to quit)"

    # loop for adding podcasts; user enters urls, the feed name is
    # fetched from the net and both are put into a file.
    podcasts = list()
    user = 'ignore'
    while user != '':
        show = dict()
        user = raw_input('> ')
        if user == '':
            continue
        show['feedurl'] = user
        # use feedparser to figure out the 'nicename'
        print "Finding show's 'nicename' ...",
        f = parse(user)
        if f.feed.get('title', 'None') == 'None':
            print "Not found.  What do you want to call this show?"
            show['nicename'] = raw_input('> ')
        else:
            print "Found."
            show['nicename'] = f.feed.title

        podcasts.append(show)

        # write podcast urls to file
        podfile = open(redrain.config['f_podcasts'], 'w')

    for p in podcasts:
        podfile.write('feedurl=' + p['feedurl'] + '\n')
        podfile.write('nicename=' + p['nicename'] + '\n')
        podfile.write('%\n')

    # close the podcast file
    podfile.flush()
    podfile.close()


def query_config():
    """Interactively create configuration options by querying the user.

    Arguments -- none.

    Asks the user several questions about how they would like the program
    configured, most importantly "where do you want your shows downloaded
    to?"  Currently, it is neither descriptive or helpful, but functional.
    """
    print 'Enter the desired values for your config options.'
    print 'The default value in brackets, enter a blank line to keep it.'
    for item in redrain.default_config.keys():
        print item, '[', redrain.default_config[item], ']',
        user = raw_input('>')
        if user == '':
            continue
        else:
            redrain.default_config[item] = user

        # clean up paths
        redrain.default_config[item] = \
            redrain.fixpath(redrain.default_config[item])

        # special case; append a '/' to the end of one item.  hack :(
        if item == 'd_download_dir' and redrain.default_config[item][-1]\
            != '/':
            redrain.default_config['d_download_dir'] = \
                redrain.default_config['d_download_dir'] + '/'


def args_config():
    """Pulls configuration information from the command line.

    Arguments -- none.

    Reads options specified on the command line in the format of key=value and
    copies those keys/values into redrain.config for later.  Note that these
    options are applied *after* the configuration file is read; the idea is
    that an argument on the command line is "for this run" and something in
    a config file is "standard."
    """

    # everything in argv other than the script name
    for item in argv[1:]:
        m = match(r'(.+)=(.+)', item)
        if m is not None:
            redrain.config[m.group(1)] = m.group(2)

            # special case for directories
            if m.group(1)[0:1] == 'd' and m.group(2)[-1:] != '/':
                redrain.config[m.group(1)] = m.group(2) + '/'


# ---- main program starts here ----

# check the command line to see if an alternate configuration file has
# been requested.
cfg_file = None
for item in argv[1:]:
    m = match(r'(.+)=(.+)', item)
    if m is not None:
        if m.group(1) == 'config':
            cfg_file = redrain.fixpath(m.group(2))

# load the config file if the user specifed one, use the default one otherwise.
if cfg_file is not None:
    redrain.load_config(cfg_file)
else:
    redrain.load_config()

# overwrite configuration items with command-line arguments
args_config()

# if specified, load a remote oldshows file
if 'r_oldshows' in redrain.config.keys():
    print 'Loading a remote oldshows file...',
    redrain.load_remote_oldshows(redrain.config['r_oldshows'])
    print 'Done.'

# load the podcast list
redrain.load_podcasts()

# if no podcasts were loaded, start asking the user for feed urls
if len(redrain.podcasts) == 0:
    query_podcasts()
    redrain.load_podcasts()

# download queue
queue = list()

# show being scraped
shownum = 1

# download and scan all feeds
for n in redrain.podcasts:
    print 'scraping [' + str(shownum) + ']',

    # if the show has a nice name defined, use it
    if 'nicename' in n:
        print n['nicename'],
        feed = redrain.scrape_feed_url(n['feedurl'], n['nicename'])
    else:
        print n['feedurl'],
        feed = redrain.scrape_feed_url(n['feedurl'])

    # filter out old episodes
    tmp = [x for x in feed if redrain.filter_list(x) == True]

    # hack -- add the dl_file_name to each item in the feed
    if 'dl_file_name' in n:
        for x in tmp:
            x['dl_file_name'] = n['dl_file_name']

    # status report for the user
    print '[' + str(len(feed)) + '/' + str(len(tmp)) + ']'

    # enqueue the new episodes to be downloaded later
    queue.extend(tmp)

    # we're done, bump the show number
    shownum = shownum + 1

# download the episode queue
print '---------------------------------------------------------------'
print str(len(queue)) + ' episodes to download.'

for n in queue:
    # clean up the filename -- print can crash when it gets unicode.
    n['title'] = redrain.sanitize_filename(n['title'])

    # download the episode
    if 'dl_file_name' in n:
        dlfn = redrain.custom_name(n, n['dl_file_name'])
        print 'downloading: ' + dlfn + ' ...'
        redrain.download_episode(n, dlfn)
    else:
        print 'downloading: ' + n['title'] + ' ...'
        redrain.download_episode(n)
print '---------------------------------------------------------------'

# tell the user where everything has been downloaded to
print 'episodes downloaded to : ' + redrain.config['d_download_dir']

# save the urls/guids to file
redrain.save_state()
