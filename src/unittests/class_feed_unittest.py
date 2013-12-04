import class_feed
import unittest
import time
import tempfile
import logging
import os
import sys

class TestPlugin:
    def __init__(self):
        self.online = True
        self.url = 'testplugin'
        self.type = 'testplugin'
        self.count = 1
        self.image = -1
        self.imageextension = -1

        self.uuidlist = []
        self.newsdict = {}
        self.counter = 0
    
    def syncMeta(self):
        
        self.counter += 1
        counter = self.counter
        self.uuidlist.append('uuid%s'%counter)
        news = {}
        news['uuid'] = 'uuid%s'%counter
        news['url'] = 'url%s'%counter
        news['title'] = 'title%s'%counter
        news['summary'] = 'summary%s'%counter
        news['rtime'] = time.time()
        news['ctime'] = counter
        news['utime'] = counter
        news['mimetype'] = 'text/text'
        self.newsdict[news['uuid']] = news
        return True

    def getList(self):
        return self.uuidlist
        
    def getMeta(self,newsuuid):
        return self.newsdict[newsuuid]
        
    def getData(self,newsuuid):
        newsmeta = self.newsdict[newsuuid]
        newsmeta['encoding'] = 'utf8'
        newsmeta['data'] = 'data_%s'%newsuuid
        return newsmeta
        
    def isOnline(self):
        return self.online
        
    def decryptData(self,data):
        log.info('Decrypting Data')
        return data





class TestSettings(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        global TestFeed
        global TestPluginObject
        global TestPath
        TestPath = tempfile.mkdtemp()
        print 'Testpath: %s'%TestPath
        TestPluginObject = TestPlugin()
        TestFeed = class_feed.Feed(TestPluginObject, TestPath, timeout=10, maxthreads=1)
        TestFeed.__version__ = 0.1

    @classmethod
    def tearDownClass(cls):
        pass

    def test_01_create_feed(self):
        TestFeed.FeedInitiate()
        
    def test_02_syncing(self):
        TestPluginObject.online = False
        assert TestFeed.FeedSync() == False
        TestPluginObject.online = True
        assert TestFeed.FeedSync() == True    
        assert TestFeed.FeedSync() == True
        
    def test_03__getmeta_setmeta(self):
        messageuuids = TestFeed.FeedSearch()
        testuuid = messageuuids[0]
        meta = TestFeed.MessageGetMeta(testuuid)
        assert meta['created'] == 3.0,meta['created']
        assert meta['updated'] == 3.0,meta['updated']

        assert meta['read'] == False
        assert meta['removed'] == False
        assert meta['favorite'] == False
        
        assert meta['url'] == 'url3'
        assert meta['title'] == 'title3'
        assert meta['summary'] == 'url3\nsummary3\n\n',meta['summary']
        assert meta['encoding'] == 'utf8'
        assert meta['mimetype'] == 'text/text'

        #~ assert meta == {'updated': 2.0, 'encoding': u'utf8', 'read': False, 
        #~ 'removed': False, 'mimetype': u'text/text', 'uuid': 'testplugin-e1943afac16b10dff1e61bb170bd885d', 
        #~ 'title': u'title2', 'url': u'url2', 'recieved': 1381663832.488509, 'created': 2.0, 'favorite': False, 'summary': u'url2\nsummary2\n\n'}
        print meta
        
    #~ def test_04_count(self):
        #~ assert TestFeed.FeedCount() == 2
        #~ assert TestFeed.FeedCount('unread') == 2
        #~ assert TestFeed.FeedCount('favorites') == 0
        #~ assert TestFeed.FeedCount('removed') == 0
        #~ assert TestFeed.FeedCount('newest') == 2
        
    def test_10_getImage(self):
        TestFeed.FeedGetImage()

if __name__ == "__main__":
    FHLOGGER = logging.getLogger()
    fmt_string = "[%(levelname)-7s]%(asctime)s.%(msecs)-3d\
    %(module)s[%(lineno)-3d]/%(funcName)-10s  %(message)-8s "
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt_string, "%H:%M:%S"))
    FHLOGGER.addHandler(handler)
    FHLOGGER.setLevel(logging.INFO)
    unittest.main()
