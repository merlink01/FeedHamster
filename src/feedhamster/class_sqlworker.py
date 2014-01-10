import sqlite3
import Queue
import threading
import logging
import time
import StringIO
import traceback
import tempfile

class sqlWorkerThread(threading.Thread):

    def __init__(self,path,temppath=None):
        self.log = logging.getLogger('sql')
        self.log.debug('Starting SQL Worker for: %s'%path)
        threading.Thread.__init__(self)


        self.running = False
        self.path = path
        self.commandQueue = Queue.Queue()
        self.returnQueue = Queue.Queue()
        self.lock = threading.Lock()
        self.name = path
        if temppath:
            self.temppath = temppath
        else:
            self.temppath = tempfile.mkdtemp()


    def getStatus(self):
        return self.running

    def executeCommand(self,*args):
        #~ counter = 0
        #~ while not self.running:
            #~ counter += 1
            #~ time.sleep(0.1)
            #~ if counter == 500:
                #~ self.log.error('SQL-Loop Not Started: %s'%self.path)
                #~ self.log.error(str(args))
                #~ raise IOError

        assert len(args) > 0
        assert len(args) < 4
        job = []
        for arg in args:
            job.append(arg)
        self.lock.acquire()
        self.commandQueue.put(job)
        data = None
        if args[0] == 'get':
            data = self.returnQueue.get()
        if args[0] == 'list_tables':
            data = self.returnQueue.get()
        if args[0] == 'list_columns':
            data = self.returnQueue.get()
        self.lock.release()
        return data

    def get(self,*args):
        assert len(args) > 0
        assert len(args) < 4
        job = ['get']
        for arg in args:
            job.append(arg)

        self.lock.acquire()
        self.commandQueue.put(job)
        data = self.returnQueue.get()
        self.lock.release()
        return data

    def compact(self):
        self.lock.acquire()
        self.commandQueue.put(['compact'])
        data = self.returnQueue.get()
        self.lock.release()
        return data


    def run(self):
        self.log.debug('Starting SQL Loop for: %s'%self.path)
        self.running = True
        self.connection = sqlite3.connect(self.path)
        self.cursor = self.connection.cursor()
        self.cursor.execute("""PRAGMA temp_store_directory = '%s'"""%self.temppath)

        while True:
            action = self.commandQueue.get()

            self.log.debug('Executing: %s'%action)

            assert len(action) > 0
            assert len(action) < 4

            if len(action) == 1:
                if action[0] == 'list_tables':
                    self.log.debug('exec listtable')
                    self.cursor.execute("""SELECT name FROM sqlite_master WHERE type = 'table'""")
                    self.log.debug('Done')
                    self.returnQueue.put(self.cursor.fetchall())

                elif action[0] == 'commit':
                    self.connection.commit()

                elif action[0] == 'compact':
                    try:
                        self.cursor.execute( ''' VACUUM ''')
                        self.returnQueue.put(True)
                    except:
                        tmp = StringIO.StringIO()
                        tmp.write('Vacuum Failed\n%s\n'%self.path)
                        traceback.print_exc(file=tmp)
                        tmp.seek(0, 0)
                        self.log.error(tmp.read())
                        tmp.close()
                        self.returnQueue.put(False)

                elif action[0] == 'exit':
                    self.connection.close()
                    self.log.debug('DB-Thread Exited complete')
                    self.running = False
                    return
                else:
                    raise IOError, 'Unknown command %s'%action[0]

            if len(action) == 2:

                if action[0] == 'put':
                    self.cursor.execute(action[1])

                elif action[0] == 'get':
                    self.cursor.execute(action[1])
                    self.returnQueue.put(self.cursor.fetchall())


                elif action[0] == 'list_columns':
                    columns = []
                    self.cursor.execute("""PRAGMA table_info(%s)"""%action[1])
                    data = self.cursor.fetchall()
                    for entry in data:
                        columns.append(entry[1])
                    self.returnQueue.put(columns)

                else:
                    raise IOError, 'Unknown command %s'%action[0]

            if len(action) == 3:
                if action[0] == 'put':
                    self.log.debug('Put: %s - %s'%(action[1],str(action[2])))
                    try:
                        self.cursor.execute(action[1],action[2])
                    except:
                        tmp = StringIO.StringIO()
                        tmp.write('DB Put Failed\n%s\n'%self.path)
                        traceback.print_exc(file=tmp)
                        tmp.seek(0, 0)
                        self.log.error(self.path + '\n' + tmp.read())
                        tmp.close()

                elif action[0] == 'get':
                    self.log.debug('Get: %s - %s'%(action[1],action[2]))
                    try:
                        self.cursor.execute(action[1],action[2])
                        returndata = self.cursor.fetchall()
                        self.log.debug('Got %s'%returndata)
                        self.returnQueue.put(returndata)
                    except:
                        tmp = StringIO.StringIO()
                        tmp.write('DB Get Failed\n%s\n'%self.path)
                        traceback.print_exc(file=tmp)
                        tmp.seek(0, 0)
                        self.log.error(self.path + '\n' + tmp.read())
                        tmp.close()
                        self.returnQueue.put(None)
                else:
                    raise IOError, 'Unknown command %s'%action[0]


import unittest
class TEST_sqlworker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        global path
        global folderpath
        import tempfile
        folderpath = tempfile.mkdtemp()
        path = folderpath + '/test.db'

        global db
        db = sqlWorkerThread(path)
        db.start()
        import time
        time.sleep(5)

    @classmethod
    def tearDownClass(cls):
        import shutil
        import time
        db.executeCommand('exit')
        time.sleep(1)
        #~ try:
            #~ shutil.rmtree(folderpath)
        #~ except:
            #~ pass

    def test_01_settings(self):
        sql = "CREATE TABLE IF NOT EXISTS settings (setting TEXT, value TEXT)"
        db.executeCommand('put',sql)
        db.executeCommand('commit')
        sql = "INSERT INTO settings (value,setting) VALUES (?,?)"
        db.executeCommand('put',sql, (10,'test'))
        sql = "SELECT value FROM settings WHERE setting=?"
        assert db.executeCommand('get',sql, ('test',))[0][0] == '10'

        sql = "UPDATE settings SET value=? where setting=?"
        db.executeCommand('put',sql, (15,'test'))
        db.executeCommand('commit')
        sql = "SELECT value FROM settings WHERE setting=?"
        assert db.executeCommand('get',sql, ('test',))[0][0] == '15'



if __name__ == "__main__":
    import sys, os
    x = logging.getLogger()
    fmt_string = "[%(levelname)-7s]%(asctime)s.%(msecs)-3d\
    %(module)s[%(lineno)-3d]/%(funcName)-10s  %(message)-8s "
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt_string, "%H:%M:%S"))
    x.addHandler(handler)
    x.setLevel(logging.DEBUG)

    unittest.main()


