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

from utils     import acquire_ext_clients, add_ext_clients, release_clients, get_atoms, change_property, proper_disconnect, debug
from workspace import Workspace
from screen    import Screen
from event     import event_sigterm, event_sigint, event_sighup, event_handler
from status    import StatusLine, Gap
from ctrl      import Keyboard, Mouse
from client    import Client

import runtime
import config

def startup():
    connect()
    lock()

    register_events()
    register_properties()

    setup()
    unlock()
    run()

def restart():
    release_clients()
    runtime.mouse.detach()
    runtime.keyboard.detach()

    runtime.clients.clear()
    runtime.workspaces[:] = []
    runtime.screens[:] = []

    reload(config)
    lock()
    setup()
    unlock()
    runtime.need_restart = False

def connect():
    runtime.con = xcb.connect()
    runtime.viewport = runtime.con.get_setup().roots[0]
    runtime.xrandr = runtime.con(xcb.randr.key)

    runtime.keyboard = Keyboard(runtime.con)
    runtime.mouse = Mouse(runtime.con)

def lock():
    runtime.con.core.GrabServer()
    while runtime.con.poll_for_event():
        pass

def unlock():
    runtime.con.core.UngrabServer()
    runtime.con.flush()
    while runtime.con.poll_for_event():
        pass

def register_events():
    try:
        runtime.con.core.ChangeWindowAttributesChecked(runtime.viewport.root, CW.EventMask, runtime.events).check()
    except BadAccess, e:
        debug("A window manager is already running !\n")
        runtime.con.disconnect()
        sys.exit(1)

    runtime.xrandr.SelectInput(runtime.viewport.root, xcb.randr.NotifyMask.ScreenChange)

    signal.signal(signal.SIGTERM, event_sigterm)
    signal.signal(signal.SIGINT, event_sigint)
    signal.signal(signal.SIGHUP, event_sighup)

def register_properties():
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

    change_property(PropMode.Replace, runtime.viewport.root,
                    runtime.net_wm_atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, wm_win)
    change_property(PropMode.Replace, wm_win,
                    runtime.net_wm_atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, wm_win)
    change_property(PropMode.Replace, wm_win,
                    runtime.net_wm_atoms["_NET_WM_NAME"], Atom.STRING, 8, len(runtime.wmname), runtime.wmname)
    change_property(PropMode.Replace, wm_win,
                    runtime.net_wm_atoms["_NET_WM_PID"], Atom.CARDINAL, 32, 1, os.getpid())

    fp_wm_atom_names = ["_FP_WM_WORKSPACE"]
    get_atoms(fp_wm_atom_names, runtime.fp_wm_atoms)

def build_status():
    if hasattr(config, "gap_x"):
        cx=config.gap_x
    else:
        cx=0
    if hasattr(config, "gap_height"):
        ch=config.gap_height
    else:
        ch=0
    if hasattr(config, "gap_top"):
        ct=config.gap_top
    else:
        ct=True

    runtime.status_line = StatusLine(config.pretty_print, Gap(x=cx, h=ch, top=ct))

def setup():
    runtime.focused_color = config.focused_color
    runtime.passive_color = config.passive_color

    runtime.ignored_windows = config.ignored_windows
    runtime.pointer_follow = config.pointer_follow

    runtime.keyboard.bind(config.keyboard_bindings)
    runtime.mouse.bind(config.mouse_bindings)

    reply = runtime.xrandr.GetScreenResources(runtime.viewport.root).reply()

    if len(config.workspaces) < reply.num_crtcs:
        debug("Not enough workspaces\n")
        runtime.con.disconnect()
        sys.exit(1)

    ext_clients = acquire_ext_clients()

    for w in config.workspaces:
        runtime.workspaces.append(Workspace(runtime.con, runtime.viewport, w, config.layouts))

    build_status()

    w = 0
    screen_ids = unpack_from("%dI" % reply.num_crtcs, reply.crtcs.buf())
    for sid in screen_ids:
        reply = runtime.xrandr.GetCrtcInfo(sid,0).reply()
        if reply.width == 0 or reply.height == 0:
            continue
        if reply.x == runtime.status_line.gap.x:
            gap = runtime.status_line.gap
        else:
            gap = None
            debug("screen: x %d y %d w %d h %d\n" % (reply.x, reply.y, reply.width, reply.height))

        duplicate = False
        for s in runtime.screens:
            if reply.x == s.x:
                duplicate = True
                break

        if duplicate:
            continue

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

    runtime.keyboard.attach(runtime.viewport.root)
    runtime.mouse.attach(runtime.viewport.root)

def run():
    while True:
        try:
            event = runtime.con.wait_for_event()
        except Exception, error:
            proper_disconnect("main: %s\n" % error.__class__.__name__)

        event_handler(event)
        runtime.con.flush()

        if runtime.need_restart:
            restart()

#
# main
#
startup()
