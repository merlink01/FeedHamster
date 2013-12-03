import unittest
import plugin
import time

testurl = 'http://heise.de.feedsportal.com/c/35207/f/653902/index.rss'
timeout = 10 #in seconds

class TestSettings(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        global TestPlugin
        x = plugin.__author__
        x = plugin.__program__
        x = plugin.__pluginname__
        x = plugin.__version__
        x = plugin.__description__
        assert plugin.__program__ == 'feedhamster'
        
        TestPlugin = plugin.Plugin(testurl)
        
        starttime = time.time()
        while 1:
            if TestPlugin.syncMeta() == True:
                if len(TestPlugin.getList()) > 0:
                    break
                
            timediff = time.time() - starttime
            if timediff > timeout:
                raise IOError, 'Timeout for sync reached'
        
    @classmethod
    def tearDownClass(cls):
        TestPlugin.__del__()

    def test_1_getmeta(self):
        entries = TestPlugin.getList()
        meta = TestPlugin.getMeta(entries[0])
        assert 'uuid' in meta
        assert 'url' in meta
        assert 'title' in meta
        assert 'summary' in meta
        assert 'ctime' in meta
        assert 'utime' in meta
        assert 'rtime' in meta
        assert 'mimetype' in meta
        
    def test_2_getdata(self):
        entries = TestPlugin.getList()
        data = TestPlugin.getData(entries[0])
        assert 'encoding' in data
        assert 'data' in data


if __name__ == "__main__":
    unittest.main()
