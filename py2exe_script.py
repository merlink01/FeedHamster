import subprocess, time, os, sys, inspect, shutil
os.chdir(os.path.abspath('src'))
folder = time.strftime("compiled-%Y.%m.%d-%H.%M.%S")
folder_path = os.path.abspath(folder)
try:
    os.path.mkdirs(folder_path)
except:
    pass

print ''

setup_file_path = os.path.abspath('setup.py')



script_path = 'FeedHamsterGui.py'

print("""Create Setup File: "%s" """%setup_file_path)
print("""Compile Folder: "%s" \n"""%folder_path)
time.sleep(5)
file = open(setup_file_path,'w')

setup_file = """from distutils.core import setup

import py2exe, sys, os

sys.argv.append('py2exe')


setup(options = {'py2exe': {
                    'includes' : ["cairo","gobject","gtk","gio","pango","pangocairo","atk","cgi","urllib","urllib2","io","StringIO","gzip","zlib","xml","sgmllib","chardet","BeautifulSoup",
                    "codecs","copy","re","struct","time","urlparse","types","warnings","base64", "binascii","rfc822","email"],
                    'excludes' : [],
                    'bundle_files': 3,
                    'dist_dir': '%s',
                    }},
console = [{'script': "%s"}],
zipfile = None,

)
"""%(folder.replace('\\','/'),script_path.replace('\\','/'))#

file.write(setup_file)
file.close()
cmd = """%s %s py2exe"""%(sys.executable, setup_file_path)
print("""Executing: "%s" \n"""%cmd)
proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout,stderr = proc.communicate()
print stdout
print stderr
print("""Remove Setup File: "%s" \n"""%setup_file_path)

shutil.copytree('plugins',os.path.join(folder_path,'plugins'))
shutil.copytree('lang',os.path.join(folder_path,'lang'))
shutil.copytree('images',os.path.join(folder_path,'images'))
os.remove(setup_file_path)
