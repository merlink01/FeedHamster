import sys
import gtk
import logging
import feedhamster_gtk

if __name__ == "__main__":
    thisapp = feedhamster_gtk.singleton.singleinstance()
    logger = logging.getLogger()
    fmt_string = "[%(levelname)-7s]%(asctime)s.%(msecs)-3d\
    %(module)s[%(lineno)-3d]/%(funcName)-10s  %(message)-8s "
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt_string, "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    feedhamster_gtk.FeedHamsterGUI()
    gtk.main()
    sys.exit(0)
