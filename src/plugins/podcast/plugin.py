import feedparser
import logging
import StringIO
import traceback
import calendar
import time
import hashlib
import urllib
import base64
import os
import tempfile
import subprocess
log = logging.getLogger('podcast_plugin')

__author__ = 'merlink'
__program__ = 'feedhamster'
__pluginname__ = 'podcast'
__version__ = 0.01
__description__ = 'A Podcast Plugin for FeedHamster'


class Plugin(object):
    
    def __init__(self,url,user=None,passwd=None):

        self.type = __pluginname__
        log.debug('Init Podcast Reader (v%s)'%__version__)
        self.newsdict = {}
        self.count = None
        self.encoding = None
        self.image = None
        self.imageextension = None
        self.uuidlist = []
        self.url = url
        self.tempfiles = []

    def syncMeta(self):

        try:
            feeddata = feedparser.parse(self.url)
            if feeddata.entries == []:
                return False
        except:
            return False
        
        if not self.encoding:
            self.encoding = feeddata.encoding
            
        self.uuidlist = []
        self.count = len(feeddata.entries)
        if not self.image:
            try:
                log.debug('Get Image')
                path = self.feeddata.feed.image.split('?')[0]
                img = urllib.urlopen(path)
                imgdata = img.read()
                img.close()
                self.image = base64.b64encode(imgdata)
                self.imageextension = os.path.splitext(path)[1].replace('.','')
                log.debug('OK')
            except:
                log.debug('Cant get a Picture for this Feed')
                self.image = -1
                self.imageextension = -1
                
        log.debug('Got %s News'%len(feeddata.entries))

        for info in feeddata.entries:
            urls = info['links']
            #log.debug('Urls: %s'%urls)
            url = None
            for entry in urls:
                if 'audio' in entry['type'] or 'video' in entry['type']:
                    log.debug('Found correct type')
                    url = entry['href']
                    break
            if not url:
                continue
            
			#Bugfix: Same file on differnt servers in background
            if '?' in  url:
                url = url.split('?')[0]
            log.debug('Got URL: %s'%url)

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
            news['mimetype'] = entry['type']
            self.newsdict[newsuuid] = news

        return True

    def getList(self):
        log.debug('Getlist: Len=%s'%len(self.uuidlist))
        return self.uuidlist
        
    def getMeta(self,newsuuid):
        return self.newsdict[newsuuid]
        
    def getData(self,newsuuid):
        log.debug('Getdata: %s'%newsuuid)
        newsmeta = self.newsdict[newsuuid]
        url = newsmeta['url']
        
        feed_data = None
        data = None
        log.debug('open %s'%url)
        count = 0
        while count < 2:
            count += 1
            try:
                feed_obj = urllib.urlopen(url)
                data = base64.b64encode(feed_obj.read())
            except:
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                tmp.write('\n'+url)
                tmp.seek(0, 0)
                log.debug(tmp.read())
                tmp.close()

        if data:
            newsmeta['encoding'] = os.path.splitext(url)[1].replace('.','')
            newsmeta['data'] = data
            return newsmeta
        else:
            return None

    def decryptData(self,data):
        log.info('Decrypting Podcast')
        return base64.b64decode(data)
        


