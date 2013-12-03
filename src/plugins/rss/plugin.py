import feedparser
import logging
import StringIO
import traceback
import calendar
import time
import hashlib
import urllib2
import tempfile
import webbrowser
import urlparse
import StringIO

__author__ = 'merlink'
__program__ = 'feedhamster'
__pluginname__ = 'rss'
__version__ = 0.04
__description__ = 'A Pluging for parsing RSS Feeds'


class Plugin(object):
    
    def __init__(self,url,user=None,passwd=None):

        self.type = __pluginname__
        self.log = logging.getLogger('plugin_rss')
        self.log.debug('Init RSS Reader (v%s)'%__version__)
        self.newsdict = {}
        self.count = None
        self.encoding = None
        self.image = None
        self.imageextension = None
        self.uuidlist = []
        self.url = url
        self.tempfiles = []
        
    def isOnline(self):
        try:
            feeddata = feedparser.parse(self.url)
            if feeddata.entries == []:
                return False
            return True
        except:
            return False

    def syncMeta(self):

        try:
            feeddata = feedparser.parse(self.url)
            if feeddata.entries == []:
                return False
        except:
            tmp = StringIO.StringIO()
            traceback.print_exc(file=tmp)
            tmp.seek(0, 0)
            self.log.debug(tmp.read())
            tmp.close()
            return False

        if not self.encoding:
            self.encoding = feeddata.encoding

        self.uuidlist = []
        self.count = len(feeddata.entries)
        if not self.image:
            try:
                path = self.feeddata.feed.image.split('?')[0]
                img = urllib.urlopen(path)
                imgdata = img.read()
                img.close()
                self.image = base64.b64encode(imgdata)
                self.imageextension = os.path.splitext(path)[1].replace('.','')
            except:
                self.image = -1
                self.imageextension = -1
                
        self.log.debug('Got %s News'%len(feeddata.entries))
        for info in feeddata.entries:
            urls = info['links']
            for entry in urls:
                if entry['type'] == 'text/html':
                    url = entry['href']
                    break

            #Read Times
            rtime = int(time.time())
            try:
                utime = int(calendar.timegm(info['updated_parsed']))
            except:
                utime = -1
            try:
                ctime = int(calendar.timegm(info['published_parsed']))
            except:
                ctime = -1
                
            newsuuid = str(hashlib.md5('%s%s%s' % (url, ctime, utime)).hexdigest())
            self.uuidlist.append(newsuuid)
            
            if newsuuid in self.newsdict:
                continue

            try:
                summary = info['summary']
            except:
                summary = ''

            news = {}
            news['uuid'] = newsuuid
            news['url'] = url
            news['title'] = info['title']
            news['summary'] = summary
            news['rtime'] = rtime
            news['ctime'] = ctime
            news['utime'] = utime
            news['mimetype'] = 'text/html'
            self.newsdict[newsuuid] = news

        return True

    def getList(self):
        self.log.debug('Getlist: Len=%s'%len(self.uuidlist))
        return self.uuidlist
        
    def getMeta(self,newsuuid):
        return self.newsdict[newsuuid]
        
    def getData(self,newsuuid):
        newsmeta = self.newsdict[newsuuid]
        url = newsmeta['url']
        
        feed_data = None
        data = None
        
        try:
            opener = urllib2.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0'),('Referer',urlparse.urlparse(self.url)[2])]
            feed_obj = opener.open(url)
            feed_data = feed_obj.read()
        except:
            try:
                opener = urllib2.build_opener()
                opener.addheaders = [('Referer',urlparse.urlparse(self.url)[2])]
                feed_obj = opener.open(url)
                feed_data = feed_obj.read()
            except:
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                tmp.write('\n'+url)
                tmp.seek(0, 0)
                self.log.debug(tmp.read())
                tmp.close()
                
        if not feed_data:
            return None
        
        try:
            data = feed_data.decode(self.encoding)
        except:
            pass
            
        if not data:
            try:
                data = feed_data.decode(feed_obj.headers.getparam('charset'))
                self.encoding = feed_obj.headers.getparam('charset')
            except:
                pass
                
        if not data:
            try:
                guessing = chardet.detect(feed_data)
                encoding = guessing['encoding']
                data = feed_data.decode(encoding)
                self.encoding = encoding
            except:
                pass

        if data:
            newsmeta['encoding'] = self.encoding
            newsmeta['data'] = data
            return newsmeta
        else:
            return None

    def __del__(self):
        for entry in self.tempfiles:
            try:
                entry.close()
            except:
                pass
            
        
