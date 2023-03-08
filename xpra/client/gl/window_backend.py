#!/usr/bin/env python3
# This file is part of Xpra.
# Copyright (C) 2018-2021 Antoine Martin <antoine@xpra.org>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import sys
import os.path
from io import BytesIO
from math import cos, sin

from xpra.util import typedict, envint, AdHocStruct, AtomicInteger
from xpra.os_util import WIN32
from xpra.log import Logger
PYTHON3 = True

log = Logger("opengl", "paint")


def get_opengl_backends(option_str):
    parts = option_str.split(":")
    if len(parts)==2:
        backend_str = parts[1]
    else:
        backend_str = option_str
    if backend_str in ("native", "gtk") or backend_str.find(",")>0:
        return backend_str.split(",")
    if PYTHON3:
        return ("native", )
    return ("native", "gtk")

def get_gl_client_window_module(backends, force_enable=False):
    #backends = ["native", "gtk"]
    gl_client_window_module = None
    for impl in backends:
        log("attempting to load '%s' OpenGL backend", impl)
        GL_CLIENT_WINDOW_MODULE = "xpra.client.gl.gtk%s.%sgl_client_window" % (sys.version_info[0], impl)
        log("importing %s", GL_CLIENT_WINDOW_MODULE)
        try:
            gl_client_window_module = __import__(GL_CLIENT_WINDOW_MODULE, {}, {}, ["GLClientWindow", "check_support"])
        except ImportError as e:
            log("cannot import %s", GL_CLIENT_WINDOW_MODULE, exc_info=True)
            log.warn("Warning: cannot import %s OpenGL module", impl)
            log.warn(" %s", e)
            del e
            continue
        log("%s=%s", GL_CLIENT_WINDOW_MODULE, gl_client_window_module)
        opengl_props = gl_client_window_module.check_support(force_enable)
        log("check_support(%s)=%s", force_enable, opengl_props)
        if opengl_props:
            return opengl_props, gl_client_window_module
    log("get_gl_client_window_module(%s, %s) no match found", backends, force_enable)
    return {}, None

def noop(*_args):
    pass
def no_scaling(*args):
    return args
def get_None(*_args):
    return None
def no_idle_add(fn, *args, **kwargs):
    fn(*args, **kwargs)
def no_timeout_add(*_args, **_kwargs):
    raise Exception("timeout_add should not have been called")
def no_source_remove(*_args, **_kwargs):
    raise Exception("source_remove should not have been called")

class FakeClient(AdHocStruct):
    def __init__(self):
        self.sp = self.sx = self.sy = self.srect = no_scaling
        self.cx = self.cy = no_scaling
        self.xscale = self.yscale = 1
        self.server_window_decorations = True
        self.mmap_enabled = False
        self.mmap = None
        self.readonly = False
        self.encoding_defaults = {}
        self.get_window_frame_sizes = get_None
        self._focused = None
        self._remote_server_mode = "seamless"
        self.wheel_smooth = False
        self.pointer_grabbed = None
        def noop(*_args):
            """ pretend this method exists and does something """
        self.find_window = noop
        self.request_frame_extents = noop
        self.server_window_states = ()
        self.server_window_frame_extents = False
        self.server_readonly = False
        self.server_pointer = False
        self.window_configure_pointer = True
        self.update_focus = noop
        self.handle_key_action = noop
        self.window_ungrab = noop
        self.idle_add = no_idle_add
        self.timeout_add = no_timeout_add
        self.source_remove = no_source_remove
        self.wheel_smooth = False
        self.pointer_grabbed = False

    def find_window(self, *args):
        return None
    def window_ungrab(self, *args):
        pass

    def send(self, *args):
        log("send%s", args)
    def get_current_modifiers(self):
        return ()
    def get_raw_mouse_position(self):
        return 0, 0
    def get_mouse_position(self):
        return 0, 0
    def server_ok(self):
        return True
    def mask_to_names(self, *_args):
        return ()

