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
from   utils   import debug, Geometry, proper_disconnect, vanilla_configure_window_request, ignored_client
from   api     import set_current_screen_from, current_workspace
from   client  import Client

def event_sigterm(signum, frame):
    proper_disconnect("received SIGTERM")
    sys.exit(0)

def event_sigint(signum, frame):
    proper_disconnect("received SIGINT")
    sys.exit(0)

def event_enter_notify(event):
    debug("enter notify 0x%x: %r\n" % (event.event, event.__dict__))

    cl = runtime.clients.get(event.event)
    if cl is None:
        return

    if runtime.ignore_next_enter_notify:
        runtime.ignore_next_enter_notify = False
        debug("** ignored **\n")
        return

    if not set_current_screen_from(cl.workspace.screen):
        debug("no screen for client 0x%x on workspace %s\n" % (cl.id, cl.workspace.name))
        return

    current_workspace().update_focus(cl)

def event_configure_window_request(event):
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is None:
        vanilla_configure_window_request(event)
    else:
        cl.configure(event)

def event_map_window(event):
    debug("map request: %r\n" % event.__dict__)
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is None:
        if ignored_client(event.window):
            gmx = runtime.con.core.GetGeometry(event.window).reply()
            geo = Geometry(gmx.x, gmx.y, gmx.width, gmx.height, 1)
            ignored = True
        else:
            geo = None
            ignored = False

        cl = Client(runtime.con, event.window, event.parent, wk, geo, ignored)
        runtime.clients[cl.id] = cl
        wk.add(cl)

    wk.map(cl)
    current_workspace().update_focus(cl)

def event_destroy_notify(event):
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is not None:
        debug("destroy client %d\n" % event.window)
        if cl.tiled:
            wk.untile(cl)
        wk.remove(cl)
        runtime.clients.__delitem__(cl.id)

# def event_reparent_notify(event):
    # wk = current_workspace()
    # cl = scr.get_client(event.window)
    # evt = pack("=B3xIIIHH3x",
    #            21, event.event, event.window, event.parent,
    #            cl.geo_virt.x, cl.geo_virt.y)
    # runtime.con.core.SendEvent(False, event.window, EventMask.StructureNotify, evt)

def event_key_press(event):
    runtime.keyboard.press(event)

def event_key_release(event):
    runtime.keyboard.release(event)

def event_motion_notify(event):
    runtime.mouse.motion(event)

def event_button_press(event):
    runtime.mouse.press(event)

def event_button_release(event):
    runtime.mouse.release(event)

def event_property_notify(event):
    debug("PropertyNotify %s: %s\n" % (runtime.con.core.GetAtomName(event.atom).reply().name.buf(), event.__dict__))

event_handlers = { EnterNotifyEvent:event_enter_notify,
                   ConfigureRequestEvent:event_configure_window_request,
                   MapRequestEvent:event_map_window,
                   DestroyNotifyEvent:event_destroy_notify,
                   KeyPressEvent:event_key_press,
                   KeyReleaseEvent:event_key_release,
                   MotionNotifyEvent:event_motion_notify,
                   ButtonPressEvent:event_button_press,
                   ButtonReleaseEvent:event_button_release,
                   PropertyNotifyEvent:event_property_notify,
                   }

def event_handler(event):
    hdl = event_handlers.get(event.__class__, None)
    if hdl is not None:
        debug("--> %s\n" % event.__class__.__name__)
        hdl(event)
    else:
        debug("** Unhandled event ** %r %r\n" % (event.__class__.__name__, event.__dict__))
