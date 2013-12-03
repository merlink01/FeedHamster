import os
import sys
import appdirs
import logging
import ConfigParser
log = logging.getLogger('settings')

class Settings(object):
    def __init__(self, name, portable=False):
        
        filename = '%s.cfg'%name
        if portable:
            path = os.path.abspath(name + '/' + filename)
        else:
            path = appdirs.user_data_dir('',appauthor='') + name + '/' + filename
        path = os.path.abspath(path)
        self._touch(path)
        log.debug('Settingsfile: %s'%path)
        self.path = path

    def _touch(self,path):
        
        try:
            os.makedirs(os.path.dirname(path))
        except:
            pass
        
        log.debug('Touching:%s'%path)
        open(path,'a').close()

    def get_sections(self):
        log.debug('Get Sections')
        parser = ConfigParser.RawConfigParser( )
        parser.read(self.path)
        sections = parser.sections()

        return sections

    def get_options(self, section):
        log.debug('Get Options: %s'%section)
        section = str(section)
        parser = ConfigParser.RawConfigParser( )
        parser.read(self.path)
        options = parser.options(section)
        return options

            
    def read(self, section, option):
        log.debug('Read: %s/%s'%(section,option))
        try:
            section = str(section)
            option = str(option)
            parser= ConfigParser.RawConfigParser( )
            parser.read(self.path)
            value = parser.get(section, option)
            log.debug('Got: %s'%value)
            return value
        except:
            log.debug('Got no Value:%s/%s'%(section,option))
            return None

    def write(self, section, option, value):
        log.debug('Write: %s/%s:%s'%(section,option,value))
        section = str(section)
        option = str(option)
        value = str(value)
        parser = ConfigParser.RawConfigParser( )
        if os.path.isfile( self.path ):
            parser.read( self.path )
        try:
            parser.add_section(section)
        except:
            pass
        parser.set(section, option, value)
        file_object = open(self.path, 'w')
        parser.write(file_object)
        file_object.close()



import unittest
class TestSettings(unittest.TestCase):
    testfile = 'test'
    def test_01_create(self):
        settings = Settings(self.testfile)

    def test_02_write(self):
        settings = Settings(self.testfile)
        settings.write('a','b','c')
        settings.write('a','d','c')
        settings.write('b','d','c')
        
    def test_03_get_sections(self):
        settings = Settings(self.testfile)
        assert settings.get_sections()  == [ 'a', 'b']
        
    def test_04_get_options(self):
        settings = Settings(self.testfile)
        assert settings.get_options('a')  == ['b','d']

    def test_05_read(self):
        settings = Settings(self.testfile)
        assert settings.read('a','b')  == 'c'

    def test_06_read_error(self):
        settings = Settings(self.testfile)
        assert settings.read('a','x') == None
        
    def test_99_delete(self):
        settings = Settings(self.testfile)
        os.remove(settings.path)

if __name__ == "__main__":
    x = logging.getLogger()
    fmt_string = "[%(levelname)-7s]%(asctime)s.%(msecs)-3d %(module)s[%(lineno)-3d]/%(funcName)-15s  %(message)-8s "
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt_string,"%H:%M:%S"))
    x.addHandler(handler)
    x.setLevel(logging.DEBUG)
    
    unittest.main()
