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

class Gap():
    def __init__(self, x=0, y=0, h=0, top=True):
        self.x = x
        self.y = y
        self.h = h
        self.top = top

class StatusLine():
    def __init__(self, pprint, gap):
        self.gap = gap
        self.pprint = pprint

    def update(self, aw, vw, hw):
        sys.stdout.write(self.pprint(aw, vw, hw))
        sys.stdout.flush()