def test_gl_client_window(gl_client_window_class, max_window_size=(1024, 1024), pixel_depth=24, show=False):
    #try to render using a temporary window:
    draw_result = {}
    window = None
    try:
        x, y = -100, -100
        if show:
            x, y = 100, 100
        w, h = 250, 250
        from xpra.codecs.loader import load_codec
        load_codec("dec_pillow")
        from xpra.client.window_border import WindowBorder
        border = WindowBorder()
        default_cursor_data = None
        noclient = FakeClient()
        #test with alpha, but not on win32
        #because we can't do alpha on win32 with opengl
        metadata = typedict({b"has-alpha" : not WIN32})
        window = gl_client_window_class(noclient, None, None, 2**32-1, x, y, w, h, w, h,
                                        metadata, False, typedict({}),
                                        border, max_window_size, default_cursor_data, pixel_depth)
        window_backing = window._backing
        window_backing.idle_add = no_idle_add
        window_backing.timeout_add = no_timeout_add
        window_backing.source_remove = no_source_remove
        window.realize()
        window_backing.paint_screen = True
        pixel_format = "BGRX"
        bpp = len(pixel_format)
        options = typedict({"pixel_format" : pixel_format})
        stride = bpp*w
        coding = "rgb32"
        widget = window_backing._backing
        widget.realize()
        def paint_callback(success, message):
            log("paint_callback(%s, %s)", success, message)
            draw_result.update({
                "success"   : success,
                "message"   : message.replace("\n", " "),
                })
        log("OpenGL: testing draw on %s widget %s with %s : %s", window, widget, coding, pixel_format)
        pix = AtomicInteger(0x7f)
        REPAINT_DELAY = envint("XPRA_REPAINT_DELAY", 0)
        def draw():
            if PYTHON3:
                img_data = bytes([pix.increase() % 256]*stride*h)
            else:
                img_data = chr(pix.increase() % 256)*stride*h
            window.draw_region(0, 0, w, h, coding, img_data, stride, 1, options, [paint_callback])
            return REPAINT_DELAY>0
        #the paint code is actually synchronous here,
        #so we can check the present_fbo() result:
        if show:
            widget.show()
            window.show()
            from xpra.gtk_common.gobject_compat import import_gtk, import_glib
            gtk = import_gtk()
            glib = import_glib()
            def window_close_event(*_args):
                gtk.main_quit()
            noclient.window_close_event = window_close_event
            glib.timeout_add(REPAINT_DELAY, draw)
            gtk.main()
        else:
            draw()
        if window_backing.last_present_fbo_error:
            return {
                "success" : False,
                "message" : "failed to present FBO on screen: %s" % window_backing.last_present_fbo_error
                }
    finally:
        if window:
            window.destroy()
    log("test_gl_client_window(..) draw_result=%s", draw_result)
    return draw_result or {"success" : False, "message" : "not painted on screen"}



def main(argv):
    try:
        if "-v" in argv or "--verbose" in argv:
            log.enable_debug()
        opengl_props, gl_client_window_module = get_gl_client_window_module(True)
        log("do_run_glcheck() opengl_props=%s, gl_client_window_module=%s", opengl_props, gl_client_window_module)
        gl_client_window_class = gl_client_window_module.GLClientWindow
        pixel_depth = 0
        log("do_run_glcheck() gl_client_window_class=%s, pixel_depth=%s", gl_client_window_class, pixel_depth)
        #if pixel_depth not in (0, 16, 24, 30) and pixel_depth<32:
        #    pixel_depth = 0
        draw_result = test_gl_client_window(gl_client_window_class, pixel_depth=pixel_depth, show=True)
        success = draw_result.pop("success", False)
        opengl_props.update(draw_result)
        if not success:
            opengl_props["safe"] = False
        return 0
    except Exception:
        log("do_run_glcheck(..)", exc_info=True)
        return 1

if __name__ == "__main__":
    r = main(sys.argv)
    sys.exit(r)
