#!/usr/bin/env python
import os
import sys

import Queue
import time
import datetime
import logging
import logging.handlers
import multiprocessing
import threading
import resource
import thread
import tempfile
import StringIO

import traceback

import gtk
import pygtk
import gobject

gobject.threads_init()
if gtk.pygtk_version < (2,3,90):
   print "PyGtk 2.3.90 or later required for this program"
   raise SystemExit

import singleton
import class_settings
import class_feedhamster
import class_translator

class FeedHamsterGUI:
    def __init__(self):
        self.log = logging.getLogger('FeedHamsterGui')
        
        self.log.info('Starting up FeedHamster-GTK')
        self.workerQueue = Queue.Queue()
        self.shutdown = False
        self.stopFeedViewColorChange = False
        tempdir = tempfile.gettempdir()
        self.syncStatus = None

        self.log.info('Initializing Gui')
        self.feedOpenDates = {}
        self.openFeed = None
        self.summarySize = 8
        self.syncTime = 30
        self.deleteQueueLock = thread.allocate_lock()
        self.deleteQueue = []

        sets = class_settings.Settings('Feedhamster')

        path = sets.read('Settings', 'Feedpath')
        lang = sets.read('Settings', 'Language')
        self.lng = class_translator.Translator(language='de_DE')
        if not path:
            question = self.lng.getText('main','messageworkingdir','Open Working Directory.')
            dialog = gtk.FileChooserDialog(question,None,gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                              (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN, gtk.RESPONSE_OK))
            dialog.set_default_response(gtk.RESPONSE_OK)
            response = dialog.run()
            if response == gtk.RESPONSE_OK:
                path = dialog.get_filename()
                sets.write('Settings', 'Feedpath', path)
                dialog.destroy()
            elif response == gtk.RESPONSE_CANCEL:
                sys.exit(0)

        self.path = path
        self.feedhamster = class_feedhamster.FeedHamster(self.path)
        #~ self.feedhamster.offline_mode = True
        self.GuiMain()
        self.GuiTop()
        self.GuiFeeds()
        self.GuiNews()
        self.GuiBottom()

        #Activate Gui
        self.log.debug('Gui Ready... Showing')
        self.mainWindow.show()

        self._NamedThread('Delete Deamon',target=self.DeamonThreadDelete)
        self._NamedThread('Worker',target=self._worker_thread)
        self.workerQueue.put('changecolors')

    def ActionStatusBarPrint(self,message):
        def senddata(data):
            self.statusBar.pop(0)
            self.statusBar.push(0,data)
        if message:
            gobject.idle_add(senddata,message)

    def GuiTop(self):
        
        button = gtk.Button('Download')
        button.connect("clicked", self.ActionStartSync)
        self.topBox.pack_start(button,False, False, 2)
        button.show()
        
        button = gtk.Button('Add Feed')
        button.connect("clicked", self.button_add_feed)
        self.topBox.pack_start(button,False, False, 0)
        button.show()
        
        button = gtk.Button('Import')
        button.connect("clicked", self.ActionStartSync)
        self.topBox.pack_start(button,False, False, 0)
        button.show()
        
        button = gtk.Button('Export')
        button.connect("clicked", self.ActionStartSync)
        self.topBox.pack_start(button,False, False, 0)
        button.show()
        
        button = gtk.Button('Settings')
        button.connect("clicked", self.ActionStartSync)
        self.topBox.pack_start(button,False, False, 0)
        button.show()
        
        
        
        #create main menus
        #~ topMenu = gtk.Menu()
        #~ entries = []
        #~
        #~ entries.append([self.lng.getText('top','menufileadd','Add new Source'),self.EventFeedAdd])
        #~ entries.append([self.lng.getText('top','menufileimport','Import Feed'),self.ActionStartSync])
        #~ entries.append([self.lng.getText('top','menufileexport','Export Feed'),self.ActionStartSync])
        #entries.append([self.lng.getText('maingui','settings') or 'Settings',self.EventSettings])
        #~ entries.append([self.lng.getText('top','menufileexit','Beenden'),self.EventShutDown])
        #~
        #~ for entry in entries:
            #~ menu_items = gtk.MenuItem(entry[0])
            #~ topMenu.append(menu_items)
            #~ menu_items.connect("activate", entry[1], entry[0])
            #~ menu_items.show()
        #~ root_menu = gtk.MenuItem(self.lng.getText('top','menufile','File'))
        #~ root_menu.show()
        #~ root_menu.set_submenu(topMenu)
        #~ menu_bar = gtk.MenuBar()
        #~ self.topBox.pack_start(menu_bar, False, False, 2)
        #~ menu_bar.show()
        #~ menu_bar.append(root_menu)

        #create search bar
        searchBar = gtk.Entry()
        searchBar.set_max_length(50)
        searchBar.connect("activate", self.EventSearchRun)
        searchBar.set_text(self.lng.getText('top','search','Search'))
        self.topBox.pack_end(searchBar, False, False, 2)
        searchBar.show()

        #create filter comboboxes
        comboCount = gtk.combo_box_new_text()
        self.topBox.pack_end(comboCount, False, False, 2)
        comboCount.append_text('50')
        comboCount.append_text('100')
        comboCount.append_text('500')
        comboCount.append_text('1000')
        comboCount.append_text(self.lng.getText('top','comboall','All'))
        comboCount.connect('changed', self.EventComboChanged,  'count')
        comboCount.set_active(0)
        comboCount.show()
        self.comboCount = 0
        comboMeta = gtk.combo_box_new_text()
        self.topBox.pack_end(comboMeta, False, False, 2)
        comboMeta.append_text(self.lng.getText('top','combounread','Unread'))
        comboMeta.append_text(self.lng.getText('top','combofav','Favorites'))
        comboMeta.append_text(self.lng.getText('top','comboallnews','All'))
        comboMeta.connect('changed', self.EventComboChanged, 'meta')
        comboMeta.set_active(0)
        comboMeta.show()
        self.comboMeta = 0

    def GuiMain(self):
        self.log.debug('Create Main Window')
        self.mainWindow = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.mainWindow.set_position(gtk.WIN_POS_CENTER)
        self.mainWindow.set_size_request(1000, 500)
        self.mainWindow.set_title("FeedHamster (v%s)"%self.feedhamster.settings['version'])
        self.mainWindow.connect("delete_event", self.EventShutDown)

        picture = "./images/hamster.png"
        if os.path.isfile(picture):
            self.mainWindow.set_icon_from_file(picture)
            pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(picture,60,60)
            statusicon = gtk.StatusIcon()
            statusicon = gtk.status_icon_new_from_pixbuf(pixbuf)
            statusicon.connect("activate",self.EventTrayClick)
        else:
            self.log.warning('Picture Missing: %s'%os.path.abspath(picture))
        self.log.debug('Done')
        #Create Main Box
        self.log.debug('Create Main Box...')
        self.mainBox = gtk.VBox(False, 0)
        self.mainWindow.add(self.mainBox)
        self.mainBox.show()
        #Create Top Menu
        self.topBox = gtk.HBox(False, 0)
        self.mainBox.pack_start(self.topBox, False, False, 2)
        self.topBox.show()
        #Create Working Box
        self.log.debug('Create Working Box...')
        self.workBox = gtk.HBox(False, 0)
        self.mainBox.add(self.workBox)
        self.workBox.show()
        #Create Message Box
        self.log.debug('Create Message Box...')
        self.messBox = gtk.VBox(False, 0)
        self.workBox.pack_end(self.messBox, True, True, 0)
        self.messBox.show()
        #Create Botton Box
        self.log.debug('Create Message Box...')
        self.bottonBox = gtk.HBox(False, 0)
        self.mainBox.pack_end(self.bottonBox, False, False, 2)
        self.bottonBox.show()

    def DeamonThreadDelete(self):
        while 1:

            time.sleep(1)
            if self.shutdown:
                self.log.debug('Exit Delete Thread')
                return

            if len(self.deleteQueue) > 0:

                self.deleteQueueLock.acquire()
                todelete = self.deleteQueue
                self.deleteQueue = []
                self.deleteQueueLock.release()

                while len(todelete) > 0:
                    self.ActionStatusBarPrint('Delete Jobs Queue: %s'%len(todelete))

                    message = todelete.pop()
                    feedID = message[0]
                    messageID = message[1]
                    feedObj = self.feedhamster.feed_get(feedID)
                    self.log.debug('Delete %s/%s'%(feedID,messageID))
                    feedObj.message_delete(messageID)
                self.ActionStatusBarPrint('Ready')




    #~ def WorkerSync(self):
        #~ if self.syncStatus != None:
            #~ return
            #~
        #~ self.syncStatus = 0
        #~ feedobs = self.feedhamster.feedobs
        #~
        #~ for feedobj in feedobs:
            #~
            #~ while self._CountSyncs() > 3:
                #~ time.sleep(1)
            #~
            #~ self._NamedThread('update_thread',target=feedobj.sync)
            #~
        #~ self.syncStatus = None
        #~ self.ActionStatusBarPrint('Ready')
        #~ self.ActionFeedChangeColors()

    #~ def WorkerSync(self):
        #~ self.ActionStatusBarPrint('Sync....')
        #~ self.feedhamster.FeedsSync()
        #~ time.sleep(0.1)
        #~ while self.feedhamster.sync_status != None:
            #~ time.sleep(0.5)
            #~ if self.shutdown:
                #~ return
            #~ self.ActionStatusBarPrint(self.feedhamster.sync_status)
        #~ self.ActionStatusBarPrint('Ready')
        #~ self.ActionFeedChangeColors()

    def _threadsListRunning(self):
        outList = []
        threads = threading.enumerate()
        for th in threads:
            outList.append(th.getName())
        return outList
        
    def EventShutDown(self,*args):
        
        self.workerQueue.put('shutdown')

        gtk.main_quit()
    
    def show_feedhamster_status(self):
        if self.feedhamster.worker_job:
            gobject.idle_add(self.progress_bar.show)
            self.progress_bar.set_text('%s: %s Percent'%(self.feedhamster.worker_job.capitalize(),self.feedhamster.worker_status))
            self.progress_bar.update(float(self.feedhamster.worker_status)/100)
        else:
            gobject.idle_add(self.progress_bar.hide)
    
    def _worker_thread(self):
        while True:
            try:
                job = self.workerQueue.get(block=True,timeout=0.1)
            except:
                job = None
                self.show_feedhamster_status()


            if job == 'shutdown':
                self.log.info('Shutting Down')
                self.shutdown = True
                self.feedhamster.feedhamster_shutdown()
                return

            if job == 'changecolors':
                if self.shutdown:
                    continue
                model = self.feedView.get_model()
                if not model:
                    continue
                    
                treemodelrowiter = iter(model)
                for folder in treemodelrowiter:
                    
                    if self.shutdown:
                        self.log.info('Ended')
                        return
                    childiter = folder.iterchildren()
                    changed = False
                    for child in childiter:
                        self.show_feedhamster_status()
                        if self.shutdown:
                            self.log.info('Ended')
                            return

                        feedObj = self.feedhamster.feed_get(child[1])

                        if feedObj.feed_count('newest') > 0:
                            changed = True
                            child[2] = '#901000'
                        else:
                            child[2] = None

                    if changed:
                        folder[2] = '#901000'
                    else:
                        folder[2] = None



    def ActionStartSync(self, *args):
        self.feedhamster.download()

    def ActionFeedViewBuild(self):

        feedList = []
        for feed in self.feedhamster.feedobs:
            name = feed._read_setting('name')
            genre = feed._read_setting('genre')

            if genre == '':
                genre = 'Unknown'
            feedList.append([genre,name,feed.feed_id])
        feedList.sort()

        feedStore = gtk.TreeStore(str,str,str)
        parents = {}

        for feed in feedList:
            if not feed[0] in parents:
                parents[feed[0]] = feedStore.append(None, [feed[0],None,None])

            feedStore.append(parents[feed[0]],[feed[1],feed[2],None])
        self.feedView.set_model(feedStore)


    def ActionMessageViewBuild(self, fid, keyword=None):

        gobject.idle_add(self.spinner.show)
        gobject.idle_add(self.spinner.start)

        self.log.info('Build News View for: %s'%fid)
        feedObj = self.feedhamster.feed_get(fid)
        newMessages = feedObj.feed_get_newest()

        name = feedObj._read_setting('name')
        feedscount = feedObj.feed_count()
        unread = feedObj.feed_count('unread')
        favorites = feedObj.feed_count('favorites')
        pluginname = feedObj._read_setting('plugin')
        size = feedObj.feed_get_size(True)
        newsCount = feedObj.feed_count('newest')


        store = gtk.ListStore(str, bool, bool, str, str, str, str)

        count = -1
        if self.comboCount == 0:
            count = 50
        if self.comboCount == 1:
            count = 100
        if self.comboCount == 2:
            count = 500
        if self.comboCount == 3:
            count = 1000

        if self.comboMeta == 0:
            news = feedObj.feed_search(keyword,unread=True,count=count)

        if self.comboMeta == 1:
            news = feedObj.feed_search(keyword,favorites=True,count=count)

        if self.comboMeta == 2:
            news = feedObj.feed_search(keyword,count=count)
        showing = len(news)

        self.log.debug('Got %s Messages'%len(news))
        counter = 0
        newscount = len(news)
        for message in news:
            counter += 1


            self.ActionStatusBarPrint('Loading: %s from %s'%(counter,newscount))

            tree_sel = self.feedView.get_selection()
            (tm, ti) = tree_sel.get_selected()

            fid = tm.get_value(ti, 1)
            if fid != None:
                if fid != feedObj.feed_id:
                    return
            loadtime = time.time()
            info = feedObj.message_get_meta(message)

            stime = ''
            if int(info['recieved']) > -1:
                stime = str(datetime.datetime.utcfromtimestamp(int(info['recieved'])))

            if int(info['updated']) > -1:
                stime = str(datetime.datetime.utcfromtimestamp(int(info['updated'])))

            if int(info['created']) > -1:
                stime = str(datetime.datetime.utcfromtimestamp(int(info['created'])))

            title = info['title'].split('\n')[0]

            if message in newMessages:
                store.append([message, bool(info['read']), bool(info['favorite']), stime, title, '#901000',None])
            else:
                store.append([message, bool(info['read']), bool(info['favorite']), stime, title, None,None])

        tree_sel = self.feedView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        fid = tm.get_value(ti, 1)
        #print fid,feedObj.feed_id
        if fid != None:
            if fid != feedObj.feed_id:
                return

        gobject.idle_add(self.newsView.set_model,store)
        sbString = '%s\tType:%s\t\tSize:%s\tShowing:%s\t| Feeds:%s\tUnread:%s\tFavorites:%s\tNews:%s'%(name,pluginname,size,showing,feedscount,unread,favorites,newsCount)
        gobject.idle_add(self.mainWindow.set_title,"feedhamster (%s)"%name)
        self.ActionStatusBarPrint(sbString)
        gobject.idle_add(self.spinner.stop)
        gobject.idle_add(self.spinner.hide)
        self.workerQueue.put('changecolors')

    def EventTrayClick(self):
        pass

    def EventMessageToggleRead(self, cell, path, model, *ignore):
        model = self.newsView.get_model()
        it = model.get_iter(path)
        value = not model[it][1]
        model[it][1] = value
        feedObj = self.feedhamster.feed_get(self.openFeed)
        feedObj.message_set_meta(model[it][0],'read',value)

    def EventMessageToggleFavorite(self, cell, path, model, *ignore):
        model = self.newsView.get_model()
        it = model.get_iter(path)
        value = not model[it][2]
        model[it][2] = value
        feedObj = self.feedhamster.feed_get(self.openFeed)
        feedObj.message_set_meta(model[it][0],'favorite',value)

    def EventMessageDelete(self, widget):
        feedObj = self.feedhamster.feed_get(self.openFeed)
        model = self.newsView.get_model()
        tree_sel = self.newsView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        nid = (tm.get_value(ti, 0))
        row = tree_sel.get_selected_rows()[1][0]
        del(model[row])
        self.Lock.acquire()
        self.deleteQueue.append([feedObj.feed_id,nid])
        self.deleteQueueLock.release()


    def EventFeedKeyPress(self,treeview, event):
        key = gtk.gdk.keyval_name(event.keyval)
        if key == 'Right':
            tree_sel = treeview.get_selection()
            (tm, ti) = tree_sel.get_selected()
            model = treeview.get_model()
            if model.iter_has_child(ti):
                path = tm.get_path(ti)
                treeview.collapse_all()
                treeview.expand_row(path,True)

    def EventMessageKeyPress(self,treeview, event):
        key = gtk.gdk.keyval_name(event.keyval)

        if key == 'Delete':

            feedObj = self.feedhamster.feed_get(self.openFeed)

            model = treeview.get_model()
            if len(model) == 0:
                return

            if len(model) == 1:
                ts = treeview.get_selection()
                row = ts.get_selected_rows()[1][0]
                fid = model[row][0]
                del(model[0])
                self.deleteQueueLock.acquire()
                self.deleteQueue.append([feedObj.feed_id,fid])
                self.deleteQueueLock.release()
                return

            ts = treeview.get_selection()
            row = ts.get_selected_rows()[1][0]
            fid = model[row][0]

            if row[0] + 1 >= len(model):
                treeview.set_cursor(row[0]-1)
            else:
                treeview.set_cursor(row[0]+1)

            del(model[row])
            self.deleteQueueLock.acquire()
            self.deleteQueue.append([feedObj.feed_id,fid])
            self.deleteQueueLock.release()

    def GuiFeeds(self):
        #Create Treeview for Feeds
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.workBox.pack_start(sw,False,False,3)

        self.feedStore = gtk.TreeStore(str,str,str)
        self.feedView = gtk.TreeView(self.feedStore)
        self.feedView.connect('key-press-event', self.EventFeedKeyPress)
        self.feedView.connect('button-release-event' , self.EventFeedViewClicked)
        self.feedView.connect('cursor-changed' , self.EventFeedViewChanged)
        self.tvcolumn = gtk.TreeViewColumn(self.lng.getText('feeds','categories','Categories'))

        self.tvcolumn.set_sort_column_id(0)
        self.feedView.append_column(self.tvcolumn)

        self.cell = gtk.CellRendererText()
        self.tvcolumn.pack_start(self.cell, True)
        self.tvcolumn.add_attribute(self.cell, 'text', 0)
        self.tvcolumn.add_attribute(self.cell, 'foreground', 2)

        self.feedView.set_search_column(2)
        self.ActionFeedViewBuild()
        sw.add(self.feedView)
        self.feedView.show()
        sw.show()

        #FeedView right click menu
        self.FeedViewMenu = gtk.Menu()
        menuitem1 = gtk.MenuItem(self.lng.getText('feeds','buttonfeedrename','Rename'))
        menuitem2 = gtk.MenuItem(self.lng.getText('feeds','buttonfeedsetgenre','Set Genre'))
        menuitem3 = gtk.MenuItem(self.lng.getText('feeds','buttonfeeddelete','Delete'))
        menuitem4 = gtk.MenuItem(self.lng.getText('feeds','buttonfeedsync','Sync'))
        menuitem5 = gtk.MenuItem(self.lng.getText('feeds','buttonfeedproerties','Properties'))

        menuitem1.connect("activate", self.EventFeedSetName)
        menuitem2.connect("activate", self.EventFeedSetGenre)
        menuitem3.connect("activate", self.EventFeedDelete)
        menuitem4.connect("activate", self.EventFeedSync)
        menuitem5.connect("activate", self.EventFeedShowProperties)

        self.FeedViewMenu.append(menuitem1)
        self.FeedViewMenu.append(menuitem2)
        self.FeedViewMenu.append(menuitem3)
        self.FeedViewMenu.append(menuitem4)
        self.FeedViewMenu.append(menuitem5)

    def GuiBottom(self):
        #Create Button Statusbar
        self.spinner = gtk.Spinner()        
        self.bottonBox.pack_start(self.spinner, False, True, 5)       
        
        self.progress_bar = gtk.ProgressBar()
        self.progress_bar.set_activity_step(1)
        self.bottonBox.pack_end(self.progress_bar, False, True, 5)
        self.statusBar = gtk.Statusbar()
        self.bottonBox.pack_end(self.statusBar, True, True, 0)
        self.statusBar.push(0, 'Ready')
        self.statusBar.show()
        self.log.debug('Done')

    def GuiNews(self):
        #Create News View
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.messBox.add(sw)

        store = gtk.ListStore(str, bool, bool, str, str, str, str)
        self.newsView = gtk.TreeView(store)
        self.newsView.connect('row-activated', self.EventMessageOpen)
        self.newsView.connect('key-press-event', self.EventMessageKeyPress)
        self.newsView.connect('button-release-event' , self.EventMessageViewClicked)
        self.newsView.connect('cursor-changed' , self.EventMessageSelect)
        self.newsView.set_rules_hint(True)
        sw.add(self.newsView)

        #Create columns
        columns = []
        columns.append([self.lng.getText('news','columnread','Read'),'cell','read'])
        columns.append([self.lng.getText('news','columnfav','Favorite'),'cell', 'fav'])
        columns.append([self.lng.getText('news','columntime','Time'),'text','time'])
        columns.append([self.lng.getText('news','columntitle','Title'),'text','title'])
        counter = 1
        for entry in columns:
            if entry[1] == 'text':
                text = gtk.CellRendererText()
                column = gtk.TreeViewColumn(entry[0], text, text=counter, foreground=5, background=6)
            else:
                cell = gtk.CellRendererToggle()
                #~ cell.set_activatable(True)
                if entry[2] == 'read':
                    cell.connect("toggled", self.EventMessageToggleRead,store)
                if entry[2] == 'fav':
                    cell.connect("toggled", self.EventMessageToggleFavorite,store)
                column = gtk.TreeViewColumn(entry[0], cell, active=counter)

            column.set_sort_column_id(counter)
            self.newsView.append_column(column)
            counter += 1

        sw.show()
        self.newsView.show()
        self.log.debug('Done')

        #textview
        self.summaryView = gtk.TextView()
        textbuffer = self.summaryView.get_buffer()
        self.summaryView.set_editable(False)
        self.messBox.pack_end(self.summaryView,False,False,2)

        #NewsView right click menu
        self.NewsViewMenu = gtk.Menu()

        menuitem1 = gtk.MenuItem(self.lng.getText('news','menuopen','Open'))
        menuitem2 = gtk.MenuItem(self.lng.getText('news','menuopenonline','Open Online'))
        menuitem3 = gtk.MenuItem(self.lng.getText('news','menusaveas','Save as'))
        menuitem4 = gtk.MenuItem(self.lng.getText('news','menudelete','Delete'))
        menuitem5 = gtk.MenuItem(self.lng.getText('news','menuproperties','Properties'))

        menuitem1.connect("activate", self.EventMessageMenuOpen)
        menuitem2.connect("activate", self.EventMessageMenuOpenOnline)
        menuitem3.connect("activate", self.EventMessageSaveAs)
        menuitem4.connect("activate", self.EventMessageDelete)
        menuitem5.connect("activate", self.EventMessageShowProperties)

        self.NewsViewMenu.append(menuitem1)
        self.NewsViewMenu.append(menuitem2)
        self.NewsViewMenu.append(gtk.SeparatorMenuItem())
        self.NewsViewMenu.append(menuitem3)
        self.NewsViewMenu.append(menuitem4)
        self.NewsViewMenu.append(gtk.SeparatorMenuItem())
        self.NewsViewMenu.append(menuitem5)

    def EventMessageSaveAs(self,widget,*args):
        feedObj = self.feedhamster.feed_get(self.openFeed)
        tree_sel = self.newsView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        nid = (tm.get_value(ti, 0))
        meta = feedObj.message_get_meta(nid)
        filechooserdialog = gtk.FileChooserDialog("Save File", None,
         gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
         gtk.STOCK_OK, gtk.RESPONSE_OK))
        
        mime = feedObj.message_get_meta(nid)['mimetype']
        extension = feedObj.mimetypes.get_extension(mime)

        filechooserdialog.set_current_name(meta['title'].split('\n')[0] + extension[0])

        filechooserdialog.set_default_response(gtk.RESPONSE_OK)
        response = filechooserdialog.run()
        if response == gtk.RESPONSE_OK:
            path = filechooserdialog.get_filename()
            
            if os.path.exists(path):
                ##########Gui
                d = gtk.MessageDialog(filechooserdialog,
                                    gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                    gtk.MESSAGE_QUESTION,
                                    gtk.BUTTONS_YES_NO,'Overwite Existing File')

                d.set_default_response(gtk.RESPONSE_YES)
                r = d.run()
                d.destroy()
                ##########
                print r
                if r == gtk.RESPONSE_NO:
                    filechooserdialog.destroy()
                    return
            self.log.info('Writing File: %s'%path)
            data = feedObj.message_get_data(nid)
            outFile = open(path,'wb')
            outFile.write(data)
            outFile.close()
            self.log.info('Done')

        filechooserdialog.destroy()
        return

    def EventFeedShowProperties(self, *args):
        tree_sel = self.feedView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        fid = (tm.get_value(ti, 1))
        feedObj = self.feedhamster.feed_get(fid)

        stime = feedObj._read_setting('last_synced')
        if stime <= 0:
            stime = ''
        else:
            stime = datetime.datetime.utcfromtimestamp(int(stime))

        ctime = feedObj._read_setting('last_compacted')
        if ctime <= 0:
            ctime = ''
        else:
            ctime = datetime.datetime.utcfromtimestamp(int(ctime))

        text = ''

        text += 'Name:  \t\t\t %s\n'%feedObj._read_setting('name')
        text += 'Genre: \t\t\t %s\n'%feedObj._read_setting('genre')
        text += 'Size: \t\t\t %s\n'%feedObj.feed_get_size(True)
        text += 'Plugin:\t\t\t %s\n'%feedObj._read_setting('plugin')

        text += 'Count: \t\t\t %s\n'%feedObj.feed_count()
        text += 'Unread: \t\t\t %s\n'%feedObj.feed_count('unread')
        text += 'Favorites: \t\t %s\n'%feedObj.feed_count('favorites')
        text += 'New: \t\t\t %s\n'%feedObj.feed_count('newest')

        text += 'Last Synced: \t\t %s\n'%stime
        text += 'Last Compacted: \t %s\n'%ctime



        d = gtk.MessageDialog(self.mainWindow,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            gtk.MESSAGE_INFO,
                            gtk.BUTTONS_OK,text)

        d.set_title(feedObj._read_setting('name'))

        d.set_default_response(gtk.BUTTONS_OK)
        r = d.run()
        d.destroy()

    def EventMessageShowProperties(self,widget,*args):
        feedObj = self.feedhamster.feed_get(self.openFeed)
        tree_sel = self.newsView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        nid = (tm.get_value(ti, 0))

        metadata = feedObj.message_get_meta(nid)

        text = ''
        text += 'URL         \t: %s\n\n'%metadata['url']
        text += 'Parent      \t: %s\n'%feedObj._read_setting('name')
        text += 'UUID        \t: %s\n'%metadata['uuid']
        text += 'Mimetype   \t: %s\n'%metadata['mimetype']
        text += 'Encoding   \t: %s\n'%metadata['encoding']

        created = int(metadata['created'])
        if created <= 0:
            created = ''
        else:
            created = datetime.datetime.utcfromtimestamp(int(metadata['created']))

        updated = int(metadata['updated'])
        if updated <= 0:
            updated = ''
        else:
            updated = datetime.datetime.utcfromtimestamp(int(metadata['updated']))

        recieved = int(metadata['created'])
        if recieved <= 0:
            recieved = ''
        else:
            recieved = datetime.datetime.utcfromtimestamp(int(metadata['recieved']))

        text += 'Created    \t: %s\n'%created
        text += 'Updated    \t: %s\n'%updated
        text += 'Recieved   \t: %s\n'%recieved
        text += 'Read         \t: %s\n'%metadata['read']
        text += 'Favorites  \t: %s\n'%metadata['favorite']
        text += 'Removed    \t: %s\n'%metadata['removed']

        d = gtk.MessageDialog(self.mainWindow,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            gtk.MESSAGE_INFO,
                            gtk.BUTTONS_OK,text)

        d.set_title(metadata['title'])

        d.set_default_response(gtk.BUTTONS_OK)
        r = d.run()
        d.destroy()

    def EventMessageSelect(self, widget, *args):

        feedObj = self.feedhamster.feed_get(self.openFeed)

        model = widget.get_model()
        if len(model) == 0:
            return

        ts = widget.get_selection()
        row = ts.get_selected_rows()[1][0]

        fid = model[row][0]
        #~ print fid
        textbuffer = self.summaryView.get_buffer()
        summary = feedObj.message_get_meta(fid)['summary']
        while '  ' in summary:
            summary = summary.replace('  ',' ')
        summary = summary.replace('\r','\n')
        summary = summary.replace('\n\n','\n')
        summary = summary.replace('\n \n','\n')
        ssummary = summary.split('\n')

        summary = ''
        lines = 0
        for info in ssummary:
            lines += 1

            if lines >= self.summarySize:
                summary += info
                break
            else:
                summary += info + '\n'
        if lines < self.summarySize:
            summary += '\n'*((self.summarySize-lines)-1)
        self.summaryView.show()
        textbuffer.set_text(summary)

    def EventMessageMenuOpenOnline(self,widget,*args):
        feedObj = self.feedhamster.feed_get(self.openFeed)
        tree_sel = self.newsView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        nid = (tm.get_value(ti, 0))
        tm.set_value(ti, 1,True)
        feedObj.message_open(nid,True)

    def EventMessageMenuOpen(self,widget,*args):
        feedObj = self.feedhamster.feed_get(self.openFeed)
        tree_sel = self.newsView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        nid = (tm.get_value(ti, 0))
        tm.set_value(ti, 1,True)
        feedObj.message_open(nid)

    def EventMessageOpen(self, cell, path, model, *args):
        model = cell.get_model()
        model[path][1] = True
        messageID = model[path][0]
        feedObj = self.feedhamster.feed_get(self.openFeed)
        feedObj.message_open(messageID,online=False)

    def EventFeedSync(self, *args):
        tree_sel = self.feedView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        fid = (tm.get_value(ti, 1))
        feedObj = self.feedhamster.feed_get(fid)

        self._NamedThread('Sync ...',target=feedObj.sync)

    def EventFeedSetName(self, *args):

        tree_sel = self.feedView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        fid = (tm.get_value(ti, 1))
        feedObj = self.feedhamster.feed_get(fid)

        message = '%s\n%s'%(self.lng.getText('feeds','messagefeedrename','Please enter a name for:'),feedObj.url)

        default = feedObj._read_setting('name')
        if default == '':
            default = feedObj.url

        ##########Gui
        parent = self.mainWindow
        d = gtk.MessageDialog(parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            gtk.MESSAGE_QUESTION,
                            gtk.BUTTONS_OK_CANCEL,message)
        entry = gtk.Entry()
        entry.set_text(default)
        entry.show()
        d.vbox.pack_end(entry)
        entry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
        d.set_default_response(gtk.RESPONSE_OK)
        r = d.run()
        name = entry.get_text().decode('utf8')
        d.destroy()
        ##########

        if r == gtk.RESPONSE_OK:
            feedObj._write_setting('name',name,True)
            self.ActionFeedViewBuild()

    def EventSettings(self, *args):

        dialog = gtk.Dialog("Settings",
                           None,
                           gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                           (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                            gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

        entry = gtk.Entry()
        entry.show()
        dialog.vbox.pack_end(entry)
        r = dialog.run()
        dialog.destroy()

    def EventFeedSetGenre(self, *args):
        default = 'Genre'
        tree_sel = self.feedView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        fid = (tm.get_value(ti, 1))
        feedObj = self.feedhamster.feed_get(fid)

        message = '%s\n%s'%(self.lng.getText('feeds','messagefeedsetgenre','Please enter the genre for:'),feedObj.url)

        parent = self.mainWindow
        d = gtk.MessageDialog(parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            gtk.MESSAGE_QUESTION,
                            gtk.BUTTONS_OK_CANCEL,message)
        entry = gtk.Entry()
        entry.set_text(default)
        entry.show()
        d.vbox.pack_end(entry)
        entry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
        d.set_default_response(gtk.RESPONSE_OK)
        r = d.run()
        name = entry.get_text().decode('utf8')
        d.destroy()
        if r == gtk.RESPONSE_OK:
            feedObj._write_setting('genre',name,True)
            self.ActionFeedViewBuild()

    def button_add_feed(self, *args):
        self.ActionStatusBarPrint('Add new Feed')
        while 1:
            message = self.lng.getText('top','messagefeedadd','Please Enter the Feed Type and URL:')
            message += ' ' * 20
            parent = self.mainWindow
            default = 'http://news.google.de/news?q=bitmessage&output=rss'
            d = gtk.MessageDialog(parent,
                                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                gtk.MESSAGE_QUESTION,
                                gtk.BUTTONS_OK_CANCEL,message)

            combo = gtk.combo_box_new_text()

            for entry in self.feedhamster.plugins_list():
                combo.append_text(entry)

            #combo.connect('changed', self.event_combo_feedtype)
            combo.set_active(0)
            combo.show()

            entry = gtk.Entry()
            entry.set_text(default)
            entry.show()
            d.vbox.pack_start(combo)
            d.vbox.pack_end(entry)
            entry.connect('activate', lambda _: d.response(gtk.RESPONSE_OK))
            d.set_default_response(gtk.RESPONSE_OK)
            r = d.run()
            
            url = entry.get_text().decode('utf8')
            model = combo.get_model()
            index = combo.get_active()
            addtype = model[index][0]
            if r == gtk.RESPONSE_OK:
                fid = self.feedhamster.feed_create(url,addtype)
                if fid:
                    feed = self.feedhamster.feed_get(fid)
                    self.ActionFeedViewBuild()
                    d.destroy()
                    self.ActionStatusBarPrint('Done')
                    time.sleep(1)
                    self.ActionStatusBarPrint('Ready')
                    break
                else:
                    d.destroy()
                    message = self.lng.getText('sub_feed_add','message2','Access to url not possible')
                    message = message or 'Error, No Feed Found:'
                    message += '\n%s'%url
                    parent = self.mainWindow
                    d = gtk.MessageDialog(parent,
                                        gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                        gtk.MESSAGE_ERROR,
                                        gtk.BUTTONS_OK,message)
                    d.set_default_response(gtk.RESPONSE_OK)
                    r = d.run()
                    d.destroy()
                    if r == gtk.RESPONSE_OK:
                        break
            else:
                d.destroy()
                self.ActionStatusBarPrint('Ready')
                break


    def EventFeedDelete(self, *args):
        tree_sel = self.feedView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        fid = (tm.get_value(ti, 1))
        feedObj = self.feedhamster.feed_get(fid)

        message = '%s\n%s'%(self.lng.getText('feeds','messagefeeddel','Really Delete:'),feedObj.url)
        parent = self.mainWindow

        d = gtk.MessageDialog(parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            gtk.MESSAGE_QUESTION,
                            gtk.BUTTONS_OK_CANCEL,message)
        d.set_default_response(gtk.RESPONSE_OK)
        r = d.run()
        d.destroy()
        if r == gtk.RESPONSE_OK:
            self.ActionStatusBarPrint('Deleting: %s'%fid)


            answer = self.feedhamster.feed_delete(fid)
            if not answer == True:

                textparts = answer.split('\n')


                dsub = gtk.MessageDialog(d,
                    gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                    gtk.MESSAGE_INFO,
                    gtk.BUTTONS_OK,answer)

                dsub.set_title('Error')

                dsub.set_default_response(gtk.BUTTONS_OK)
                r = dsub.run()
                dsub.destroy()
                return

            time.sleep(1)
            self.ActionFeedViewBuild()
            self.ActionStatusBarPrint('Ready')
            self.ActionFeedViewBuild()

    def EventSearchRun(self, widget):
        keyword = widget.get_text()
        tree_sel = tree_sel = self.feedView.get_selection()
        (tm, ti) = tree_sel.get_selected()
        fid = tm.get_value(ti, 1)

        self._NamedThread('Searching...',target=self.ActionMessageViewBuild, args=(fid,keyword))

    def EventComboChanged(self, widget, ctype):
        if ctype == 'count':
            self.comboCount = widget.get_active()
        if ctype == 'meta':
            self.comboMeta = widget.get_active()

        try:
            tree_sel = self.feedView.get_selection()
            (tm, ti) = tree_sel.get_selected()
            fid = tm.get_value(ti, 1)

            self._NamedThread('Rebuild Combo change...',target=self.ActionMessageViewBuild, args=(fid,))

        except:
            pass

    def EventFeedViewChanged(self, treeview):
        self.stopFeedViewColorChange = True
        tree_sel = treeview.get_selection()
        (tm, ti) = tree_sel.get_selected()
        fid = tm.get_value(ti, 1)
        if fid:
            for fuuid in self.feedOpenDates:
                feedObj = self.feedhamster.feed_get(fuuid)
                if feedObj != None:
                    feedObj.feed_set_newest_time_flag(self.feedOpenDates[fuuid][0])
                    self.feedOpenDates[fuuid][1].set_value(self.feedOpenDates[fuuid][2], 2, None)
            self.feedOpenDates = {}
            self.openFeed = fid
            self.log.debug('Selected Feed: %s'%fid)
            self._NamedThread('MessageBuild',target=self.ActionMessageViewBuild, args=(fid,))
            self.feedOpenDates[fid] = [int(time.time()),tm,ti]
            self.stopFeedViewColorChange = False

    def _NamedThread(self,name,**kwargs):
        td = threading.Thread(**kwargs)
        td.setName(name)
        td.start()

    #~ def _CountSyncs(self):
        #~ threads = threading.enumerate()
        #~ counter = 0
        #~ for th in threads:
            #~ if th.isAlive():
                #~ if 'update_thread' in th.getName():
                    #~ counter += 1
        #~ return counter

    def EventFeedViewClicked(self, treeview, event):

        self.workerQueue.put('changecolors')

        #~ if event.button == 1: # left click
            #~ help(treeview)
            #~ x = int(event.x)
            #~ y = int(event.y)
            #~ pthinfo = treeview.get_path_at_pos(x, y)
            #~ print pthinfo[1]
            #~ treeview.set_cursor_on_cell(pthinfo[1])


            #~ tree_sel = treeview.get_selection()
            #~ (tm, ti) = tree_sel.get_selected()

            #~ if ti == None:
                #~ return
                #~
#~
            #~
            #~
            #~ model = treeview.get_model()
            #~
            #~
            #~ if model.iter_has_child(ti):
                #~ path = tm.get_path(ti)
                #~ treeview.collapse_all()
                #~ if treeview.row_expanded(path):
                    #~ treeview.collapse_row(path)
                #~ else:
                    #~ treeview.expand_row(path,True)

        if event.button == 3: # right click
            tree_sel = treeview.get_selection()
            (tm, ti) = tree_sel.get_selected()
            fid = tm.get_value(ti, 1)
            self.summaryView.hide()
            x = int(event.x)
            y = int(event.y)
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                if fid:
                    self.FeedViewMenu.popup(None, None, None, event.button, event.time, None)
                    self.FeedViewMenu.show_all()
                return

    def EventMessageViewClicked(self, treeview, event):
        if event.button == 3: # right click
            model = treeview.get_model()
            if len(model) == 0:
                return

            self.NewsViewMenu.popup(None, None, None, event.button, event.time, None)
            self.NewsViewMenu.show_all()


        
if __name__ == "__main__":

    thisapp = singleton.singleinstance()
    
    logger = logging.getLogger()
    fmt_string = "[%(levelname)-7s]%(asctime)s.%(msecs)-3d\
    %(module)s[%(lineno)-3d]/%(funcName)-10s  %(message)-8s "
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt_string, "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    FeedHamsterGUI()
    gtk.main()
    sys.exit(0)


