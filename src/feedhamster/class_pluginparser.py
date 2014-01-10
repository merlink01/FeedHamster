import os
import sys
import imp
import logging
import tempfile
import traceback
import StringIO
import zipfile
import shutil


log = logging.getLogger('pluginparser')

class PluginParser:
    
    def __init__(self, progname, pluginpath, packageextension='.plugin'):
        pluginpath = os.path.abspath(pluginpath)
        self.tempDir = tempfile.mkdtemp()
        self.progName = progname
        self.plugins = {}
        self.counter = 1
             
        if not os.path.isdir(pluginpath):
            return

        #Extract all Packages to the temppath
        counter = 0
        for root, dirs, files in os.walk(pluginpath):
            for filename in files:
                if os.path.splitext(filename)[1] == packageextension:
                    try:
                        zf = zipfile.ZipFile(os.path.join(root,filename),'r')
                        if 'plugin.py' in zf.namelist():
                            extractpath = os.path.join(self.tempDir,str(counter))
                            os.makedirs(extractpath)
                            zf.extractall(extractpath)
                            counter += 1
                    except:
                        pass
                        
        #Collect all plugin Files
        for path in [pluginpath,self.tempDir]:
            for root, dirs, files in os.walk(path):
                for filename in files:
                    if filename == 'plugin.py' or filename == 'plugin.pyc':
                        pluginFilePath = os.path.join(root,filename)
                        plugin = self.AnalysePlugin(pluginFilePath)
                        if plugin != None:
                            name  = plugin['name']
                            if name in self.plugins:
                                if plugin['version'] > self.plugins[name]['version']:
                                    del self.plugins[name]
                                else:
                                    continue
                            self.plugins[name] = plugin
                            
        for plugin in self.plugins:
            log.info('Loaded Plugin: %s'%plugin)
            log.info('Path: %s'%self.plugins[plugin]['path'])
           

    def AnalysePlugin(self,path):
        self.counter += 1
        checkOK = False
        modfolder = os.path.dirname(path)
        
        if not modfolder in sys.path:
            sys.path.append(modfolder)
        
        #If available use only py files
        if path[-1] == 'c':
            if os.path.isfile(path[0:-1]):
                return None
            
        try:
            mod = imp.load_source(str(self.counter),path)
            checkOK = True
        except:
            pass
        
        try:
            mod = imp.load_compiled(str(self.counter),path)
            checkOK = True
        except:
            pass
        
        if not checkOK:
            return None
        
        if not hasattr(mod, 'Plugin'):
            return None
            
        try:
            program = mod.__program__
            name = mod.__pluginname__
            version = float(mod.__version__)
            description = mod.__description__
        except:
            return None
        
        if self.progName != program:
            log.warning('Plugin is not for me')
            return None
            
        return {'name':name,'version':version,'description':description,'path':path,'mod':mod}

            
    def LoadPlugin(self,name):
        log.debug('Load Plugin for: %s'%(name))
        plugininfo = self.plugins[name]            
        return plugininfo['mod']

    def ListPlugins(self):
        return self.plugins
        
    #~ def LoadAll(self):
        #~ plugins = []
        #~ for name in self.plugins:
            #~ plugins.append(self.LoadPlugin(name))
        #~ return plugins

    def __del__(self):
        try:
            shutil.rmtree(self.tempDir,True)
        except:
            pass

