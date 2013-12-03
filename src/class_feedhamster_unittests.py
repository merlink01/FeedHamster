import unittest
import logging
import sys
import tempfile
import class_feedhamster
import class_feed


class TestFeedHamster(unittest.TestCase):

    feed_01 = 'http://heise.de.feedsportal.com/c/35207/f/653902/index.rss'
    uuid_01 = 'heise.de.feedsportal.com-c9b5ba28d3aca5d352f13de880952694'

    def test_01_start(self):
        FeedHamster = self.start()
        self.stop(FeedHamster)

    def test_02_add_feed(self):
        FeedHamster = self.start()
        assert len(FeedHamster.list()) == 0
        FeedHamster.add(self.feed_01)
        assert len(FeedHamster.list()) == 1
        self.stop(FeedHamster)

    def test_03_del_feed(self):
        FeedHamster = self.start()
        assert len(FeedHamster.list()) == 0
        FeedHamster.add(self.feed_01)
        assert len(FeedHamster.list()) == 1
        FeedHamster.delete(self.uuid_01)
        assert len(FeedHamster.list()) == 0
        self.stop(FeedHamster)

    def test_04_sync_feed(self):
        FeedHamster = self.start()
        assert len(FeedHamster.list()) == 0
        FeedHamster.add(self.feed_01)
        assert len(FeedHamster.list()) == 1
        FeedHamster.sync()
        time.sleep(0.1)
        while FeedHamster.sync_status is not None:
            time.sleep(1)
        #second time with synced db
        FeedHamster.sync()
        time.sleep(0.1)
        while FeedHamster.sync_status is not None:
            time.sleep(1)
        self.stop(FeedHamster)

    def test_04_compact_feed(self):
        #todo:
        #delete message and check the cleanup
        FeedHamster = self.start()
        assert len(FeedHamster.list()) == 0
        FeedHamster.add(self.feed_01)
        assert len(FeedHamster.list()) == 1
        FeedHamster.compact()
        while FeedHamster.compact_status is not None:
            time.sleep(1)
        self.stop(FeedHamster)

    def test_05_get_feed(self):
        FeedHamster = self.start()
        assert len(FeedHamster.list()) == 0
        FeedHamster.add(self.feed_01)
        assert len(FeedHamster.list()) == 1
        info = FeedHamster.list()
        feedid = info.keys()[0]
        assert FeedHamster.get(feedid).url == self.feed_01
        self.stop(FeedHamster)

    def start(self):
        temppath = tempfile.mkdtemp()
        return class_feedhamster.FeedHamster(temppath)

    def stop(self, FeedHamster):
        temppath = FeedHamster.path
        import shutil
        shutil.rmtree(temppath)
        del FeedHamster


class TestFeed(unittest.TestCase):

    feed_01 = 'http://heise.de.feedsportal.com/c/35207/f/653902/index.rss'
    uuid_01 = 'heise.de.feedsportal.com-c9b5ba28d3aca5d352f13de880952694'

    def test_01_test_search_setmeta(self):
        feedreader = self.start()
        
        assert len(feedreader.list()) == 0
        feedreader.add(self.feed_01)
        assert len(feedreader.list()) == 1
        info = feedreader.list()
        feedid = info.keys()[0]
        feed = feedreader.get(feedid)
        feed.sync()
        assert len(feed.search()) > 0
        assert len(feed.search(unread=True)) == len(feed.search())
        assert len(feed.search(favorites=True)) == 0
        assert len(feed.search(count=3)) == 3,'Got %s of %s'%(feed.search(count=3),feed.search())
        messageid = feed.search()[0]
        feed.setMeta(messageid, 'favorite', True)
        feed.setMeta(messageid, 'read', True)
        assert len(feed.search(unread=True)) == len(feed.search()) - 1
        assert len(feed.search(favorites=True)) == 1
        #try searching
        feed.search('test')
        self.stop(feedreader)

    def start(self):
        temppath = tempfile.mkdtemp()
        return FeedHamster(temppath)

    def stop(self, feedreader):
        temppath = feedreader.path
        feedreader.close()
        import shutil
        shutil.rmtree(temppath)

if __name__ == "__main__":

    x = logging.getLogger()
    fmt_string = "[%(levelname)-7s]%(asctime)s.%(msecs)-3d\
    %(module)s[%(lineno)-3d]/%(funcName)-10s  %(message)-8s "
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt_string, "%H:%M:%S"))
    x.addHandler(handler)
    x.setLevel(logging.WARNING)

    testfeed = "http://heise.de.feedsportal.com/c/35207/f/653902/index.rss"
    temppath = tempfile.mkdtemp()
    feedreader = class_feedhamster.FeedHamster(temppath)

    print 'Testing Feedreader: \nThis could take some time....'
    #~ if feedreader.add(testfeed,'rss'):
        #~ del feedreader
        #~ import shutil
        #~ shutil.rmtree(temppath)
    #~ else:
        #~ print 'You must be online to test this Library'
        #~ sys.exit(0)

    #~ unittest.main()
