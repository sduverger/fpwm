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
from   xcb.xproto import *
from   api import update_workspace_info
import runtime

class Workspace:
    def __init__(self, con, viewport, name, layouts):
        self.__con = con
        self.name = name
        self.screen = None
        self.__clients = {}
        self.__master = None
        self.__slaves = []
        self.__floating = []
        self.__layouts = [l(self) for l in layouts]
        self.__current_layout = 0
        self.focused_client = None
        self.__toggle_desktop = False

        self.vroot = self.__con.generate_id()
        self.__con.core.CreateWindow(viewport.root_depth, self.vroot, viewport.root,
                              -1, -1, 1, 1, 0, WindowClass.CopyFromParent,
                              viewport.root_visual, 0, [])

    def add(self, client):
        self.__clients[client.id] = client
        self.__floating.append(client)

    def remove(self, client):
        if self.focused_client == client:
            if len(self.__clients) > 1:
                self.next_client()
            else:
                client.unfocus()
                self.focused_client = None

        self.__floating.remove(client)
        self.__clients.__delitem__(client.id)

    def get_client(self, id):
        return self.__clients.get(id, None)

    def current_layout(self):
        return self.__layouts[self.__current_layout]

    def update(self):
        if self.screen is None:
            return

        if self.__master != None:
            self.__layouts[self.__current_layout].update(self.__master, self.__slaves)

        for c in self.__floating:
            c.real_configure_notify()
            c.stack_above()

    def map(self, client):
        if client.never_tiled:
            self.__tile(client)
        client.map()

        # self.update_focus(client)
        # runtime.ignore_next_enter_notify = True

    def __tile(self, client):
        client.tile()
        self.__floating.remove(client)

        if self.__master is not None:
            self.__slaves.insert(0,self.__master)

        self.__master = client
        self.update()

    def __untile(self, client, update=True):
        client.untile()
        self.__floating.append(client)

        if self.__master.id == client.id:
            self.__master = None
            if len(self.__slaves) == 0:
                return
            self.__master = self.__slaves.pop(0)
        else:
            self.__slaves.remove(client)

        if update:
            self.update()

    def untile(self, client, update=True):
        if not client.tiled:
            return
        self.__untile(client, update)

    def tile(self, client):
        if client.tiled:
            return
        self.__tile(client)

    def detach(self, client, update=True):
        self.untile(client, update)
        self.remove(client)

    def attach(self, client, teleport=False):
        self.add(client)
        client.attach(self, teleport)

    def __next_client(self, with_floating=True):
        if self.focused_client.tiled:
            if self.focused_client == self.__master:
                if len(self.__slaves) != 0:
                    return self.__slaves[0]
                elif with_floating and len(self.__floating) != 0:
                    return self.__floating[0]
            else:
                for n in range(len(self.__slaves)):
                    if self.__slaves[n] == self.focused_client:
                        break

                n = (n+1)%len(self.__slaves)
                if n != 0:
                    return self.__slaves[n]

                if with_floating and len(self.__floating) != 0:
                    return self.__floating[0]

                return self.__master

        elif with_floating:
            for n in range(len(self.__floating)):
                if self.__floating[n] == self.focused_client:
                    break

            n = (n+1)%len(self.__floating)
            if n != 0 or self.__master == None:
                return self.__floating[n]

            return self.__master

        return self.focused_client

    def __prev_client(self, with_floating=True):
        last_sl = len(self.__slaves) - 1
        last_fl = len(self.__floating) - 1

        if self.focused_client.tiled:
            if self.focused_client == self.__master:
                if with_floating and len(self.__floating) != 0:
                    return self.__floating[last_fl]
                elif len(self.__slaves) != 0:
                    return self.__slaves[last_sl]
            else:
                for n in range(len(self.__slaves)):
                    if self.__slaves[n] == self.focused_client:
                        break

                n = (n-1)%len(self.__slaves)
                if n != last_sl:
                    return self.__slaves[n]

                return self.__master

        elif with_floating:
            for n in range(len(self.__floating)):
                if self.__floating[n] == self.focused_client:
                    break

            n = (n-1)%len(self.__floating)
            if n == last_fl:
                if len(self.__slaves) != 0:
                    return self.__slaves[last_sl]
                elif self.__master != None:
                    return self.__master

            return self.__floating[n]

        return self.focused_client

    def next_client(self):
        if self.focused_client is None:
            return

        self.update_focus(self.__next_client())
        if not self.focused_client.tiled:
            self.focused_client.stack_above()

    def prev_client(self):
        if self.focused_client is None:
            return

        self.update_focus(self.__prev_client())
        if not self.focused_client.tiled:
            self.focused_client.stack_above()

    def laydown_client(self):
        if self.focused_client is None or not self.focused_client.tiled:
            return

        if len(self.__slaves) == 0:
            return

        if self.focused_client == self.__master:
            self.__master, self.__slaves[0] = self.__slaves[0], self.__master
        else:
            for n in range(len(self.__slaves)):
                if self.__slaves[n] == self.focused_client:
                    break

            nn = (n+1)%len(self.__slaves)
            if nn != 0:
                self.__slaves[n], self.__slaves[nn] = self.__slaves[nn], self.__slaves[n]
            else:
                c = self.__slaves.pop(n)
                self.__slaves.insert(0, self.__master)
                self.__master = c

        runtime.ignore_next_enter_notify = True

        self.focused_client.focus()
        self.update()

    def layup_client(self):
        if self.focused_client is None or not self.focused_client.tiled:
            return

        if len(self.__slaves) == 0:
            return

        last_sl = len(self.__slaves) - 1

        if self.focused_client == self.__master:
                c = self.__slaves.pop(0)
                self.__slaves.append(self.__master)
                self.__master = c
        else:
            for n in range(len(self.__slaves)):
                if self.__slaves[n] == self.focused_client:
                    break

            nn = (n-1)%len(self.__slaves)
            if nn != last_sl:
                self.__slaves[n], self.__slaves[nn] = self.__slaves[nn], self.__slaves[n]
            else:
                self.__master, self.__slaves[n] = self.__slaves[n], self.__master

        runtime.ignore_next_enter_notify = True

        self.focused_client.focus()
        self.update()

    def update_focus(self, client):
        if self.focused_client is not None:
            self.focused_client.unfocus()

        self.focused_client = client

        if client is not None:
            self.focused_client.focus()

    def reparent(self, who, wm_state):
        for c in self.__clients.itervalues():
            c.reparent(who, wm_state)

    def set_passive(self):
        self.screen = None
        self.reparent(self.vroot, 0)

    def set_active(self, screen):
        self.screen = screen
        self.reparent(self.screen.root, 1)
        self.update()

    def next_layout(self):
        if self.screen is None:
            return

        self.__current_layout = (self.__current_layout+1)%len(self.__layouts)
        self.update()
        update_workspace_info()

    def toggle_desktop(self):
        if self.screen is None or len(self.__clients) == 0:
            return

        if not self.__toggle_desktop:
            self.__con.core.UnmapSubwindows(self.screen.root)
            self.__toggle_desktop = True
        else:
            self.__con.core.MapSubwindows(self.screen.root)
            self.__toggle_desktop = False

    def toggle_fullscreen(self):
        if self.screen is None or self.focused_client is None:
            return
        self.focused_client.toggle_maximize()
