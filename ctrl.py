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

class Keyboard:
    def __init__(self, con):
        self.__con = con
        self.__bindings = {}

    def attach(self, bindings, root):
        self.__root = root
        for m,k,f in bindings:
            if m is None:
                raise ValueError("missing modifier in keyboard bindings")

            if not self.__bindings.has_key(k):
                self.__bindings[k] = {}

            self.__bindings[k][m] = f
            self.__con.core.GrabKey(False, self.__root, m, k, GrabMode.Async, GrabMode.Async)

    def detach(self):
        self.__con.core.UngrabKey(False, self.__root, ModMask.Any)

    def press(self, event):
        debug("key press 0x%x: %r\n" % (event.child, event.__dict__))
        self.__bindings[event.detail][event.state]()

    def release(self, event):
        debug("key release 0x%x: %r\n" % (event.child, event.__dict__))

class Mouse:
    def __init__(self, con):
        self.__con = con
        self.__acting = None
        self.__c = None
        self.__x = 0
        self.__y = 0
        self.__up = False
        self.__left = False
        self.__bindings = {}

    def attach(self, bindings, root):
        self.__root = root
        for m,b,f in bindings:
            if m is None:
                raise ValueError("missing modifier in mouse bindings")

            if not self.__bindings.has_key(b):
                self.__bindings[b] = {}

            self.__bindings[b][m] = f

            bmask = eval("EventMask.Button%dMotion" % b)
            emask = EventMask.ButtonPress|EventMask.ButtonRelease|bmask
            self.__con.core.GrabButton(False, self.__root, emask, GrabMode.Async, GrabMode.Async, 0, 0, b, m)

    def detach(self):
        self.__con.core.UngrabButton(False, self.__root, ButtonMask.Any)

    def motion(self, event):
        if self.__acting is None:
            return

        dx = event.root_x - self.__x
        dy = event.root_y - self.__y

        self.__acting(self.__c, self.__up, self.__left, dx, dy)

        self.__x = event.event_x
        self.__y = event.event_y

    def press(self, event):
        debug("button press 0x%x: %r\n" % (event.child, event.__dict__))
        if self.__acting is not None or event.child == 0:
            return

        wk = current_workspace()
        self.__c = wk.get_client(event.child)
        if self.__c is None:
            return

        self.__c.stack_above()
        self.__acting = self.__bindings[event.detail][event.state]
        self.__x = event.root_x
        self.__y = event.root_y

        if self.__x - wk.screen.x < self.__c.geo_virt.x+(2*self.__c.geo_virt.b+self.__c.geo_virt.w)/2:
            self.__left = True
        else:
            self.__left = False

        if self.__y - wk.screen.y < self.__c.geo_virt.y+(2*self.__c.geo_virt.b+self.__c.geo_virt.h)/2:
            self.__up = True
        else:
            self.__up = False

    def release(self, event):
        debug("button release 0x%x: %r\n" % (event.child, event.__dict__))
        set_current_screen_at(Geometry(event.root_x, event.root_y))

        if self.__acting is None:
            return

        owk = self.__c.workspace
        nwk = current_workspace()
        if nwk != owk and self.__c.located_into(nwk):
            owk.detach(self.__c)
            nwk.attach(self.__c)

        if self.__c.tiled:
            self.__c.stack_below()

        self.__acting = None
