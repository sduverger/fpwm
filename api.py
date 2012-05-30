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
import sys, os
from   xcb.xproto import *
from   utils import debug, get_screen_at, Geometry, configure_window, stack_window, set_input_focus
import runtime

def set_current_screen_at(geo):
    ns = get_screen_at(geo)
    if ns != runtime.focused_screen:
        runtime.focused_screen = ns
        update_workspace_info()

def set_current_screen_from(screen):
    if screen is None:
        return False

    if screen != runtime.focused_screen:
        runtime.focused_screen = screen
        update_workspace_info()

    return True

def current_screen():
    return runtime.focused_screen

def update_workspace_info():
    aw  = current_workspace()
    vw = []
    hw = []
    for w in runtime.workspaces:
        if w.screen is None:
            hw.append(w)
        elif w != aw:
            vw.append(w)

    runtime.status_line.update(aw, vw, hw)

def current_workspace():
    return current_screen().active_workspace

def current_client():
    return current_workspace().focused_client

def current_client_id():
    c = current_client()
    if c is None:
        return current_workspace().screen.root
    return c.id

def tile(c):
    if c is not None and not c.tiled:
        c.workspace.tile(c)

def untile(c):
    if c is not None and c.tiled:
        c.workspace.untile(c)

def tile_client():
    tile(current_client())

def untile_client():
    untile(current_client())

def move_client(c, up, left, dx, dy):
    if c is not None:
        untile(c)
        c.move(dx, dy)

def resize_client(c, up, left, dx, dy):
    if c is not None:
        untile(c)
        c.resize(up, left, dx, dy)

def next_layout():
    current_workspace().next_layout()

def toggle_show_desktop():
    wk = current_workspace()
    wk.toggle_desktop()

def toggle_fullscreen():
    wk = current_workspace()
    wk.toggle_fullscreen()

def get_workspace_with(wk1, stp):
    n = 0
    for w in runtime.workspaces:
        if w == wk1:
            break
        n += 1

    while True:
        n = (n+stp)%len(runtime.workspaces)
        wk2 = runtime.workspaces[n]
        if wk2 == wk1:
            return None
        if wk2.screen == None:
            return wk2

def get_workspace_at(n):
    if n >= len(runtime.workspaces):
        return None

    return runtime.workspaces[n]

def get_next_workspace_with(wk):
    return get_workspace_with(wk, 1)

def get_prev_workspace_with(wk):
    return get_workspace_with(wk, -1)

def send_to_workspace_with(nwk):
    c = current_client()
    if nwk is None or c is None:
        return

    cwk = c.workspace
    tiled = c.tiled

    debug("send_to_workspace %s -> %s\n" % (cwk.name, nwk.name))

    cwk.detach(c, tiled)
    nwk.attach(c, True)

    if nwk.screen is None:
        c.reparent(nwk.vroot, 0)
        update = False
    else:
        update = True

    if tiled:
        nwk.tile(c)
        c.stack_below()
    elif update:
        c.real_configure_notify()
        c.stack_above()

def send_to_workspace(n):
    wk = get_workspace_at(n)
    if wk is not None and wk != current_workspace():
        send_to_workspace_with(wk)

def send_to_next_workspace():
    send_to_workspace_with(get_next_workspace_with(current_workspace()))

def send_to_prev_workspace():
    send_to_workspace_with(get_prev_workspace_with(current_workspace()))

def goto_workspace(n):
    nwk = get_workspace_at(n)
    if nwk is not None:
        if nwk.screen is None:
            if nwk != current_workspace():
                debug("goto_workspace %s -> %s\n" % (current_workspace().name, nwk.name))
                current_screen().set_workspace(nwk)
        else:
            set_current_screen_from(nwk.screen)
            if nwk.focused_client is not None:
                debug("force focus on visible workspace %s\n" % nwk.name)
                nwk.focused_client.focus()

def next_workspace():
    nwk = get_next_workspace_with(current_workspace())
    if nwk is not None:
        debug("next_workspace %s -> %s\n" % (current_workspace().name, nwk.name))
        current_screen().set_workspace(nwk)

def prev_workspace():
    nwk = get_prev_workspace_with(current_workspace())
    if nwk is not None:
        debug("prev_workspace %s -> %s\n" % (current_workspace().name, nwk.name))
        current_screen().set_workspace(nwk)

def warp_pointer(c):
    if c is not None:
        runtime.con.core.WarpPointer(0, c.id, 0,0,0,0, c.geo_virt.w - 10, 10)

def next_client():
    current_workspace().next_client()
    if runtime.pointer_follow:
        warp_pointer(current_client())

def prev_client():
    current_workspace().prev_client()
    if runtime.pointer_follow:
        warp_pointer(current_client())

def layup_client():
    current_workspace().layup_client()

def laydown_client():
    current_workspace().laydown_client()

def increase_layout(stp):
    wk = current_workspace()
    wk.current_layout().increase(stp)
    wk.update()

def decrease_layout(stp):
    wk = current_workspace()
    wk.current_layout().decrease(stp)
    wk.update()

def spawn(*args):
    child = os.fork()
    if child != 0:
        os.waitpid(child, 0)
        return
    os.close(sys.stdout.fileno())
    if os.fork() != 0:
        os._exit(0)
    os.setsid()
    os.execl(args[0], *args)

def quakeconsole_show():
    geo = runtime.quake_console_geometry.copy()
    geo.x += current_screen().x
    configure_window(runtime.quake_console, geo)
    stack_window(runtime.quake_console, StackMode.Above)
    runtime.con.core.MapWindow(runtime.quake_console)
    current_workspace().update_focus(None)
    set_input_focus(runtime.quake_console)
    runtime.quake_console_toggle = True

def quakeconsole_hide():
    runtime.con.core.UnmapWindow(runtime.quake_console)
    runtime.quake_console_toggle = False

def quakeconsole(x,y,w,h):
    debug("quake console\n")
    if runtime.quake_console is None:
        spawn("/usr/bin/xterm","-class","QuakeConsole")
        runtime.quake_console_geometry = Geometry(x,y,w,h)
        runtime.quake_console_toggle = True
    elif runtime.quake_console_toggle:
        quakeconsole_hide()
    else:
        quakeconsole_show()
