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

from   utils import Geometry, change_property, debug, configure_window, map_window, stack_window
import config
import runtime

class Client:
    def __init__(self, con, window, parent, workspace, geometry=None, ignored=False):
        self.__con = con
        self.id = window
        self.parent = parent
        self.__min_w = 20
        self.__min_h = 20
        if geometry is None:
            self.geo_virt = Geometry(0,0, self.__min_w, self.__min_w, 1)
            self.geo_want = Geometry(0,0, self.__min_w, self.__min_w, 1)
        else:
            self.geo_virt = geometry.copy()
            self.geo_want = geometry.copy()

        self.geo_unmax = None
        self.border_color = config.passive_color
        self.tiled = False
        if ignored:
            self.never_tiled = False
        else:
            self.never_tiled = True

        self.__set_workspace(workspace)
        self.__setup()

    def __set_workspace(self, workspace):
        self.workspace = workspace
        change_property(PropMode.Replace, self.id, runtime.fp_wm_atoms["_FP_WM_WORKSPACE"], Atom.STRING, 8,
                        len(self.workspace.name), self.workspace.name)

    def __setup(self):
        mask  = EventMask.EnterWindow|EventMask.PropertyChange|EventMask.FocusChange
        self.__con.core.ChangeWindowAttributes(self.id, CW.BorderPixel|CW.EventMask, [self.border_color,mask])

    def relative_geometry(self):
        return self.geo_virt.copy()

    def absolute_geometry(self):
        return Geometry(self.geo_virt.x+self.workspace.screen.x, self.geo_virt.y+self.workspace.screen.y,
                        self.geo_virt.w, self.geo_virt.h, self.geo_virt.b)

    def located_into(self, workspace):
        geo_abs = self.absolute_geometry()
        screen = workspace.screen
        if geo_abs.x >= screen.x and geo_abs.x < screen.x+screen.width:
            return True
        return False

    def move(self, dx, dy):
        self.geo_virt.x += dx
        self.geo_virt.y += dy
        self.real_configure_notify()

    def resize(self, up, left, dx, dy):
        if up:
            my = min(dy, self.geo_virt.h - self.__min_h)
            ry = -my
        else:
            my = 0
            ry = max(dy, self.__min_h - self.geo_virt.h)

        if left:
            mx = min(dx, self.geo_virt.w - self.__min_w)
            rx = -mx
        else:
            mx = 0
            rx = max(dx, self.__min_w - self.geo_virt.w)

        if rx == 0 and ry == 0:
            return

        if mx != 0 or my != 0:
            self.move(mx, my)

        self.geo_virt.w += rx
        self.geo_virt.h += ry
        self.real_configure_notify()

    def focus(self):
        self.border_color = config.focused_color
        self.update_border_color()
        self.__con.core.SetInputFocus(InputFocus.PointerRoot, self.id, InputFocus._None)

    def unfocus(self):
        self.border_color = config.passive_color
        self.update_border_color()

    def update_border_color(self):
        self.__con.core.ChangeWindowAttributes(self.id, CW.BorderPixel, [self.border_color])

    def reparent(self, who, wm_state):
        self.parent = who
        geo_abs = self.absolute_geometry()
        self.__con.core.ReparentWindow(self.id, self.parent, geo_abs.x, geo_abs.y)
        change_property(PropMode.Replace, self.id, runtime.wm_atoms["WM_STATE"], Atom.CARDINAL, 32, 1, wm_state)

    def map(self):
        map_window(self.id, 1)

    def tile(self):
        if self.never_tiled:
            self.never_tiled = False

        if not self.tiled:
            self.tiled = True
            self.stack_below()

    def untile(self):
        if self.tiled:
            self.tiled = False

    def __stack(self, how):
        stack_window(self.id, how)

    def stack_above(self):
        self.__stack(StackMode.Above)

    def stack_below(self):
        self.__stack(StackMode.Below)

    def toggle_maximize(self):
        if self.geo_unmax is None:
            self.maximize()
        else:
            self.unmaximize()

        self.real_configure_notify()

    def maximize(self):
        self.geo_unmax = self.relative_geometry()
        self.geo_virt.x = 0
        self.geo_virt.y = 0
        self.geo_virt.w = self.workspace.screen.width - 2*self.geo_virt.b
        self.geo_virt.h = self.workspace.screen.height - 2*self.geo_virt.b
        self.stack_above()

    def unmaximize(self):
        self.geo_virt.x = self.geo_unmax.x
        self.geo_virt.y = self.geo_unmax.y
        self.geo_virt.w = self.geo_unmax.w
        self.geo_virt.h = self.geo_unmax.h
        self.geo_unmax = None

        if self.tiled:
            self.stack_below()

    def attach(self, workspace, teleport):
        if not teleport:
            geo_abs = self.absolute_geometry()
            self.geo_virt.x = geo_abs.x - workspace.screen.x
            self.geo_virt.y = geo_abs.y - workspace.screen.y

        self.__set_workspace(workspace)

    def send_config_window(self, geo):
        configure_window(self.id, geo)

    def real_configure_notify(self):
        geo_abs = self.absolute_geometry()
        if not self.tiled and self.workspace.screen.gap is not None:
            if self.workspace.screen.gap.top:
                geo_abs.y -= self.workspace.screen.gap.h

        self.send_config_window(geo_abs)

    def synthetic_configure_notify(self):
        debug("s_configure: x %d y %d w %d h %d\n" % (self.geo_want.x, self.geo_want.y, self.geo_want.w, self.geo_want.h))
        event = pack("=B3xIIIHHHHHBx", 22, self.id, self.id, 0,
                     self.geo_want.x, self.geo_want.y,
                     self.geo_want.w, self.geo_want.h, self.geo_want.b, 0)
        self.__con.core.SendEvent(False, self.id, EventMask.StructureNotify, event)

    def moveresize(self):
        if self.geo_want.x != self.geo_virt.x:
            self.geo_virt.x = self.geo_want.x

        if self.geo_want.y != self.geo_virt.y:
            self.geo_virt.y = self.geo_want.y

        if self.geo_want.w != self.geo_virt.w:
            self.geo_virt.w = self.geo_want.w

        if self.geo_want.h != self.geo_virt.h:
            self.geo_virt.h = self.geo_want.h

        self.real_configure_notify()

    def configure(self, event):
        if not self.never_tiled:
            return

        if event.value_mask & ConfigWindow.X:
            self.geo_want.x = event.x
        if event.value_mask & ConfigWindow.Y:
            self.geo_want.y = event.y
        if event.value_mask & ConfigWindow.Width:
            self.geo_want.w = event.width
        if event.value_mask & ConfigWindow.Height:
            self.geo_want.h = event.height
        if event.value_mask & ConfigWindow.BorderWidth:
            self.geo_want.b = event.border_width

        if not self.tiled and event.value_mask & (ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height):
            return self.moveresize()

        return self.synthetic_configure_notify()
