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
from decimal import *

class LayoutTall:
    def __init__(self, workspace, master_mapper, slaves_mapper, name):
        self.workspace = workspace
        self.ratio = Decimal(0.5)
        self.name = name
        self.__master_mapper = master_mapper
        self.__slaves_mapper = slaves_mapper

    def update(self, master, slaves):
        if master == None:
            return
        if self.__master_mapper(master, slaves):
            self.__slaves_mapper(slaves)

    def increase(self, stp):
        stp = Decimal(stp)
        if self.ratio < (Decimal(1.0) - stp):
            self.ratio += stp

    def decrease(self, stp):
        stp = Decimal(stp)
        if self.ratio > stp:
            self.ratio -= stp

class LayoutVTall(LayoutTall):
    def __init__(self, workspace):
        LayoutTall.__init__(self, workspace, self.__map_master, self.__map_slaves, "vTall")

    def __map_master(self, master, slaves):
        master.geo_virt.b = 1
        master.geo_virt.x = 0
        master.geo_virt.y = 0
        master.geo_virt.h = self.workspace.screen.height - 2*master.geo_virt.b

        if len(slaves) == 0:
            master.geo_virt.w = self.workspace.screen.width - 2*master.geo_virt.b
            do_slaves = False
        else:
            master.geo_virt.w = int(Decimal(self.workspace.screen.width) * self.ratio) - 2*master.geo_virt.b
            do_slaves = True

        master.real_configure_notify()
        return do_slaves

    def __map_slaves(self, slaves):
        L = len(slaves)
        if L != 0:
            H = self.workspace.screen.height/L
            for i in range(L):
                c = slaves[i]
                c.geo_virt.x = int(Decimal(self.workspace.screen.width) * self.ratio)
                c.geo_virt.y = i*H
                c.geo_virt.w = int(Decimal(self.workspace.screen.width) * (Decimal(1.0) - self.ratio)) - 2*c.geo_virt.b
                c.geo_virt.h = H - 2*c.geo_virt.b
                if i == L-1:
                    c.geo_virt.h += self.workspace.screen.height - (c.geo_virt.y + H)

                c.real_configure_notify()


class LayoutHTall(LayoutTall):
    def __init__(self, workspace):
        LayoutTall.__init__(self, workspace, self.__map_master, self.__map_slaves, "hTall")

    def __map_master(self, master, slaves):
        master.geo_virt.b = 1
        master.geo_virt.x = 0
        master.geo_virt.y = 0
        master.geo_virt.w = self.workspace.screen.width - 2*master.geo_virt.b

        if len(slaves) == 0:
            master.geo_virt.h = self.workspace.screen.height - 2*master.geo_virt.b
            do_slaves = False
        else:
            master.geo_virt.h = int(Decimal(self.workspace.screen.height) * self.ratio) - 2*master.geo_virt.b
            do_slaves = True

        master.real_configure_notify()
        return do_slaves

    def __map_slaves(self, slaves):
        L = len(slaves)
        if L != 0:
            W = self.workspace.screen.width/L
            for i in range(L):
                c = slaves[i]
                c.geo_virt.y = int(Decimal(self.workspace.screen.height) * self.ratio)
                c.geo_virt.x = i*W
                c.geo_virt.h = int(Decimal(self.workspace.screen.height) * (Decimal(1.0) - self.ratio)) - 2*c.geo_virt.b
                c.geo_virt.w = W - (2*c.geo_virt.b)
                if i == L-1:
                    c.geo_virt.w += self.workspace.screen.width - (c.geo_virt.x+W)

                c.real_configure_notify()
