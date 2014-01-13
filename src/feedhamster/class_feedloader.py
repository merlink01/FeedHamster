import os
import sys
import sqlite3
import class_pluginparser
import class_sqlworker
import class_feed
import logging

COLUMNS_TO_CHECK = ['uuid','title','summary','recieved','created','updated','read','favorite',\
                'removed','encoding','mimetype','url','data']

SETTINGS_TO_CHECK = ['version','id','name','url','genre','last_search','last_compacted',\
                    'last_synced','import_date','image','image_ext','max_size','tso',\
                    'teo','feedcount','plugin']

class FeedLoader:

    def __init__(self,settings):
        self.settings = settings
        self.log = logging.getLogger('feedloader')
        self.log.debug('Starting Feedloader')
        self.feedobs = []
        self._load_feeds()

    def _check_feed_db(self, db_path, check_naming=True):
        self.log.debug('Check Feed: %s'%db_path)

        db_handle = class_sqlworker.sqlWorkerThread(db_path)
        db_handle.start()

        if  db_handle.executeCommand('list_tables') != [(u'settings',), (u'feeds',)]:
            db_handle.executeCommand('exit')
            return False

        if db_handle.executeCommand('list_columns','settings') != [u'setting', u'value']:
            db_handle.executeCommand('exit')
            return False

        feeds_columns_list = db_handle.executeCommand('list_columns','feeds')
        for entry in COLUMNS_TO_CHECK:
            self.log.debug('Testing: %s'%entry)
            if not entry in feeds_columns_list:
                self.log.warning('Column not present: %s'%entry)
                db_handle.executeCommand('exit')
                return False

        for entry in SETTINGS_TO_CHECK:
            self.log.debug('Testing: %s'%entry)

            sql = "SELECT value FROM settings WHERE setting=?"
            answer = db_handle.executeCommand('get',sql, (entry,))[0][0]

            if answer == None:
                self.log.warning('Setting not present: %s'%entry)
                db_handle.executeCommand('exit')
                return False

        if check_naming:
            name = os.path.basename(db_path)

            sql = "SELECT value FROM settings WHERE setting=?"
            answer = db_handle.executeCommand('get',sql, ('id',))[0][0]

            fid = answer + '.hdb'
            if name != fid:
                self.log.warning('Filenamename wrong: %s - Please use the FeedHamster.feed_import function.'%name)
                db_handle.executeCommand('exit')
                return False

        db_handle.executeCommand('exit')
        return True


    def get_feeds(self):
        return self.feedobs

    def reload_feeds(self):
        self._load_feeds()

    def add_new_feed(self,url,plugin):

        module = self.pluginparser.LoadPlugin(plugin)
        module = module.Plugin(url)
        feed = class_feed.Feed(module, self.settings)
        if feed.feed_initiate():
            self.feedobs.append(feed)
            return feed.feed_id
        else:
            return


    def _read_setting(self, name):

        """Helper function for fast reading Settings from DB"""

        sql = "SELECT value FROM settings WHERE setting=?"
        answer = self.db.executeCommand('get',sql, (name,))[0][0]
        return answer

    def _load_feeds(self):

        self.log.debug('Load Plugins')
        self.pluginparser = class_pluginparser.PluginParser('feedhamster',self.settings['plugindir'],'.hpi')
        modulelist = self.pluginparser.ListPlugins()

        self.log.debug('Loading DBs')
        filelist = os.listdir(self.settings['workingdir'])

        for entry in filelist:
            self.log.debug('Loading: %s' % entry)
            if os.path.splitext(entry)[1] == '.hdb':
                full_path = os.path.join(self.settings['workingdir'], entry)
                self.log.info('Load Feed: %s'%entry)

                if not self._check_feed_db(full_path):
                    self.log.warning('DB Check Error: %s'%entry)
                    continue

                self.db = class_sqlworker.sqlWorkerThread(full_path)
                self.db.start()
                url = self._read_setting('url')
                plugin = self._read_setting('plugin')
                self.db.executeCommand('exit')

                if modulelist.has_key(plugin):

                    module = self.pluginparser.LoadPlugin(plugin)
                    module = module.Plugin(url, self.settings['tempdir'])
                    feed = class_feed.Feed(module, self.settings)
                    self.feedobs.append(feed)
                    assert plugin == feed.plugin.type

                else:
                    self.log.warning('Plugin for %s could not be loaded, please download it.'%plugin)

    def _feed_update(self):
        return
        for feed in self.feedobs:

            fid = feed._read_setting('id')
            feedversion = feed._read_setting('version')
            while float(self.version) != float(feedversion):

                self.log.info('Updating %s (v%s)' % (fid, feedversion))
                feedversion = self._update(feedversion, feed)
                self.log.info('Done: New Version:%s' % feedversion)

    def _feeds_update(self, version, feed):

        if float(version) == float(0.8) or float(version) == float(0.9):
            feed._save_setting('version', 0.01, True)
            return 0.01

        if float(version) == float(0.01):
            feed._save_setting('version', 0.02, True)
            feed.db.add_row('feeds','extension','TEXT')
            if feed._read_setting('plugin') == 'rss':
                sql = "UPDATE feeds SET extension='html'"
                feed.db.put(sql)
            return 0.02

        if float(version) == float(0.02):
            feed._save_setting('version', 0.03, True)
            feed._save_setting('max_size', 1024*1024*4000)
            return 0.03

#~ global FHLOGGER
#~ FHLOGGER = logging.getLogger()
#~ fmt_string = "[%(levelname)-7s]%(asctime)s.%(msecs)-3d\
#~ %(module)s[%(lineno)-3d]/%(funcName)-10s  %(message)-8s "
#~ handler = logging.StreamHandler(sys.stderr)
#~ handler.setFormatter(logging.Formatter(fmt_string, "%H:%M:%S"))
#~ FHLOGGER.addHandler(handler)
#~ FHLOGGER.setLevel(logging.INFO)
#~
#~ wd = '/home/merlink/feeds'
#~ pd = '/home/merlink/Workspace/FeedHamster/src/plugins'
#~ fl = FeedLoader(wd,pd,0.1)
#~ print fl.get_feeds()
