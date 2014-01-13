import os
import locale
import logging
import ConfigParser

class Translator(object):
    def __init__(self,path=None):
        self.log = logging.getLogger('translator')

        language = locale.getdefaultlocale()[0]
        self.parser = None
        self.fallback = False
        self.language = language
        self.langlist = []

        if not path:
            self.path = os.path.abspath('lang')
        else:
            self.path = os.path.abspath(path)

        self.langfile = os.path.join(self.path,language + '.lng')
        self.writable = False

        try:
            os.open(self.langfile,'a').close()
            self.writable = True
        except:
            pass

        self.log.info('Laqngfile: %s'%self.langfile)




    def read(self, section, option):
        try:
            parser= ConfigParser.RawConfigParser( )
            parser.read(self.langfile)
            value = parser.get(section, option)
            return value
        except:
            return None

    def write(self, section, option, value):
        #~ if not self.writable:
            #~ return
        self.log.info('writing')
        parser = ConfigParser.RawConfigParser( )
        if os.path.isfile(self.langfile):
            parser.read(self.langfile)
        try:
            parser.add_section(section)
        except:
            pass
        parser.set(section, option, value)
        file_object = open(self.langfile, 'w')
        parser.write(file_object)
        file_object.close()


    def getText(self,header,name,fallback):

        text = self.read(header,name)

        if not text:
            self.log.info('writing: %s %s %s'%(header,name,fallback))
            self.write(header,name,fallback)
            return fallback

        else:
            return text
