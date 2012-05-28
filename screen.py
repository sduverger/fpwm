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
from api import update_workspace_info

class Screen:
    def __init__(self, viewport, x, y, w, h, workspaces, gap=None):
        self.root = viewport.root
        self.visual = viewport.root_visual
        self.depth = viewport.root_depth
        self.x = x
        self.y = y
        self.width = w
        self.height = h
        self.workspaces = workspaces
        self.active_workspace = None
        self.set_gap(gap)

    def set_gap(self, gap):
        self.gap = gap
        if self.gap is not None:
            self.height -= gap.h
            if gap.top:
                self.y += gap.h

    def set_workspace(self, workspace):
        if workspace.screen is not None:
            return

        if self.active_workspace is not None:
            self.active_workspace.set_passive()

        self.active_workspace = workspace
        self.active_workspace.set_active(self)
        update_workspace_info()
