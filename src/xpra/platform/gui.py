# This file is part of Xpra.
# Copyright (C) 2010 Nathaniel Smith <njs@pobox.com>
# Copyright (C) 2012-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import sys

_init_done = False
def init():
    #warning: we currently call init() from multiple places to try
    #to ensure we run it as early as possible..
    global _init_done
    if not _init_done:
        _init_done = True
        do_init()

def do_init():
    pass

_ready_done = False
def ready():
    global _ready_done
    if not _ready_done:
        _ready_done = True
        do_ready()

def do_ready():
    pass


#defaults:
def get_native_tray_menu_helper_classes():
    #classes that generate menus for xpra's system tray
    #let the toolkit classes use their own
    return []
def get_native_tray_classes(*args):
    #the classes we can use for our system tray:
    #let the toolkit classes use their own
    return []
def get_native_system_tray_classes(*args):
    #the classes we can use for application system tray forwarding:
    #let the toolkit classes use their own
    return []
def system_bell(*args):
    #let the toolkit classes use their own
    return False
def get_native_notifier_classes():
    return []


def get_antialias_info():
    return {}

def get_workarea():
    return None

def get_vrefresh():
    return -1

def get_double_click_time():
    return -1

def get_double_click_distance():
    return -1, -1


def add_window_hooks(window):
    pass

def remove_window_hooks(window):
    pass


def gl_check():
    return None     #no problem

take_screenshot = None
ClientExtras = None


def get_info_base():
    def fname(v):
        try:
            return v.__name__
        except:
            return str(v)
    def fnames(l):
        return [fname(x) for x in l]
    return {
            "native_tray_menu_helpers"      : fnames(get_native_tray_menu_helper_classes()),
            "native_trays"                  : fnames(get_native_tray_classes()),
            "native_system_trays"           : fnames(get_native_system_tray_classes()),
            "system_bell"                   : fname(system_bell),
            "native_notifiers"              : fnames(get_native_notifier_classes()),
            "workarea"                      : get_workarea() or "",
            "antialias"                     : get_antialias_info(),
            "vertical-refresh"              : get_vrefresh(),
            "double_click.time"             : get_double_click_time(),
            "double_click.distance"         : get_double_click_distance(),
            }
get_info = get_info_base


from xpra.platform import platform_import
platform_import(globals(), "gui", False,
                "do_ready",
                "do_init",
                "gl_check",
                "ClientExtras",
                "take_screenshot",
                "get_native_tray_menu_helper_classes",
                "get_native_tray_classes",
                "get_native_system_tray_classes",
                "get_native_notifier_classes",
                "get_vrefresh", "get_workarea", "get_antialias_info",
                "get_double_click_time", "get_double_click_distance",
                "add_window_hooks", "remove_window_hooks",
                "system_bell",
                "get_info")


def main():
    from xpra.platform import init as platform_init,clean
    from xpra.util import nonl
    try:
        platform_init("GUI-Properties")
        init()
        verbose = "-v" in sys.argv or "--verbose" in sys.argv
        if verbose:
            from xpra.log import get_all_loggers
            for x in get_all_loggers():
                x.enable_debug()

        #naughty, but how else can I hook this up?
        import os
        if os.name=="posix":
            try:
                from xpra.x11.gtk_x11 import gdk_display_source
                assert gdk_display_source
            except:
                from xpra.x11.gtk3_x11 import gdk_display_source    #@Reimport
                assert gdk_display_source

        i = get_info()
        for k in sorted(i.keys()):
            v = i[k]
            print("* %s : %s" % (k.ljust(32), nonl(v)))
    finally:
        clean()


if __name__ == "__main__":
    sys.exit(main())
