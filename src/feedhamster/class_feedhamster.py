#!/usr/bin/env python

"""class_feedhamster.py
This Library Manages the Downloading of whole RSS Feed.
Feeds and Metadata are managed in DBs
"""

__author__ = "Merlink"
__website__ = "https://github.com/merlink01/FeedHamster"
__email__ = "Bitmessage:BM-BbmSsPKPa1azaBaMdsSRaDPJxvf9CrYu"
__copyright__ = "Copyright C2013,C2014, Merlin Kessler"
__thanks__ = ["MIK:www.mik-digital.de"]
__version__ = 0.03

import os
import sys
import time
import shutil
import logging
import traceback
import threading
import StringIO
import sqlite3
import Queue
from helper_export import feed_export
import class_feedloader
import class_feed

class FeedHamster(object):

    """FeedHamster object
    With this object we can organise our Feeds
    path = Working directory
    """

    def __init__(self, workingdir, download_pulse=20, cleanup_pulse=120, maxthreads=5):
        self.log = logging.getLogger('feedhamster')
        self.offline_mode = False
        self.shutdown = False

        self.settings = {}
        self.settings['version'] = __version__
        self.settings['workingdir'] = workingdir
        self.settings['tempdir'] = os.path.join(workingdir,'temp')
        self.settings['plugindir'] = os.path.abspath('plugins')
        self.settings['maxthreads'] = maxthreads
        self.settings['download_timeout'] = 10
        self.settings['download_pulse'] = download_pulse
        self.settings['cleanup_pulse'] = cleanup_pulse

        self.log.info('FeedHamster is starting up...')
        for entry in self.settings:
            self.log.info('%s:\t %s'%(entry.upper(),self.settings[entry]))


        # Test and Create Pathes

        if not os.path.isdir(self.settings['workingdir']):
            try:
                os.makedirs(self.settings['workingdir'])
            except:
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                tmp.seek(0, 0)
                self.log.error(tmp.read())
                tmp.close()
                sys.exit(1)

        #Temppath
        shutil.rmtree(self.settings['tempdir'],ignore_errors=True)
        if not os.path.isdir(self.settings['tempdir']):
            try:
                os.makedirs(self.settings['tempdir'])
            except:
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                tmp.seek(0, 0)
                self.log.error(tmp.read())
                tmp.close()
                sys.exit(1)

        #Plugin
        if not os.path.isdir(self.settings['plugindir']):
            try:
                os.makedirs(self.settings['plugindir'])
            except:
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                tmp.seek(0, 0)
                self.log.error(tmp.read())
                tmp.close()
                sys.exit(1)

        self.feedloader = class_feedloader.FeedLoader(self.settings)
        self.feedobs = self.feedloader.get_feeds()

        td = threading.Thread(target=self._worker_thread)
        td.setName('worker_thread')
        td.start()

        self.log.info('Feedhamster started up correct')


    def _worker_thread(self):

        self.log.info('Starting up worker Thread')

        self.worker_queue = Queue.Queue()
        self.worker_status = None
        self.worker_job = None
        self.download_time = time.time()
        self.cleanup_time = time.time()

        while True:

            try:
                self.worker_job = self.worker_queue.get(block=True,timeout=0.2)
                self.log.info('Got Job: %s'%self.worker_job.upper())
            except:

                if self.settings['download_pulse'] > 0:
                    if self.download_time + self.settings['download_pulse'] * 60 < int(time.time()):
                        if not 'download' in self.worker_queue.queue:
                            if not self.worker_job == 'download':
                                self.log.debug('AutoDownload')
                                self.worker_queue.put('download')
                                self.download_time = time.time()


                if self.settings['cleanup_pulse'] > 0:
                    if self.cleanup_time + self.settings['cleanup_pulse'] * 60 < int(time.time()):
                        if not 'download' in self.worker_queue.queue:
                            if not self.worker_job == 'cleanup':
                                self.log.debug('AutoCleanup')
                                self.worker_queue.put('cleanup')
                                self.cleanup_time = time.time()

                continue

            if self.worker_job == 'shutdown':

                for obj in self.feedobs:
                    obj.feed_close()
                    del obj

                del self.feedobs



                self.log.info('FeedHamster closed correct')

                return

            #Data Download
            if self.worker_job == 'download':
                if self.offline_mode:
                    self.log.info('Dont download, Offline Mode is aktivated')
                    self.worker_job = None
                    continue

                count = len(self.feedobs)
                counter = 0
                count_of_jobs = len(self.feedobs)

                self.worker_status = 0
                for feed in self.feedobs:

                    while self._count_threads('download_thread') >=  self.settings['maxthreads']:
                        time.sleep(1)

                    self.worker_status = int(100 * float(counter) / float(count))
                    counter += 1
                    self.log.info("""Download: %2d Percent"""%self.worker_status)

                    if 'shutdown' in self.worker_queue.queue:
                        self.log.info('Ending Downloads for shutdown')
                        break

                    self.log.debug('Download: %s' % feed._read_setting('id'))

                    td = threading.Thread(target=feed.feed_download)
                    td.setName('download_thread')
                    td.start()
                else:
                    #All Downloads are started - Waiting for them to end
                    while self._count_threads('download_thread') != 0:

                        if self.shutdown:
                            self.log.info('Ending Downloads for shutdown')
                            break

                        self.log.debug('Waiting to finish sync: Running %s'%self._count_threads('retrieve_thread'))
                        time.sleep(1)
                    else:
                        self.log.info('Download: Done')
                        self.worker_status = None
                        self.worker_job = None


            if self.worker_job == 'cleanup':

                count = len(self.feedobs)
                counter = 0
                self.compact_status = 0
                for feed in self.feedobs:

                    self.log.info('Cleanup: %s'%feed.feed_id)

                    if 'shutdown' in self.worker_queue.queue:
                        self.log.info('Ending Cleanups for shutdown')
                        break

                    self.worker_status = int(100 * float(counter) / float(count))
                    counter += 1
                    self.log.info("""Cleanup: %2d Percent"""%self.worker_status)

                    feed.feed_cleanup()
                else:
                    self.log.info('Cleanup Done')
                    self.worker_status = None
                    self.worker_job = None




    #~ def search(self, keyword, unread=False, favorites=False, startTime=-1, endTime=-1):
        #~ found = []
        #~ for ob in self.feedobs:
            #~ fid = ob._read_setting('id')
            #~ log.debug('Searching in: %s'%fid)
            #~ feeds = ob.search(keyword=keyword,unread=unread,favorites=favorites,startTime=startTime,endTime=endTime)
            #~ for info in feeds:
                #~ found.append(fid,info)


    def _count_threads(self,name):

        """This function counts running Threads"""

        thcount = 0
        threads = threading.enumerate()
        for th in threads:
            if th.getName() == name:
                if th.is_alive():
                    thcount += 1
        return thcount

    def feeds_list(self):
        out = {}
        for ob in self.feedobs:
            fid = ob._read_setting('id')
            url = ob._read_setting('url')
            name = ob._read_setting('name')
            version = ob._read_setting('version')
            genre = ob._read_setting('genre')
            out[fid] = {'url': url, 'name': name, 'version': version, 'genre':genre}
        return out

    def feed_get(self, feedid):
        for obj in self.feedobs:
            if obj._read_setting('id') == feedid:
                return obj

    def plugins_list(self):
        return self.feedloader.pluginparser.ListPlugins()

    def feed_create(self, url, plugin='rss'):

        """ Add a new Feed """

        self.log.debug('Adding: %s'%url)

        self.log.debug('Check awareness')
        for obj in self.feedobs:
            if obj.url == url:
                self.log.warning('Feed already inside: %s' % url)
                return
        self.log.debug('Done')

        return self.feedloader.add_new_feed(url,plugin)

    def feed_delete(self, uuid):
        counter = 0
        for obj in self.feedobs:
            if obj._read_setting('id') == uuid:
                if 'deletionCleanup' in dir(obj.plugin):
                    if not obj.plugin.deletionCleanup():
                        log.warning('Parser Cleanup Error')
                del self.feedobs[counter]
            counter += 1

        path = os.path.join(self.settings['workingdir'], '%s.hdb' % uuid)
        os.remove(path)

    def feed_export(self,fid,export_path):
        try:
            counter = -1
            for obj in self.feedobs:
                counter += 1
                if obj.feed_id == fid:
                    del self.feedobs[counter]
                    obj.feed_close()
                    db_path = obj.db_path
                    self.log.info('Exporting: %s --> %s'%(db_path,export_path))
                    shutil.copyfile(db_path,export_path)
            self.feedloader = class_feedloader.FeedLoader(self.settings)
            self.feedobs = self.feedloader.get_feeds()
            connection = sqlite3.connect(export_path)
            cursor = connection.cursor()
            sql = "UPDATE feeds SET read=0"
            cursor.execute(sql)
            sql = "UPDATE feeds SET favorite=0"
            cursor.execute(sql)
            connection.commit()
            connection.close()
            #~ assert False
            return None
        except:
            tmp = StringIO.StringIO()
            traceback.print_exc(file=tmp)
            tmp.seek(0, 0)
            errmsg = tmp.read()
            self.log.error(errmsg)
            tmp.close()
            return errmsg


    def download(self,*args):
        if not 'download' in self.worker_queue.queue:
            if not self.worker_job == 'download':
                self.worker_queue.put('download')


    def feedhamster_shutdown(self,*args):
        self.shutdown = True
        self.worker_queue.put('shutdown')
        shutil.rmtree(self.settings['tempdir'],ignore_errors=True)


