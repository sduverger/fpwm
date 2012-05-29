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
from xcb.randr  import *

wmname = "fpwm"

screens = []
workspaces = []
clients = {}

focused_screen = None
ignore_next_enter_notify = False
need_restart = False

con = None
viewport = None
xrandr = None

wm_atoms = {}
net_wm_atoms = {}
fp_wm_atoms = {}

#|EventMask.LeaveWindow
#|EventMask.ButtonPress|EventMask.ButtonRelease
events = [EventMask.SubstructureRedirect|EventMask.SubstructureNotify|EventMask.EnterWindow|EventMask.StructureNotify|EventMask.PropertyChange|EventMask.FocusChange]

status_line = None
keyboard = None
mouse = None

ignored_windows = []
