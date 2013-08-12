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
        
        log.debug('Name:%s , Path:%s, Ext:%s'%(progname, pluginpath, packageextension))
        
        if not os.path.isdir(pluginpath):
            return

        #Extract all Packages to the temppath
        counter = 0
        for root, dirs, files in os.walk(pluginpath):
            for filename in files:
                print filename
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
           
                    
        
    def AnalysePlugin(self,path):
        log.info('Is Plugin Importable:%s'%path)
        checkOK = False
        modfolder = os.path.dirname(path)
        if not modfolder in sys.path:
            sys.path.append(modfolder)
        try:
            mod = imp.load_source('x',path)
            checkOK = True
        except:
            pass
        
        try:
            mod = imp.load_compiled('x',path)
            checkOK = True
        except:
            pass
            
            
        log.info('result:%s'%path)
        
        if not checkOK:
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
            
        return {'name':name,'version':version,'description':description,'path':path}
            
    def LoadPlugin(self,name):
        plugininfo = self.plugins[name]
        path = plugininfo['path']
        try:
            mod = imp.load_source('x',path)
        except:
            pass
        
        try:
            mod = imp.load_compiled('x',path)
        except:
            pass
            
        return mod

    def ListPlugins(self):
        return self.plugins
        
    def LoadAll(self):
        plugins = []
        for name in self.plugins:
            plugins.append(self.LoadPlugin(name))
        return plugins

    def __del__(self):
        try:
            shutil.rmtree(self.tempDir,True)
        except:
            pass

