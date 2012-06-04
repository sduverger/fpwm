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
from xcb.xproto import *

from utils import debug, Geometry
from api   import set_current_screen_at, current_workspace

class Controller:
    def __init__(self, con):
        self._con = con
        self._bindings = {}
        self._wid = None

    def bind(self, bindings):
        for m,k,f in bindings:
            if m is None:
                raise ValueError("missing modifier for binding")

            if not self._bindings.has_key(k):
                self._bindings[k] = {}

            self._bindings[k][m] = f

class Keyboard(Controller):
    def __init__(self, con):
        Controller.__init__(self, con)

    def attach(self, wid):
        self._wid = wid

        for k in self._bindings:
            for m in self._bindings[k]:
                self._con.core.GrabKey(False, self._wid, m, k, GrabMode.Async, GrabMode.Async)

    def detach(self):
        self._con.core.UngrabKey(False, self._wid, ModMask.Any)

    def press(self, event):
        debug("key press 0x%x: %r\n" % (event.child, event.__dict__))
        self._bindings[event.detail][event.state]()

    def release(self, event):
        debug("key release 0x%x: %r\n" % (event.child, event.__dict__))

class Mouse(Controller):
    def __init__(self, con):
        Controller.__init__(self, con)
        self._acting = None
        self._c = None
        self._x = 0
        self._y = 0
        self._up = False
        self._left = False

    def attach(self, wid):
        self._wid = wid

        for b in self._bindings:
            for m in self._bindings[b]:
                bmask = eval("EventMask.Button%dMotion" % b)
                emask = EventMask.ButtonPress|EventMask.ButtonRelease|bmask
                self._con.core.GrabButton(False, self._wid, emask, GrabMode.Async, GrabMode.Async, 0, 0, b, m)

    def detach(self):
        self._con.core.UngrabButton(False, self._wid, ButtonMask.Any)

    def motion(self, event):
        if self._acting is None:
            return

        dx = event.root_x - self._x
        dy = event.root_y - self._y

        self._acting(self._c, self._up, self._left, dx, dy)

        self._x = event.event_x
        self._y = event.event_y

    def press(self, event):
        debug("button press 0x%x: %r\n" % (event.child, event.__dict__))
        if self._acting is not None or event.child == 0:
            return

        wk = current_workspace()
        self._c = wk.get_client(event.child)
        if self._c is None:
            return

        self._c.stack_above()
        self._acting = self._bindings[event.detail][event.state]
        self._x = event.root_x
        self._y = event.root_y

        if self._x - wk.screen.x < self._c.geo_virt.x+(2*self._c.geo_virt.b+self._c.geo_virt.w)/2:
            self._left = True
        else:
            self._left = False

        if self._y - wk.screen.y < self._c.geo_virt.y+(2*self._c.geo_virt.b+self._c.geo_virt.h)/2:
            self._up = True
        else:
            self._up = False

    def release(self, event):
        debug("button release 0x%x: %r\n" % (event.child, event.__dict__))
        set_current_screen_at(Geometry(event.root_x, event.root_y))

        if self._acting is None:
            return

        owk = self._c.workspace
        nwk = current_workspace()
        if nwk != owk and self._c.located_into(nwk):
            owk.detach(self._c)
            nwk.attach(self._c)

        if self._c.tiled:
            self._c.stack_below()

        self._acting = None
