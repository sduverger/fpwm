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
from layout import LayoutVTall, LayoutHTall
from utils  import KeyMap
from api    import next_layout, tile_client, toggle_fullscreen, toggle_show_desktop, next_workspace, prev_workspace, next_client, prev_client, send_to_next_workspace, send_to_prev_workspace, send_to_workspace, goto_workspace, increase_layout, decrease_layout, layup_client, laydown_client, move_client, resize_client, spawn

#
# Workspace names
#
workspaces = [ "1", "2", "3", "web" ]

#
# Usable layouts
#
layouts = [LayoutVTall, LayoutHTall]

#
# Keyboard & Mouse bindings: (modifier, key/button, function)
#
keyboard_bindings = [ (KeyMap.mod_alt, KeyMap.space, next_layout),
                      (KeyMap.mod_alt, KeyMap.t,     tile_client),
                      (KeyMap.mod_alt, KeyMap.f,     toggle_fullscreen),
                      (KeyMap.mod_alt, KeyMap.d,     toggle_show_desktop),

                      (KeyMap.mod_alt, KeyMap.right, next_workspace),
                      (KeyMap.mod_alt, KeyMap.left,  prev_workspace),

                      (KeyMap.mod_alt|KeyMap.mod_shift, KeyMap.right, lambda: (send_to_next_workspace(), next_workspace())),
                      (KeyMap.mod_alt|KeyMap.mod_shift, KeyMap.left,  lambda: (send_to_prev_workspace(), prev_workspace())),

                      (KeyMap.mod_alt, KeyMap.tab,   next_client),
                      (KeyMap.mod_alt, KeyMap.down,  next_client),
                      (KeyMap.mod_alt, KeyMap.up,    prev_client),

                      (KeyMap.mod_alt|KeyMap.mod_shift, KeyMap.up, layup_client),
                      (KeyMap.mod_alt|KeyMap.mod_shift, KeyMap.down, laydown_client),

                      (KeyMap.mod_alt, KeyMap.n1, lambda: goto_workspace(0)),
                      (KeyMap.mod_alt, KeyMap.n2, lambda: goto_workspace(1)),
                      (KeyMap.mod_alt, KeyMap.n3, lambda: goto_workspace(2)),
                      (KeyMap.mod_alt, KeyMap.n4, lambda: goto_workspace(3)),

                      (KeyMap.mod_alt|KeyMap.mod_shift, KeyMap.n1, lambda: (send_to_workspace(0),goto_workspace(0))),
                      (KeyMap.mod_alt|KeyMap.mod_shift, KeyMap.n2, lambda: (send_to_workspace(1),goto_workspace(1))),
                      (KeyMap.mod_alt|KeyMap.mod_shift, KeyMap.n3, lambda: (send_to_workspace(2),goto_workspace(2))),
                      (KeyMap.mod_alt|KeyMap.mod_shift, KeyMap.n4, lambda: (send_to_workspace(3),goto_workspace(3))),

                      (KeyMap.mod_alt, KeyMap.l, lambda: increase_layout(0.05)),
                      (KeyMap.mod_alt, KeyMap.h, lambda: decrease_layout(0.05)),

                      (KeyMap.mod_alt, KeyMap.s, lambda:spawn("/usr/bin/xterm","-fg","lightgreen","-bg","black")),
                      (KeyMap.mod_alt, KeyMap.r, lambda:spawn("/usr/bin/gmrun")),
                      ]

mouse_bindings = [ (KeyMap.mod_alt, 1, move_client),
                   (KeyMap.mod_alt, 3, resize_client),
                   ]

#
# Pretty Print: active workspace, the visible workspace list and the hidden workspace list
#
def pretty_print(aw, vw, hw):
    return "> %s < :: %s [%s | %s]\n" % (aw.name, aw.current_layout().name,
                                         " ".join(map(lambda w: w.name,vw)),
                                         " ".join(map(lambda w: w.name, hw)))

#
# Gap: available space for application such as Dzen
#
gap_height = 18
gap_top = True

#
# Focused/Unfocused client colors
#
focused_color = 0x94bff3
passive_color = 0x505050

#
# These clients will not be tilled by default
#
ignored_windows = ["Gmrun", "MPlayer"]
