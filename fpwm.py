#!/usr/bin/env python
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
import sys, os, signal
from   decimal import *

import xcb
from   xcb.xproto import *
import xcb.randr

from utils     import acquire_ext_clients, add_ext_clients, get_atoms, change_property, proper_disconnect
from workspace import Workspace
from screen    import Screen
from event     import event_sigterm, event_sigint, event_handler
from status    import StatusLine, Gap
from ctrl      import Keyboard, Mouse
from client    import Client

import runtime
import config


wmname = "fpwm"
runtime.ignored_windows = config.ignored_windows

runtime.con = xcb.connect()
runtime.viewport = runtime.con.get_setup().roots[0]
xrandr = runtime.con(xcb.randr.key)

runtime.con.core.GrabServer()
while runtime.con.poll_for_event():
    pass

try:
    runtime.con.core.ChangeWindowAttributesChecked(runtime.viewport.root, CW.EventMask, runtime.events).check()
except BadAccess, e:
    debug("A window manager is already running !\n")
    runtime.con.disconnect()
    sys.exit(1)

ext_clients = acquire_ext_clients()

reply = xrandr.GetScreenResources(runtime.viewport.root).reply()

if len(config.workspaces) < reply.num_crtcs:
    debug("Not enough workspaces\n")
    runtime.con.disconnect()
    sys.exit(1)

wm_atom_names = ["WM_STATE", "WM_CLASS"]
get_atoms(wm_atom_names, runtime.wm_atoms)

net_wm_atom_names = ["_NET_SUPPORTED", "_NET_SUPPORTING_WM_CHECK", "_NET_WM_NAME", "_NET_WM_PID"]
# "_NET_STARTUP_ID", "_NET_CLIENT_LIST", "_NET_CLIENT_LIST_STACKING", "_NET_NUMBER_OF_DESKTOPS",
# "_NET_CURRENT_DESKTOP", "_NET_DESKTOP_NAMES", "_NET_ACTIVE_WINDOW", "_NET_DESKTOP_GEOMETRY",
# "_NET_CLOSE_WINDOW", "_NET_WM_STRUT_PARTIAL", "_NET_WM_ICON_NAME", "_NET_WM_VISIBLE_ICON_NAME",
# "_NET_WM_DESKTOP", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DESKTOP", "_NET_WM_WINDOW_TYPE_DOCK",
# "_NET_WM_WINDOW_TYPE_TOOLBAR", "_NET_WM_WINDOW_TYPE_MENU", "_NET_WM_WINDOW_TYPE_UTILITY",
# "_NET_WM_WINDOW_TYPE_SPLASH", "_NET_WM_WINDOW_TYPE_DIALOG", "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU",
# "_NET_WM_WINDOW_TYPE_POPUP_MENU", "_NET_WM_WINDOW_TYPE_TOOLTIP", "_NET_WM_WINDOW_TYPE_NOTIFICATION",
# "_NET_WM_WINDOW_TYPE_COMBO", "_NET_WM_WINDOW_TYPE_DND", "_NET_WM_WINDOW_TYPE_NORMAL", "_NET_WM_ICON",
# "_NET_WM_STATE", "_NET_WM_STATE_STICKY", "_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_FULLSCREEN",
# "_NET_WM_STATE_MAXIMIZED_HORZ", "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_ABOVE",
# "_NET_WM_STATE_BELOW", "_NET_WM_STATE_MODAL", "_NET_WM_STATE_HIDDEN", "_NET_WM_STATE_DEMANDS_ATTENTION"

get_atoms(net_wm_atom_names, runtime.net_wm_atoms)

change_property(PropMode.Replace, runtime.viewport.root, runtime.net_wm_atoms["_NET_SUPPORTED"],
                Atom.ATOM, 32, len(runtime.net_wm_atoms), runtime.net_wm_atoms.itervalues())

wm_win = runtime.con.generate_id()
runtime.con.core.CreateWindow(runtime.viewport.root_depth, wm_win, runtime.viewport.root,
                              -1,-1,1,1,0, WindowClass.CopyFromParent, runtime.viewport.root_visual, 0, [])

change_property(PropMode.Replace, runtime.viewport.root, runtime.net_wm_atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, wm_win)
change_property(PropMode.Replace, wm_win, runtime.net_wm_atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, wm_win)
change_property(PropMode.Replace, wm_win, runtime.net_wm_atoms["_NET_WM_NAME"], Atom.STRING, 8, len(wmname), wmname)
change_property(PropMode.Replace, wm_win, runtime.net_wm_atoms["_NET_WM_PID"], Atom.CARDINAL, 32, 1, os.getpid())

fp_wm_atom_names = ["_FP_WM_WORKSPACE"]
get_atoms(fp_wm_atom_names, runtime.fp_wm_atoms)

for w in config.workspaces:
    runtime.workspaces.append(Workspace(runtime.con, runtime.viewport, w, config.layouts))

runtime.status_line = StatusLine(config.pretty_print, Gap(h=config.gap_height, top=config.gap_top))

w = 0
screen_ids = unpack_from("%dI" % reply.num_crtcs, reply.crtcs.buf())
for sid in screen_ids:
    reply = xrandr.GetCrtcInfo(sid,0).reply()
    if reply.width == 0 or reply.height == 0:
        continue
    if reply.x == runtime.status_line.gap.x:
        gap = runtime.status_line.gap
    else:
        gap = None
    scr = Screen(runtime.viewport, reply.x, reply.y, reply.width, reply.height, runtime.workspaces, gap)
    runtime.focused_screen = scr
    scr.set_workspace(runtime.workspaces[w])
    runtime.screens.append(scr)
    w += 1

add_ext_clients(ext_clients, Client)

for w in runtime.workspaces:
    if w.screen is not None:
        w.update()
    else:
        w.set_passive()

runtime.con.core.UngrabServer()
runtime.con.flush()
while runtime.con.poll_for_event():
    pass

runtime.keyboard = Keyboard(runtime.con)
runtime.mouse = Mouse(runtime.con)

runtime.keyboard.attach(config.keyboard_bindings, runtime.viewport.root)
runtime.mouse.attach(config.mouse_bindings, runtime.viewport.root)

signal.signal(signal.SIGTERM, event_sigterm)
signal.signal(signal.SIGINT, event_sigint)

while True:
    try:
        event_handler(runtime.con.wait_for_event())
        runtime.con.flush()
    except Exception, error:
        proper_disconnect("main: %s\n" % error.__class__.__name__)
