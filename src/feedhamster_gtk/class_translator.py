import os

class Translator(object):
    def __init__(self,path=None,language=None):

        self.parser = None
        self.fallback = False
        self.language = language
        self.langlist = []

        if not path:
            self.path = os.path.abspath('lang')
        else:
            self.path = os.path.abspath(path)
            
        try:
            filelist = os.listdir(self.path)
        except:
            self.fallback = True
            return

        for entry in filelist:
            if os.path.splitext(entry)[1] == '.lng':
                full_path = os.path.join(self.path, entry)
                try:
                    parser = ConfigParser.RawConfigParser( )
                    parser.read(full_path)
                    sections = parser.sections()
                    if 'info' in sections:
                        if parser.get('info', 'type') == 'languagefile':
                            self.langlist.append([parser.get('info', 'language'),full_path])
                except:
                    continue

        if self.langlist == []:
            self.fallback = True

        if self.language:
            if not self._check_lang(self.language):
                 self.fallback = True
            if not self.fallback:
                for entry in self.langlist:
                    if entry[0].lower() == self.language.lower():
                        self.parser = ConfigParser.RawConfigParser( )
                        self.parser.read(entry[1])

    def get_langs(self):
        return self.langlist
        
    def set_lang(self,language):
        if self._check_lang(language):
            self.language = language
            for entry in self.langlist:
                if entry[0].lower() == self.language.lower():
                    self.parser = ConfigParser.RawConfigParser( )
                    self.parser.read(entry[1])
        
    def _check_lang(self,language):
        for entry in self.langlist:
            if entry[0].lower() == language.lower():
               return True
        return False

    def getText(self,header,name,fallback):
        try:
            return self.parser.get(header, name)
        except:
            return fallback
