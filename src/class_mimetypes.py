import mimetypes
import logging

class MimeTypesWrapper:
    def __init__(self):
        self.log = logging.getLogger('mimetypeswrapper')
        mimetypes.init()
        self.mimemap =  mimetypes.types_map
        self.reversemap = {}
        
        for ext in self.mimemap:
            mime = self.mimemap[ext]
            if mime in self.reversemap:
                self.reversemap[mime].append(ext)
            else:
                self.reversemap[mime] = [ext]
                
    def get_mimetype(self,ext):
        if ext in self.mimemap:
            return self.mimemap[ext]
        else:
            return None
            
    def get_extension(self,mime):
        self.log.info('Checking: %s'%mime)
        if mime == 'text/plain':
            return ['.txt']
        if mime == 'text/html':
            return ['.html']
        if mime == 'video/mpeg':
            return ['.mgp']
        if mime == 'video/mp4':
            return ['.mp4']
        if mime == 'image/jpeg':
            return ['.jpg']
        if mime == 'audio/mpeg':
            return ['.mp3']
        if mime == 'application/msword':
            return ['.doc']
        if mime == 'audio/x-ogg':
            return ['.ogg']
        
        if mime in self.reversemap:
            return self.reversemap[mime]
        else:
            self.log.info('Not Found')
            return None

#~ a = MimeTypesWrapper()
#~ print a.get_extension('text/html')
#~ 
#~ exit(0)

#~ class Opener:
#~ 
#~ for entry in mimetypes.types_map:
    #~ 
#~ if mimetypes.types_map[entry] == 'text/plain':
        #~ pass


