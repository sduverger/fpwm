#
# Copyright (C) 2012 stephane duverger
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
import sys
from   xcb.xproto import *

import runtime

class Geometry:
    def __init__(self, x=0, y=0, w=0, h=0, b=1):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.b = b

    def copy(self):
        return Geometry(self.x, self.y, self.w, self.h, self.b)

class KeyMap:
    up             = 111
    down           = 116
    left           = 113
    right          = 114
    pause          = 127
    tab            = 23
    space          = 65
    square         = 49
    a              = 24
    z              = 25
    e              = 26
    r              = 27
    t              = 28
    y              = 29
    u              = 30
    i              = 31
    o              = 32
    p              = 33
    q              = 38
    s              = 39
    d              = 40
    f              = 41
    g              = 42
    h              = 43
    j              = 44
    k              = 45
    l              = 46
    m              = 47
    w              = 52
    x              = 53
    c              = 54
    v              = 55
    b              = 56
    n              = 57
    n1             = 10
    n2             = 11
    n3             = 12
    n4             = 13
    n5             = 14
    n6             = 15
    n7             = 16
    n8             = 17
    n9             = 18
    n0             = 19

    mod_shift      = KeyButMask.Shift
    mod_ctrl       = KeyButMask.Control
    mod_alt        = KeyButMask.Mod1
    mod_win        = KeyButMask.Mod4
    mod_altgr      = KeyButMask.Mod5

def debug(msg):
    if runtime.debug:
        sys.stderr.write(msg)

def vanilla_configure_window_request(event):
    values = []
    if event.value_mask & ConfigWindow.X:
        values.append(event.x)
    if event.value_mask & ConfigWindow.Y:
        values.append(event.y)
    if event.value_mask & ConfigWindow.Width:
        values.append(event.width)
    if event.value_mask & ConfigWindow.Height:
        values.append(event.height)
    if event.value_mask & ConfigWindow.BorderWidth:
        values.append(event.border_width)
    if event.value_mask & ConfigWindow.Sibling:
        values.append(event.sibling)
    if event.value_mask & ConfigWindow.StackMode:
        values.append(event.stack_mode)

    runtime.con.core.ConfigureWindow(event.window, event.value_mask, values)

def get_client_classes(cid):
    r = runtime.con.core.GetProperty(False, cid, runtime.wm_atoms["WM_CLASS"], Atom.STRING, 0, 20).reply()
    if r.value_len == 0:
        return []
    return str(r.value.buf()).split('\x00')

def ignored_client(cid):
    classes = get_client_classes(cid)
    if len(classes) == 0:
        return (False, "")

    if len(classes) > 1:
        if classes[1] in runtime.ignored_windows:
            return (True, classes[1])
        if classes[0] in runtime.ignored_windows:
            return (True, classes[0])
    return (False, classes[0])

def acquire_ext_clients():
    clients = []
    reply = runtime.con.core.QueryTree(runtime.viewport.root).reply()
    if reply.children_len == 0:
        debug("no ext client found\n")
        return clients
    children = unpack_from("%dI" % reply.children_len, reply.children.buf())
    for cid in children:
        cls = get_client_classes(cid)
        if len(cls) > 1 and cls[1] == "QuakeConsole":
            runtime.quake_console = cid
            geo = runtime.con.core.GetGeometry(cid).reply()
            runtime.quake_console_geometry = Geometry(geo.x, geo.y, geo.width, geo.height)
            continue

        wa = runtime.con.core.GetWindowAttributes(cid).reply()
        if wa.map_state == MapState.Unmapped or wa.override_redirect:
            continue

        clients.append(cid)

    return clients

def get_screen_at(geo):
    for s in runtime.screens:
        if geo.x >= s.x and geo.x < s.x+s.width:
            return s

def add_ext_clients(ext_clients, client_builder):
    for cid in ext_clients:
        geo = runtime.con.core.GetGeometry(cid).reply()
        gm = Geometry(geo.x, geo.y, geo.width, geo.height)
        debug("ext client at x %d y %d w %d h %d b %d\n" % (gm.x, gm.y, gm.w, gm.h, gm.b))

        r = runtime.con.core.GetProperty(False, cid, runtime.fp_wm_atoms["_FP_WM_WORKSPACE"], Atom.STRING, 0, 10).reply()
        lost_client = True
        if r.value_len != 0:
            for w in runtime.workspaces:
                if w.name == str(r.value.buf()):
                    wk = w
                    lost_client = False
                    break

        if lost_client:
            sc = get_screen_at(gm)
            if sc is None:
                gm.x = 0
                gm.y = 0
                gm.w = 320
                gm.h = 240
                sc = get_screen_at(gm)
            wk = sc.active_workspace

        cl = client_builder(runtime.con, cid, runtime.viewport.root, wk, gm)
        runtime.clients[cid] = cl
        wk.add(cl)
        debug("acquired client 0x%x\n" % cid)

def release_clients():
    for c in runtime.clients.itervalues():
        runtime.con.core.ReparentWindow(c.id, runtime.viewport.root, c.geo_virt.x, c.geo_virt.y)
        c.send_config_window(c.geo_virt)

    if runtime.quake_console is not None:
        runtime.con.core.ReparentWindow(runtime.quake_console, runtime.viewport.root,
                                        runtime.quake_console_geometry.x, runtime.quake_console_geometry.y)
        configure_window(runtime.quake_console, runtime.quake_console_geometry)

def flat(format, data):
    f={32:'I',16:'H',8:'B'}[format]
    if not hasattr(data, "__iter__") and not hasattr(data, "__getitem__"):
        data = [data]
    return array(f, data).tostring()

def change_property(mode, window, property, type, format, data_len, data):
    runtime.con.core.ChangeProperty(mode, window, property, type, format, data_len, flat(format, data))

def stack_window(wid, mode):
    runtime.con.core.ConfigureWindow(wid, ConfigWindow.StackMode, [mode])

def configure_window(wid, geo):
    debug("configure 0x%x: x %d y %d w %d h %d\n" % (wid, geo.x, geo.y, geo.w, geo.h))
    mask = ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height|ConfigWindow.BorderWidth
    pkt = pack('=xx2xIH2xiiIII', wid, mask, geo.x, geo.y, geo.w, geo.h, geo.b)
    runtime.con.core.send_request(xcb.Request(pkt, 12, True, False), xcb.VoidCookie())

def map_window(wid, state):
    change_property(PropMode.Replace, wid, runtime.wm_atoms["WM_STATE"], Atom.CARDINAL, 32, 1, state)
    runtime.con.core.MapWindow(wid)

def get_atoms(names, store):
    for n in names:
        store[n] = runtime.con.core.InternAtom(False, len(n), n)
    for n in store:
        store[n] = store[n].reply().atom

def proper_disconnect(msg):
    sys.stderr.write("%s\n" % msg)
    release_clients()
    runtime.mouse.detach()
    runtime.keyboard.detach()
    runtime.con.flush()
    runtime.con.disconnect()

# Xephyr bug: KeyButMask.Mod2 always
# def xhephyr_fix(x):
#     for n in range(len(x)):
#         x[n] = (x[n][0]|KeyButMask.Mod2, x[n][1], x[n][2])
