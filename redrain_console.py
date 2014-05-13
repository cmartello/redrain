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
    print "No podcasts found in " + redrain.CONFIG['f_podcasts']
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
        url = parse(user)
        if url.feed.get('title', 'None') == 'None':
            print "Not found.  What do you want to call this show?"
            show['nicename'] = raw_input('> ')
        else:
            print "Found."
            show['nicename'] = url.feed.title

        podcasts.append(show)

        # write podcast urls to file
        podfile = open(redrain.CONFIG['f_podcasts'], 'w')

    for podcast in podcasts:
        podfile.write('feedurl=' + podcast['feedurl'] + '\n')
        podfile.write('nicename=' + podcast['nicename'] + '\n')
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
    for key in redrain.DEFAULT_CONFIG.keys():
        print key, '[', redrain.DEFAULT_CONFIG[key], ']',
        user = raw_input('>')
        if user == '':
            continue
        else:
            redrain.DEFAULT_CONFIG[key] = user

        # clean up paths
        redrain.DEFAULT_CONFIG[key] = \
            redrain.fixpath(redrain.DEFAULT_CONFIG[key])

        # special case; append a '/' to the end of one item.  hack :(
        if key == 'd_download_dir' and redrain.DEFAULT_CONFIG[key][-1]\
            != '/':
            redrain.DEFAULT_CONFIG['d_download_dir'] = \
                redrain.DEFAULT_CONFIG['d_download_dir'] + '/'


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
    for argument in argv[1:]:
        rex = match(r'(.+)=(.+)', argument)
        if rex is not None:
            redrain.CONFIG[rex.group(1)] = rex.group(2)

            # special case for directories
            if rex.group(1)[0:1] == 'd' and rex.group(2)[-1:] != '/':
                redrain.CONFIG[rex.group(1)] = rex.group(2) + '/'


# ---- main program starts here ----
if __name__ == '__main__':
    # check the command line to see if an alternate configuration file has
    # been requested.
    CFG_FILE = None
    for item in argv[1:]:
        m = match(r'(.+)=(.+)', item)
        if m is not None:
            if m.group(1) == 'config':
                CFG_FILE = redrain.fixpath(m.group(2))

    # load the config file if the user specifed one, else use the default
    if CFG_FILE is not None:
        redrain.load_config(CFG_FILE)
    else:
        redrain.load_config()

    # overwrite configuration items with command-line arguments
    args_config()

    # load the podcast list
    redrain.load_podcasts()

    # if no podcasts were loaded, start asking the user for feed urls
    if len(redrain.PODCASTS) == 0:
        query_podcasts()
        redrain.load_podcasts()

    # download queue
    QUEUE = list()

    # show being scraped
    SHOWNUM = 1

    # download and scan all feeds
    for n in redrain.PODCASTS:
        print 'scraping [' + str(SHOWNUM) + ']',

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
        QUEUE.extend(tmp)

        # we're done, bump the show number
        SHOWNUM = SHOWNUM + 1

    # download the episode queue
    print '---------------------------------------------------------------'
    print str(len(QUEUE)) + ' episodes to download.'

    for n in QUEUE:
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
        print '\n'
    print '---------------------------------------------------------------'

    # tell the user where everything has been downloaded to
    print 'episodes downloaded to : ' + redrain.CONFIG['d_download_dir']

    # save the urls/guids to file
    redrain.save_state()
