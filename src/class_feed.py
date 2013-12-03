#html2text
import html2text
if float(html2text.__version__) < float(3.1):
    print 'html2text Version > 3.0 is required'
    sys.exit(1)
html2text.IGNORE_ANCHORS = True
html2text.IGNORE_IMAGES = True

import logging
import os
import sys
import time
import socket
import urlparse
import urllib
import hashlib
import threading
import class_sqlWorker
import StringIO
import traceback
import tempfile
import webbrowser
import class_mimetypes
import FilterHTML


class Feed:

    """Feed Object:
    This object represents both:
    An online RSS Feed and a Local Sqlite Database
    The Sync downloads all Metadata and HTML Code into the Database
    All Feeds could then be viewed offline.
    #url       : Feed url
    #path      : Path of the local DB
    #timeout   : Socket timeout in seconds for downloading
    #maxthreads: Thread count used while syncing
    """

    def __init__(self, plugin, settings):
        self.log = logging.getLogger('feed')
        
        self.settings = settings
        self.plugin = plugin

        socket.setdefaulttimeout(self.settings['download_timeout'])
        self.mimetypes = class_mimetypes.MimeTypesWrapper()

        self.tempfiles = []
        self.settingsCache = {}
        self.status = None
        self.shutdown = False
        
        #URL and feedID
        self.url = self.plugin.url
        parsed = urlparse.urlparse(self.url)
        hashstring1 = parsed.netloc + parsed.path + parsed.params
        hashstring2 = parsed.query + parsed.fragment
        hashvalue = hashlib.md5(str(hashstring1+hashstring2)).hexdigest()
        if parsed.netloc == '':
            preName = self.url 
        else:
            preName = parsed.netloc
        self.feed_id = '%s-%s' % (preName, hashvalue)

        self.log.debug('Starting with url:%s ,timeout:%s seconds' % (self.url, self.settings['download_timeout']))

        self.db_path = os.path.join(self.settings['workingdir'], self.feed_id + '.hdb')
        self.db = class_sqlWorker.sqlWorkerThread(self.db_path,settings['tempdir'])
        self.db.start() 
            
    def feed_initiate(self):

        """Create a new DB with all
        data needed"""
        
        if not self.plugin.syncMeta():
            self.log.warning('Access of URL not possible (syncmeta)')
            return False

        #Create Database
        sql = "CREATE TABLE IF NOT EXISTS settings (setting TEXT, value TEXT)"
        self.db.executeCommand('put',sql)
        sql = "CREATE TABLE IF NOT EXISTS feeds\
        (uuid TEXT, title TEXT, summary TEXT, created INTEGER,\
        updated INTEGER ,recieved INTEGER, read INTEGER, favorite INTEGER,\
        mimetype TEXT, removed INTEGER, encoding TEXT, url TEXT, data TEXT)"
        self.db.executeCommand('get',sql)

        self._write_setting('version', self.settings['version'])
        self._write_setting('id', self.feed_id)
        self._write_setting('name', self.url)
        self._write_setting('url', self.url)
        self._write_setting('genre', '')
        self._write_setting('last_search', int(time.time()))
        self._write_setting('last_compacted', int(time.time()))
        self._write_setting('last_synced', int(time.time()))
        self._write_setting('import_date', int(time.time()))
        self._write_setting('image', -1)
        self._write_setting('image_ext', -1)
        self._write_setting('max_size', 1024*1024*4000)
        self._write_setting('tso', 0)
        self._write_setting('teo', 0)
        self._write_setting('feedcount',100)
        self._write_setting('plugin',self.plugin.type)

        return True
        
    def message_delete(self, fuuid, complete=False):
        
        self.log.info('Deleting Message: %s'%fuuid)
        if complete:
            sql = "DELETE FROM feeds WHERE uuid=?"
        else:
            sql = "UPDATE feeds SET removed='1' AND data='-1' WHERE uuid=?"
        self.db.executeCommand('put',sql,(fuuid,))
        self.db.executeCommand('commit')

        self.log.info('Done')
        
    def _count_threads(self,name):

        """This function counts running Threads"""

        thcount = 0
        threads = threading.enumerate()
        for th in threads:
            if th.getName() == name:
                if th.is_alive():
                    thcount += 1
        return thcount

        
    def _write_setting(self, name, value, overwrite=False):

        """Helper function for fast writing Settings to DB"""
        
        self.log.debug('SaveSetting %s.../%s: %s'%(self.feed_id[:12],name,value))
        
        #Delete entry from settings cache
        if name in self.settingsCache:
            del self.settingsCache[name]
            
        sql = "SELECT COUNT(*) FROM settings WHERE setting=?"
        if self.db.executeCommand('get',sql,(name,))[0][0] == 0:
            sql = "INSERT INTO settings (value,setting) VALUES (?,?)"
            self.db.executeCommand('put',sql, (value,name))
            self.db.executeCommand('commit')
            assert str(self._read_setting(name)) == str(value), '%s-%s'%(self._read_setting(name),value)

        else:
            if overwrite:
                sql = "UPDATE settings SET value=? where setting=?"
                self.db.executeCommand('put',sql, (value,name))
                self.db.executeCommand('commit')

    def _read_setting(self, name):

        """Helper function for fast reading Settings from DB"""


        #Create a settings Cache for speeding up requests
        if name in self.settingsCache:
            return self.settingsCache[name]
        
        sql = "SELECT value FROM settings WHERE setting=?"
        answer = self.db.executeCommand('get',sql, (name,))[0][0]
        self.settingsCache[name] = answer
        return answer

    def feed_count(self, meta='all'):

        """Count of News with meta:
        Usage: Feed.count('unread')
        Returns the count of all unread News
        """

        if meta == 'all':
            sql = "SELECT COUNT(*) FROM feeds  WHERE removed=0"
            return int(self.db.executeCommand('get',sql)[0][0])
        elif meta == 'unread':
            sql = "SELECT COUNT(*) FROM feeds WHERE removed=0 and read='0'"
            return int(self.db.executeCommand('get',sql)[0][0])
        elif meta == 'favorites':
            sql = "SELECT COUNT(*) FROM feeds WHERE removed=0 and favorite='1'"
            return int(self.db.executeCommand('get',sql)[0][0])
        elif meta == 'removed':
            sql = "SELECT COUNT(*) FROM feeds WHERE removed='1'"
            return int(self.db.executeCommand('get',sql)[0][0])
        elif meta == 'newest':
            return len(self.feed_get_newest())
        else:
            self.log.error('Meta %s does not exists' % meta)

    def feed_is_online(self):
        if 'isOnline' in dir(self.plugin):
            online = self.plugin.isOnline()
            self.log.debug('Online: %s'%online)
            return online

        urllist = ['http://www.google.com','http://www.adobe.com','http://www.apple.com']
        for entry in urllist:
            try:
                urllib.urlopen(entry)
                self.log.debug('Online: True')
                return True
            except:
                self.log.debug('Online: False')
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                tmp.seek(0, 0)
                self.log.debug(tmp.read())
                tmp.close()
                
        return False

    def feed_download(self):
        if not self.feed_is_online():
            return False
        
        if self.status == None:
            self.status = 'syncing'
        else:
            self.log.debug('Feed cant sync, %s already'%self.status)
            return False

        self.log.debug('Start MetaSync of: %s'%self.url)
        output = self.plugin.syncMeta()
        
        self.log.debug('MetaSync Returns: %s'%output)

        if self.plugin.count:
            self._write_setting('feedcount',self.plugin.count,True)

        if self.plugin.image:
            self._write_setting('image', self.plugin.image, True)
            self._write_setting('image_ext', self.plugin.imageextension, True)

        newslist = self.plugin.getList()
        self.log.debug('Got %s News'%len(newslist))
        self.sync_counter = 0
        for newsuuid in newslist:
            if self.shutdown:
                return False
            
            self.log.debug('Checking: %s'%newsuuid)

            if self.status == 'stopping':
                self.log.debug('Stopping Sync')
                self.status = None
                return False

            #check if feed exists already
            sql = """SELECT COUNT(*) FROM feeds WHERE uuid=?"""
            if self.db.executeCommand('get',sql, (newsuuid,))[0][0] > 0:
                self.log.debug('UUID: %s already exists'%newsuuid)
                if 'gotDataAlready' in dir(self.plugin):
                    self.plugin.gotDataAlready(newsuuid)
                continue

            newsmeta = self.plugin.getMeta(newsuuid)
            assert type(newsmeta) == dict
            #check if feed exists already but not up to date
            sql = """SELECT uuid FROM feeds WHERE url=?"""
            data = self.db.executeCommand('get',sql, (newsmeta['url'],))

            favorite = 0
            if data != []:
                uuid = data[0][0]
                
                if self.message_get_meta(uuid)['favorite']:
                    self.log.info('Info: Overtake Favorite for feed: %s'%uuid)
                    favorite = 1
                self.log.debug('Delete: %s' % uuid)
                self.message_set_meta(uuid, 'removed', True)

            data = self.plugin.getData(newsuuid)

            counter = 0
            while not data:
                time.sleep(0.1)
                counter += 1
                data = self.plugin.getData(newsuuid)

                if counter > 5:
                    break

            if not data:
                self.log.debug('Error Downloading: %s'%newsuuid)
                continue
            self.log.debug('Download: %s/%s'%(self.feed_id,newsuuid))
            sql = "INSERT INTO feeds \
            (uuid,title,summary,created,updated,recieved,read,removed,favorite,\
            mimetype,encoding,url,data) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"

            self.db.executeCommand('put',sql, (data['uuid'], data['title'], data['summary'], data['ctime'],
                              data['utime'],data['rtime'], 0, 0, favorite,
                              data['mimetype'],data['encoding'], data['url'], data['data']))
            del data
        
        self._write_setting('last_synced', int(time.time()), True)
        self.log.debug('Syncing Done')
        self.status = None
        return True

    def message_set_meta(self, uuid, metaname, value):

        """Change Information of a Message in DB:
        Normally only to set a message read or favorite
        """

        if metaname == 'title':
            sql = "UPDATE feeds SET title=? where uuid=?"
            self.db.executeCommand('put',sql, (value, uuid))
            return

        if metaname == 'summary':
            sql = "UPDATE feeds SET summary=? where uuid=?"
            self.db.put(sql, (value, uuid))
            return

        # only bool values from here
        if type(value) == bool:
            if value:
                value = 1
            else:
                value = 0

        if metaname == 'favorite':
            sql = "UPDATE feeds SET favorite=? where uuid=?"
            self.db.executeCommand('put',sql, (value, uuid))
            return

        if metaname == 'read':
            sql = "UPDATE feeds SET read=? where uuid=?"
            self.db.executeCommand('put',sql, (value, uuid))
            return

        if metaname == 'removed':
            sql = "UPDATE feeds SET removed=? where uuid=?"
            self.db.executeCommand('put',sql, (value, uuid))
            return

        self.log.error('Metaname %s does not exist' % metaname)

    def feed_set_all_read(self):
        sql = "UPDATE feeds SET read='1'"
        self.db.executeCommand('put',sql)
        
    def feed_compact(self):
        
        """Compact the Database File"""
        
        if self.db.compact():
            self.log.info('Compacted successfull')
            return True
        else:
            self.log.info('Error while compacting, maybe freespace in Temp is not enough.')
            return False
            
    def feed_cleanup(self):
        
        """Cleanup the Database File"""
        
        max_size = int(self._read_setting('max_size'))
        
        if max_size < self.feed_get_size():
            self.log.debug('Filesize too high: %s Compacting.'%(self._convert_space_human_readable(self.feed_get_size() - max_size)))

            result = self.feed_compact()
            if result == False:
                return
            
            if max_size >= self.feed_get_size():
                self.log.debug('Done')
                return
                
            sql = 'SELECT uuid FROM feeds WHERE favorite=0 ORDER BY recieved'
            messages_by_date = self.db.executeCommand('get',sql)

            oversize = self.feed_get_size() - max_size
            counter = 0
            
            while oversize > 0:
                oversize -= len(self.message_get_data(messages_by_date[counter][0],raw=True))
                self.message_delete(messages_by_date[counter][0],True)
                counter += 1
                self.log.info('Calculated oversize: %s'%oversize)
            
            self.feed_compact()
            self.log.info('New Size: %s'%(self._convert_space_human_readable(self.feed_get_size() - max_size)))
            
            self.log.debug('Cleanup Done')
                
        else:
            self.log.debug('Cleanup not necessary, Filesize is OK')

    def _convert_space_human_readable(self,space):
        for x in ['bytes','KB','MB','GB','TB']:
            if space < 1024.0:
                return "%3.1f %s" % (space, x)
            space /= 1024.0

    def feed_get_size(self, humanReadable = False):
        
        if humanReadable:
            return self._convert_space_human_readable(os.path.getsize(self.db_path))
        else:
            return os.path.getsize(self.db_path)
        
    def feed_get_image(self):
        data = self._read_setting('image')
        if data == '-1':
            pic = """iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAABm
                JLR0QAAAAAAAD5Q7t/AAAACXBIWXMAAA3WAAAN1gGQb3mcAAAA
                CXZwQWcAAABAAAAAQADq8/hgAAAORklEQVR42u2aS48lR1bHfy
                ciX/dVtx632+5u2wwej0Cy5bFsCUZGRrCwvPWOb4C85CPwAViw
                GRaoMWskRuyMvBo2ICON5ZYHaTRCw8Pudj9U1V1Vt+o+8mbGYR
                GZNyPvo6ra08Ia6JBSN/NkvP4nTpz/iZMXnpfn5Xl5Xv4fF9ki
                t9VlvusJPsPigLK61hWgqty6dWvw0UcfvfvDt374o8FgcCuO4s
                FlvSq6QbhBqltq6xV6VF2vqo1E1+pKuz+FoliMx2dn937+5c8/
                u3379r/cu3dvLCJEAB988AGj0Wjw47/68Z+99957fzocDl+01l
                rxZTt41SvJNivkKWWqUM+lVogqCCgCqkgwvkpb5lS1LMvy7bff
                fvDaa6/99Wg0+sv3339/bG/evMkXX3zBPJ//8Ycffvjno9HoZW
                OMuRB5OFAAeJMsBKDfVhaucgu8oIBcJKuaiYgYY0y309kZjUav
                JUly5+OPP/6VqV7aN99880fD4fDGxhW8AHytp02yFgARb5gh0E
                tkIeBvA761dVR9/6oMdnZuvPHGG78vIlHt5OxgMLhlrY2eOfjq
                99uAv/IqbwGvK1umHstaG/UHg1uArRVg4jgeXGL1W4FeCP5brv
                yzAq+VHwhlIkIcxX3ALGlOEK7i8LYB5TcEfLPFVQC2mryqYkSw
                RvBU4n+b0CCUSdBuu0xDenpKGUjgCJ9GBqVrFN7yLxcpwIjwnw
                +O+cd/e0SBZQNhL0UB1FYtWa14WdGVDjc0k+CF0q6+qa9IC95/
                /To3DgZLR0hg6VsVIAK/enTGX/yiy7RzDZFmXYSmDwnqb3sv1c
                1V6q4CMtK+D/tq1V+VVcLs9B5v3JpyczTw+Ks6tfIu9PpihLTb
                RXsDBN048adVwGXvANIIdlPvog8yb9InczicKIVrxrpsPiAkRR
                eR+cbVv1QBALEozuhyJa4EYsNqbHpu3/s1sSL87j68sgMHHaEb
                w/EMxrly/wwenMOsgIUDp+qd95b5+PnTOFcJRtILFKCBw0gMYC
                8HcCVL2Kg0r9zICJHAqAvfG0IWCVnkXe5O6p+HKdwaKOM5jHN4
                eC5MFrpmXQYfHot4ngtNvmEx3ayAMBIUIDaAYc0CuMKqts1x1U
                wVg9CJhVEXRh3YSaAbV0oXmC3aFpsY2EsFCyQWurHyZCqUCpHA
                vPTbJrPeaoqatKTBdiEL6Aq/UinA2G3AtQ244vOLTd2velqt6F
                7mwcfVGIXzl4QUsGJViYXIeMvYzzzNpZH/nRWQl5BFcJbDxKyw
                xTYWqAksDHRqC7CBAhpASicSDjp+4NPcD147S4K9ue6ohN0U+o
                kHkzu/pwn6XwUdWmW4nRC/6l5pHriqUhphkEJhA+BB0LWVBdrR
                oBIbUFMP3Ow3K8IP9uBGX1BVzhdwdwwnc6GsHVRgEaH1WPGKLU
                olF3BlAFQ2b51QAUgTjq3TseBUcJVCUstmJ7hNAbUV1JViA2J9
                s0iEqFJGL/ZUVTg/fCeC7+8q89JbwulcOJ4pTkMrEEQUAzgnKM
                JUN/iXysJqmRFIIyGtTH9RwqTwkeiahVU3NefXscOaE9zGApuc
                YGShGwt7mXdS9aQUIS/DCQixgSSBfqx0Y+Es95Mpnc9J9WI/+L
                TwPOOcj1jDtTECBsGKN+mDrr86kWeL0in/dSw8OvfZnrafEUQb
                S7Mr2K7mBAMN9BPY7/vBbaXKWqOLUtf2aWiSgxj61Qil8165E/
                m25wuYLpRSm5WLjNCvmCCN/NWJYJBWlBhY0qt7yqKUFlPocoXr
                wx0Ups4aXeIEa9ShEzQIg1RIK8dSaNvc1hyVgAThfKiMLBYy66
                mqcMpO4p+94/SObDeDvY63tqii3hp0WVbZzKrPNILv7cK8aMaZ
                FzBdCLPC+yAQctPSzvZIcLnrgwoi/lBUOm9WSBN5hdtkqQRlLd
                iJjZJYH9H1Eu8wz/KKYoMzlkgQ/FR72KnfNqGCm3F9n524ETv1
                VjkrYLYQFg7mRpvQrz46Byu+zgLLPeIn6xZz3PwciTJEDIg/rk
                rdRwA45FvFBye92INKLFjxUd9u6idrZGVsURblditrbTXaY9e/
                kYF+DN0IFgrjqJlZmH9Y3wJLU/C24LGVlA+/YPLgnOSFt0hHr2
                M8JbQiuobuggOTKhYoS6VAWSzUU1NlVcZAbA3WBBa11Or6Ftpk
                cWyoE7aLqkhzNYEjW/MBKxkeUQf5EWUxZn73n2F2RLb3KibqoC
                5nMTmknJ8SZUOi7nVyukxyQ14orixxzqHOUZT+cpUX9ikpYacb
                s9dLGfZjumlEbAVj2lss3CLbzhirilhajoARbUGUi/IBm0zET8
                egxYzZwzvMD3+BiEXVoWWOaomIRWxKbgZMOGBqrpPbfZCoCaA2
                mPPp2YJvZEocG/pZRL8T0+9EDLKYbmZJY0tUKUQVVPz5oYZkas
                S1yYYaqben8y9Xk93rkaC22zUm5kdw6gnbMEcr/1CPqOrQYkrM
                hCGP6Mt/MI9eYBq9TG4PUElAwqnXNOX7LhaO48WcJ+M5RoTYCn
                FkGPZiXtztcH2YkiUWEWEyK7h7NKEolSw2DDox/Swiiw1J1M5r
                Gqmou0Z2FRYIO1BXcvL4LqcnX1MWc0QMSdqjNxiRdXcxxjad18
                anitU53cVXZMV9CjuksPsUdkhp+qjp4ogoZ08opg+JOtexnWtg
                4uXedA7mecmjvOToZM69XszN/YydbsxXjybcezwBBWOEyHqFDT
                oxe72Y/X7CwSChk3j/EpuGmlssoFtYgOClcwseP/x3xuP7gWKE
                J4f/zc7ui+xf/z5J2mvbTKhhN8cW3yDua4xzlCUUpWM+m3N+cp
                dieoRJdkj2Xie79jZZ7xoppyAWJxlqMlRTTscx4/MZ1kaUTolM
                uEiO3MFRXnJ0OiOyhkFmubmX8dvXe/44f8EWv5AFavIQEU+BVC
                etIufJ4VfMJiccvPADejvXEBHv8IqcfHbGbHbKfHrKIp9QLLyv
                UPVO0bliqcxyOmU6fcj80b8y7x0wHO7RG1wnSnogFhWLmg7O9F
                Hbx1r/q6YDEoHE3mEv97BjPHH8crrg0cmcF2yODNvYrs4CtQpc
                law2zRZRVaaTE+5//SW9wTWMtRT5jHx+RlHkuLJotkYrgKn7CL
                IDqrhiwuTknOn4HmnapzcY0R2MyDo7WHuGNUdVm1opCdg+zg7R
                aA+NhmAyMHG1wsqT8wXzYo57KWoSoldmAQF1yuQ45/yJAwQTCV
                GiRKlgouroWeacPrnb7Bxts7YrwJWVfzGe/8VWpz2pkigSKsMx
                m54ym55yfPQVcdIj7QxIsz5JNiDNelibYGyElGcYHlSWkqLRDh
                rt4eIRGu2CSTF1TgxdA99WQG1BwRn+5HTC9CynXPgK5UIppoKJ
                lLgj2FhR552WOn+u19KhjiU9OUdAUVWgJF4JxgrGKiaq7wFTvR
                fBuYLZ9ITZ9NgvgI2wNiZOuqSdAUnaJ046xHGGjVNMfoyYe0Qm
                hXjIwl7j0eMZJ7/1CsIIDQ5F2xMiy6UUnownLIqy8m2N6ZcFuL
                NKm9o+Ql9YtBmYotG6twL1uUdbXxIoRhADrizQsqDIJ0zODhER
                jLGIsV4xcYcoTjE2whiLMRGzxZDT89EyR7C08K0sUDvB1YAgyP
                8ti9sg+1bFW5I6wbuOdlgnpto+kWBii0mi5eczH5PUU5/idEbp
                DE4NpbM4NRR/FHwj5KpOEP9Nb1EYRAVXJaFkGauH3+1bKgq7az
                /70wKlWkoXUail1AiHn6j/tSimqmvWLicxGOsVID5KpXaqErYR
                VA2dJKqeL3WCusaTpTM8nBxQFjtQdWJEq7SWq9JWshywOg6hVS
                66kRtUpALoAft3FhUTgKiSABIu/ab7y94H9zH+WS9xgs1H4+Yw
                ogiTckhRJ/YqMD6HFaQ7xTQTa90HK7R2/7T1V9tuG9O0lRS5Sr
                Z5r17gBNU3zHZ9VuJpJ7d15X5dgCt1xTRUWgVs4XNii2UQ56H5
                wK52Axud4PJXLHR2wdlff6IXKqkNRKp34bP3+P7ZiHinKKaRGa
                nyDKZVJyPHWtPKdOtWJxhUUMTzUbYHGl1pJep3srISEgJcTtTX
                MRIAWAI0S0ASADMr7VuAW/02fURuirVFy8mHG2EzCyz9gUU6e4
                gkLTA1wLb2V1ZpZeKN3LQAhCt5eb1NiljtP7QMgyzOMObxFVhg
                5T87Ctzc7/J7L0cstHbOQSRHGSiD5pfgObyvL1hp08jY1F+rn6
                p/I9vHoaqj/rJ2wV438Xv/0v8HBN/OXOn4wzde4q1XRyvZlJVv
                B9p6Ch7bMgkabOiuXXstxGjLWr1sqhsUAfqdpArsLsgK+5hFmo
                +IQBJbRsNeEDxvAb82v6eTbVNAM86Kgq8ga6ZXR7b1J7EL8gFL
                M6kb1hpz7c/mYTj5LP++dpGs7q8Vzj6FzFNfwHCVfmqCdHmenz
                vnngnQ5lvV/w54LgG/nGsN1jnyPD8HXK2A8vjJk/tlsTz6fWer
                vKq4q6wyVwRf/5ZlWR4fnzwAClO9KH/2s88/Pzw6Olr+OWLDv0
                WeCXh4tiYeLNhlK1+zzuPHj4/u3Pnic1Ut7Xg85tNPP+WffvrT
                w/2D/ZdeePHFVzudTmqMwRgjYkyLkhChlpmgU+p6sAxuNsoC6q
                tlYqrIr+rPPI1shUpNML8adKUILYpCHzx4cPzJJ5/8w+3bf/O3
                P/nJ30+brLkqN27c+J13/+DdP3nnnXfevDa6dpBlWbb8FrqJBd
                Ye2oILqfKStu1m2+RXbq+z2Xx2eHh4dOfOnS8/++yzv7t///4v
                a8UBYIzBOUeapiNr7SvAQETS2sp+c0v9XYk5MC7L8qvZbHZora
                Usyza4mzdvhq2CP5j9nyiKP9cqwDfffPNdz+d5eV6el+fluy//
                A9J8gKxqPpzYAAAAJXRFWHRkYXRlOmNyZWF0ZQAyMDEwLTA1LT
                I0VDA3OjQyOjMwLTA2OjAw8BwQ8AAAACV0RVh0ZGF0ZTptb2Rp
                ZnkAMjAxMC0wNS0yNFQwNzo0MjozMC0wNjowMIFBqEwAAAA1dE
                VYdExpY2Vuc2UAaHR0cDovL2NyZWF0aXZlY29tbW9ucy5vcmcv
                bGljZW5zZXMvTEdQTC8yLjEvO8G0GAAAABl0RVh0U29mdHdhcm
                UAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAAPdEVYdFNvdXJjZQBu
                dW92ZVhUMuogNtwAAAAidEVYdFNvdXJjZV9VUkwAaHR0cDovL2
                51b3ZleHQucHdzcC5uZXSRicctAAAAAElFTkSuQmCC"""
        else:
            pic = data
        
        return pic

    def message_get_meta(self, uuid):

        """Extract Metadata for a Message"""

        self.log.debug('Get Meta of: %s'%uuid)

        sql = """SELECT title, summary, created, updated,recieved,\
        url ,favorite, read, removed, encoding, mimetype FROM feeds WHERE uuid=?"""


        data = self.db.executeCommand('get',sql,(uuid,))
        data = data[0]
        
        out = {'uuid': self.feed_id,
                'title':    data[0],
               'summary':  '%s\n%s'%(data[5],html2text.html2text(data[1]).replace('\r','\n')),
               'created':  float(data[2]),
               'updated':  float(data[3]),               
               'recieved':  float(data[4]),
               'url':      data[5],
               'favorite': bool(data[6]),
               'read':     bool(data[7]),
               'removed':  bool(data[8]),
               'encoding': data[9],
               'mimetype': data[10]}
        return out


    def message_get_data(self, uuid, text=False,raw=False, encoding='auto'):

        """Return the HTML Code of the Feed"""

        self.log.debug('Extracting data for: %s, Text:%s' % (uuid,text))
        sql = """SELECT data,encoding FROM feeds WHERE uuid=?"""
        answer = self.db.executeCommand('get',sql, (uuid,))
        data = answer[0][0]
        
        if raw:
            return data
            
        if text == True:
            try:
                data = html2text.html2text(data).replace('\r','\n')
            except:
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                tmp.seek(0, 0)
                self.log.error(tmp.read())
                tmp.close()
                return
                
            linelist = data.split('\n')
            startline = int(self._read_setting('tso'))
            endline = len(linelist) - int(self._read_setting('teo'))
            counter = 0
            outtext = 'Path: %s/%s\n \n '%(self.feed_id,uuid)
            for line in linelist:
                counter += 1
                if counter >= startline:
                    outtext += line + '\n'
                if counter > endline:
                    break

            return outtext
        else:
            if 'decryptData' in dir(self.plugin):
                return self.plugin.decryptData(data)
            else:
                return data.decode(answer[0][1])

    def message_open(self, muuid, online=False):

        """Extracts the HTML Site to a Temp File and
        Shows it in Webbrowser.
        The Message is set read.
        Temp Files are deleted in __del__ function.
        """
        
        self.log.info('Open: %s'%muuid)
        if online:
            url = self.message_get_meta(muuid)['url']
            webbrowser.open_new_tab(url)
        else:
            mime = self.message_get_meta(muuid)['mimetype']
            extension = self.mimetypes.get_extension(mime)

            tmp = tempfile.NamedTemporaryFile(suffix=extension[0])
            self.tempfiles.append(tmp)
            
            if extension[0] == '.html':
                #~ result = FilterHTML.filter_html(self.message_get_data(muuid), SPEC)
                meta = self.message_get_meta(muuid)
                data = self.message_get_data(muuid).encode(meta['encoding'])
                tmp.write(data)
                webbrowser.open_new_tab(tmp.name)
            else:

                import subprocess
                data = self.message_get_data(muuid)
                tmp.write(data)
                #~ try:
                    #~ data = self.plugin.decryptData(data)
                #~ except:
                    #~ pass
                subprocess.Popen(['vlc',tmp.name])
                
        self.message_set_meta(muuid, 'read', True)

    def feed_set_newest_time_flag(self,setTime=None):
        
        self.log.debug('(%s) Set: %s'%(self.feed_id,setTime))
        if setTime:
            self._write_setting('last_search',setTime,True)
        else:
            self._write_setting('last_search',int(time.time()),True)

    def feed_get_newest(self,count=-1):
        
        last_time = self._read_setting('last_search')
            
        sql = 'SELECT uuid FROM feeds WHERE removed=0 AND recieved>? ORDER BY updated DESC'
        answer = self.db.executeCommand('get',sql,(last_time,))

        self.log.debug('Got: %s '%len(answer))
        out = []
        counter = 0

        for entry in answer:
            if count > 0:
                if counter >= count:
                    break
            counter += 1
            out.append(entry[0])
            
        return out
        
    def feed_search(self, keyword=None, unread=False,
                favorites=False, startTime=-1,endTime=-1,
                count=-1, created=False, fullText=False):

        """Feed Search engine:
        Returns a list of message IDs matching the criterias
        #-keyword:        Search for news including this string
        #                None: No String search is performed
        #-unread:        Return unread messages only
        #-favorite:      Return Favorites only
        #-timestamp:     Return Messages updated later than given timestamp
        #-count:         Return only "count" Messages
        """
        
        options = ''
        if unread:
            options += 'AND read=0 '
            
        if favorites:
            options += 'AND favorite=1 '
            
        if created:
            if startTime > 0:
                options += """AND created>"%s" """ % startTime
                
            if endTime > 0:
                options += """AND created<"%s" """ % endTime
        else:
            if startTime > 0:
                options += """AND updated>"%s" """ % startTime
                
            if endTime > 0:
                options += """AND updated<"%s" """ % endTime
            
        if keyword:
            if fullText:
                sql = """SELECT uuid FROM feeds WHERE title LIKE '%s' %s\
                or summary LIKE '%s' %s or data LIKE '%s' %s AND\
                removed=0 """ % ('%' + keyword + '%',options, '%' + keyword + '%', options, '%' + keyword + '%', options)
            else:
                sql = """SELECT uuid FROM feeds WHERE title LIKE '%s' %s\
                or summary LIKE '%s' %s AND removed=0 """ % ('%' + keyword + '%',options, '%' + keyword + '%', options)
        else:
            sql = "SELECT uuid FROM feeds WHERE removed=0 %s"%options

        sql += 'ORDER BY updated DESC'
        self.log.debug(sql)
        answer = self.db.executeCommand('get',sql)
        self.log.debug('Got: %s'%len(answer))
        out = []
        counter = 0

        for entry in answer:
            if count > 0:
                if counter >= count:
                    break
            counter += 1
            out.append(entry[0])
            
        if len(out) == 0 and created == False:
            return self.feed_search(keyword, unread, favorites, startTime, endTime, count, True, fullText)

        return out

    def feed_close(self):
        
        """Cleanup while deleting object"""
        
        self.log.info('Closing: %s'%self.feed_id)
        self.shutdown = True
        
        while self._count_threads('download_thread') > 0:
            self.log.debug('Waiting for Threads: %s'%self._count_threads('download_thread'))
            time.sleep(0.1)
        
        self.db.executeCommand('exit')
        while self.db.getStatus():
            time.sleep(0.1)
            
        for entry in self.tempfiles:
            try:
                entry.close()
            except:
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                tmp.seek(0, 0)
                self.log.debug(tmp.read())
                tmp.close()
                



    def feed_delete(self):
        self.feed_close()
        os.path.remove(self.db_path)
        return True
        
        