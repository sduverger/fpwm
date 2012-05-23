#!/usr/bin/env python

import sys, os
import xcb
from   xcb.xproto import *
import xcb.randr

wmname = "fpwm"

atom_names = ["_NET_SUPPORTED",
              "_NET_SUPPORTING_WM_CHECK",
              # "_NET_STARTUP_ID",
              # "_NET_CLIENT_LIST",
              # "_NET_CLIENT_LIST_STACKING",
              # "_NET_NUMBER_OF_DESKTOPS",
              # "_NET_CURRENT_DESKTOP",
              # "_NET_DESKTOP_NAMES",
              # "_NET_ACTIVE_WINDOW",
              # "_NET_DESKTOP_GEOMETRY",
              # "_NET_CLOSE_WINDOW",
              "_NET_WM_NAME",
              # "_NET_WM_STRUT_PARTIAL",
              # "_NET_WM_ICON_NAME",
              # "_NET_WM_VISIBLE_ICON_NAME",
              # "_NET_WM_DESKTOP",
              # "_NET_WM_WINDOW_TYPE",
              # "_NET_WM_WINDOW_TYPE_DESKTOP",
              # "_NET_WM_WINDOW_TYPE_DOCK",
              # "_NET_WM_WINDOW_TYPE_TOOLBAR",
              # "_NET_WM_WINDOW_TYPE_MENU",
              # "_NET_WM_WINDOW_TYPE_UTILITY",
              # "_NET_WM_WINDOW_TYPE_SPLASH",
              # "_NET_WM_WINDOW_TYPE_DIALOG",
              # "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU",
              # "_NET_WM_WINDOW_TYPE_POPUP_MENU",
              # "_NET_WM_WINDOW_TYPE_TOOLTIP",
              # "_NET_WM_WINDOW_TYPE_NOTIFICATION",
              # "_NET_WM_WINDOW_TYPE_COMBO",
              # "_NET_WM_WINDOW_TYPE_DND",
              # "_NET_WM_WINDOW_TYPE_NORMAL",
              # "_NET_WM_ICON",
              "_NET_WM_PID",
              # "_NET_WM_STATE",
              # "_NET_WM_STATE_STICKY",
              # "_NET_WM_STATE_SKIP_TASKBAR",
              # "_NET_WM_STATE_FULLSCREEN",
              # "_NET_WM_STATE_MAXIMIZED_HORZ",
              # "_NET_WM_STATE_MAXIMIZED_VERT",
              # "_NET_WM_STATE_ABOVE",
              # "_NET_WM_STATE_BELOW",
              # "_NET_WM_STATE_MODAL",
              # "_NET_WM_STATE_HIDDEN",
              # "_NET_WM_STATE_DEMANDS_ATTENTION"
              ]

def Flat(format, data):
    f={32:'I',16:'H',8:'B'}[format]
    if not hasattr(data, "__iter__") and not hasattr(data, "__getitem__"):
        data = [data]
    return array(f, data).tostring()

def ChangeProperty(core, mode, window, property, type, format, data_len, data):
    core.ChangeProperty(mode, window, property, type, format, data_len, Flat(format, data))


#
# Gap ()
#
class Gap():
    def __init__(self, x=0, y=0, w=0, h=0, top=True):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.top = top

#
# Screen
#
class Screen:
    #focused_color = 0x94bff3
    focused_color = 0xff0000
    passive_color = 0x505050

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

        if gap is not None:
            self.height -= gap.h
            if gap.top:
                self.y += gap.h

        ChangeProperty(con.core, PropMode.Replace, self.root, atoms["_NET_SUPPORTED"], Atom.ATOM, 32, len(atoms), atoms.itervalues())

        self.wm = con.generate_id()
        con.core.CreateWindow(self.depth, self.wm, self.root, -1, -1, 1, 1, 0, WindowClass.CopyFromParent, self.visual, 0, [])

        ChangeProperty(con.core, PropMode.Replace, self.root,  atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, self.wm)
        ChangeProperty(con.core, PropMode.Replace, self.wm, atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, self.wm)
        ChangeProperty(con.core, PropMode.Replace, self.wm, atoms["_NET_WM_NAME"], Atom.STRING, 8, len(wmname), wmname)
        ChangeProperty(con.core, PropMode.Replace, self.wm, atoms["_NET_WM_PID"], Atom.CARDINAL, 32, 1, os.getpid())

    def set_workspace(self, workspace):
        if workspace.screen is not None:
            return

        if self.active_workspace is not None:
            self.active_workspace.set_passive()

        self.active_workspace = workspace
        self.active_workspace.set_active(self)
        update_workspace_info()
#
# Layout
#
class LayoutTall:
    def __init__(self, workspace, master_mapper, slaves_mapper):
        self.workspace = workspace
        self.__master_mapper = master_mapper
        self.__slaves_mapper = slaves_mapper

    def update(self, master, slaves):
        if master == None:
            return
        if self.__master_mapper(master, slaves):
            self.__slaves_mapper(slaves)

class LayoutVTall(LayoutTall):
    def __init__(self, workspace):
        LayoutTall.__init__(self, workspace, self.__map_master, self.__map_slaves)

    def __map_master(self, master, slaves):
        master.geo_virt.b = 1
        master.geo_virt.x = 0
        master.geo_virt.y = 0
        master.geo_virt.h = self.workspace.screen.height - 2*master.geo_virt.b

        if len(slaves) == 0:
            master.geo_virt.w = self.workspace.screen.width - 2*master.geo_virt.b
            do_slaves = False
        else:
            master.geo_virt.w = self.workspace.screen.width/2 - 2*master.geo_virt.b
            do_slaves = True

        master.real_configure_notify()
        return do_slaves

    def __map_slaves(self, slaves):
        L = len(slaves)
        if L != 0:
            H = self.workspace.screen.height/L
            for i in range(L):
                c = slaves[i]
                c.geo_virt.x = self.workspace.screen.width/2
                c.geo_virt.y = i*H
                c.geo_virt.w = self.workspace.screen.width/2 - 2*c.geo_virt.b
                c.geo_virt.h = H - 2*c.geo_virt.b
                c.real_configure_notify()

class LayoutHTall(LayoutTall):
    def __init__(self, workspace):
        LayoutTall.__init__(self, workspace, self.__map_master, self.__map_slaves)

    def __map_master(self, master, slaves):
        master.geo_virt.b = 1
        master.geo_virt.x = 0
        master.geo_virt.y = 0
        master.geo_virt.w = self.workspace.screen.width - 2*master.geo_virt.b

        if len(slaves) == 0:
            master.geo_virt.h = self.workspace.screen.height - 2*master.geo_virt.b
            do_slaves = False
        else:
            master.geo_virt.h = self.workspace.screen.height/2 - 2*master.geo_virt.b
            do_slaves = True

        master.real_configure_notify()
        return do_slaves

    def __map_slaves(self, slaves):
        L = len(slaves)
        if L != 0:
            W = self.workspace.screen.width/L
            for i in range(L):
                c = slaves[i]
                c.geo_virt.y = self.workspace.screen.height/2
                c.geo_virt.x = i*W
                c.geo_virt.h = self.workspace.screen.height/2 - 2*c.geo_virt.b
                c.geo_virt.w = W - (2*c.geo_virt.b)
                c.real_configure_notify()

#
# Workspace
#
class Workspace:
    def __init__(self, name, viewport):
        self.name = name
        self.screen = None
        self.__clients = {}
        self.__master = None
        self.__slaves = []
        self.__floating = []
        self.__layouts = [LayoutVTall(self), LayoutHTall(self)]
        self.current_layout = 0
        self.focused_client = None
        self.__toggle_desktop = False

        self.vroot = con.generate_id()
        con.core.CreateWindow(viewport.root_depth, self.vroot, viewport.root,
                              -1, -1, 1, 1, 0, WindowClass.CopyFromParent,
                              viewport.root_visual, 0, [])

    def add(self, client):
        self.__clients[client.id] = client
        self.__floating.append(client)

    def remove(self, client):
        if self.focused_client == client:
            if len(self.__clients) > 1:
                self.__next_client()
            else:
                client.unfocus()
                self.focused_client = None

        self.__floating.remove(client)
        self.__clients.__delitem__(client.id)

    def get_client(self, id):
        return self.__clients.get(id, None)

    def update(self):
        if self.screen is None:
            return

        if self.__master != None:
            self.__layouts[self.current_layout].update(self.__master, self.__slaves)

        for c in self.__floating:
            c.stack_above()

    def map(self, client):
        if client.never_tiled:
            self.__tile(client)
        client.map()

    def __tile(self, client, update=True):
        client.tile()
        self.__floating.remove(client)

        if self.__master is not None:
            self.__slaves.insert(0,self.__master)

        self.__master = client
        if update:
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

    def tile(self, client, update=True):
        if client.tiled:
            return
        self.__tile(client, update)

    def detach(self, client, update=True):
        self.untile(client, update)
        client.detach()
        self.remove(client)

    def attach(self, client):
        self.add(client)
        client.attach(self)

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

        global _ignore_next_enter_notify
        _ignore_next_enter_notify = True

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

        global _ignore_next_enter_notify
        _ignore_next_enter_notify = True

        self.focused_client.focus()
        self.update()

    def update_focus(self, client):
        if self.focused_client is not None:
            self.focused_client.unfocus()

        self.focused_client = client

        if client is not None:
            self.focused_client.focus()
        else:
            con.core.SetInputFocus(InputFocus.PointerRoot, self.screen.root, InputFocus._None)

    def reparent(self, who):
        for c in self.__clients.itervalues():
            c.reparent(who)

    def set_passive(self):
        self.screen = None
        self.reparent(self.vroot)

    def set_active(self, screen):
        self.screen = screen
        self.reparent(self.screen.root)
        self.update()

    def next_layout(self):
        if self.screen is None:
            return

        self.current_layout = (self.current_layout+1)%len(self.__layouts)
        self.update()

    def toggle_desktop(self):
        if self.screen is None or len(self.__clients) == 0:
            return

        if not self.__toggle_desktop:
            con.core.UnmapSubwindows(self.screen.root)
            self.__toggle_desktop = True
        else:
            con.core.MapSubwindows(self.screen.root)
            self.__toggle_desktop = False

    def toggle_fullscreen(self):
        if self.screen is None or self.focused_client is None:
            return
        self.focused_client.toggle_maximize()

#
# Client
#
class Geometry:
    def __init__(self, x=0, y=0, w=0, h=0, b=0):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.b = b

    def copy(self):
        return Geometry(self.x, self.y, self.w, self.h, self.b)

class Client:
    def __init__(self, window, parent, workspace, geometry=None):
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
        self.border_color = Screen.passive_color
        self.workspace = workspace
        self.tiled = False
        self.never_tiled = True
        self.__setup()

    def __setup(self):
        mask  = EventMask.EnterWindow|EventMask.PropertyChange|EventMask.FocusChange
        con.core.ChangeWindowAttributes(self.id, CW.EventMask, [mask])

    def relative_geometry(self):
        return self.geo_virt.copy()

    def absolute_geometry(self):
        return Geometry(self.geo_virt.x+self.workspace.screen.x, self.geo_virt.y+self.workspace.screen.y)

    def located_into(self, workspace):
        geo_abs = self.absolute_geometry()
        screen = workspace.screen
        if geo_abs.x >= screen.x and geo_abs.x < screen.x+screen.width:
            return True
        return False

    def detach(self):
        geo_abs = self.absolute_geometry()
        self.geo_virt.x = geo_abs.x - self.workspace.screen.x
        self.geo_virt.y = geo_abs.y - self.workspace.screen.y

    def attach(self, workspace):
        self.workspace = workspace

    def move(self, dx, dy):
        self.geo_virt.x += dx
        self.geo_virt.y += dy
        self.real_configure_notify()

    def resize(self, up, left, dx, dy):
        if up and left:
            mx = dx
            my = dy
            dy = -dy
            dx = -dx
        elif up and not left:
            mx = 0
            my = dy
            dy = -dy
        elif not up and left:
            mx = dx
            my = 0
            dx = -dx
        else:
            mx = 0
            my = 0

        if self.geo_virt.w < self.__min_w:
            self.geo_virt.w = self.__min_w

        if self.geo_virt.w == self.__min_w and dx < 0:
            dx = 0
            mx = 0

        if self.geo_virt.h < self.__min_h:
            self.geo_virt.h = self.__min_h

        if self.geo_virt.h == self.__min_h and dy < 0:
            dy = 0
            my = 0

        if dx == 0 and dy == 0:
            return

        if mx != 0 or my != 0:
            self.move(mx, my)

        self.geo_virt.w += dx
        self.geo_virt.h += dy
        self.real_configure_notify()

    def reparent(self, who):
        self.parent = who
        con.core.ReparentWindow(self.id, self.parent, self.geo_virt.x, self.geo_virt.y)

    def focus(self):
        self.border_color = Screen.focused_color
        self.update_border_color()
        con.core.SetInputFocus(InputFocus.PointerRoot, self.id, InputFocus._None)

    def unfocus(self):
        self.border_color = Screen.passive_color
        self.update_border_color()

    def update_border_color(self):
        con.core.ChangeWindowAttributes(self.id, CW.BorderPixel, [self.border_color])

    def release(root):
        self.geo_virt.x = 0
        self.geo_virt.y = 0
        self.reparent(root)

    def map(self):
        con.core.MapWindow(self.id)

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
        con.core.ConfigureWindow(self.id, ConfigWindow.StackMode, [how])

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

    def real_configure_notify(self):
        geo_abs = self.absolute_geometry()
        mask = ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height|ConfigWindow.BorderWidth
        sys.stderr.write("r_configure: x %d y %d w %d h %d\n" % (geo_abs.x, geo_abs.y, self.geo_virt.w, self.geo_virt.h))
        pkt = pack('=xx2xIH2xiiIII', self.id, mask, geo_abs.x, geo_abs.y,
                   self.geo_virt.w, self.geo_virt.h, self.geo_virt.b)
        con.core.send_request(xcb.Request(pkt, 12, True, False), xcb.VoidCookie())

    def synthetic_configure_notify(self):
        sys.stderr.write("s_configure: x %d y %d w %d h %d\n" % (self.geo_want.x, self.geo_want.y, self.geo_want.w, self.geo_want.h))
        event = pack("=B3xIIIHHHHHBx", 22, self.id, self.id, 0,
                     self.geo_want.x, self.geo_want.y,
                     self.geo_want.w, self.geo_want.h, self.geo_want.b, 0)
        con.core.SendEvent(False, self.id, EventMask.StructureNotify, event)

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

#
# Other clients
#
def vanilla_configure_window_request(event):
    values = []
    if event.value_mask & ConfigWindow.X:
        values.append(event.x)
    if event.value_mask & ConfigWindow.Y:
        values.append(event.y)
    if event.value_mask & ConfigWindow.Width:
        values.append(event.width)
    if event.value_mask & ConfigWindow.Height:
        values.append(event.height)
    if event.value_mask & ConfigWindow.BorderWidth:
        values.append(event.border_width)
    if event.value_mask & ConfigWindow.Sibling:
        values.append(event.sibling)
    if event.value_mask & ConfigWindow.StackMode:
        values.append(event.stack_mode)

    con.core.ConfigureWindow(event.window, event.value_mask, values)

def acquire_ext_clients(viewport):
    clients = []
    reply = con.core.QueryTree(viewport.root).reply()
    if reply.children_len == 0:
        return clients
    children = unpack_from("%dI" % reply.children_len, reply.children.buf())
    for cid in children:
        wa = con.core.GetWindowAttributes(cid).reply()
        if wa.map_state == MapState.Unmapped or wa.override_redirect:
            continue
        geo = con.core.GetGeometry(cid).reply()
        clients.append((cid, geo.x, geo.y, geo.width, geo.height, geo.border_width))
    return clients

def add_ext_clients(ext_clients):
    for cid,x,y,w,h,b in ext_clients:
        lost_client = False
        gm = Geometry(x, y, w, h, b)
        sys.stderr.write("ext client at x %d y %d\n" % (x,y))

        sc = get_screen_at(gm)
        if sc is None:
            lost_client = True
            gm.x = 0
            gm.y = 0
            sc = get_screen_at(gm)

        wk = sc.active_workspace
        cl = Client(cid, viewport.root, wk, gm)
        _clients[cid] = cl
        wk.add(cl)

        if lost_client:
            cl.real_configure_notify()
        sys.stderr.write("acquired client %d\n" % cid)

def release_clients(viewport):
    for c in _clients:
        c.release(viewport.root)

#
# Events
#
def event_enter_notify(event):
    sys.stderr.write("enter notify 0x%x: %r\n" % (event.event, event.__dict__))
    global _ignore_next_enter_notify
    if _ignore_next_enter_notify:
        _ignore_next_enter_notify = False
        return

    cl = _clients.get(event.event)
    if cl is not None:
        set_current_screen_from(cl.workspace.screen)
    else:
        set_current_screen_at(Geometry(event.root_x, event.root_y))

    current_workspace().update_focus(cl)

def event_configure_window_request(event):
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is None:
        vanilla_configure_window_request(event)
    else:
        cl.configure(event)

def event_map_window(event):
    sys.stderr.write("map request: %r\n" % event.__dict__)
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is None:
        cl = Client(event.window, event.parent, wk)
        _clients[cl.id] = cl
        wk.add(cl)
    wk.map(cl)

def event_destroy_notify(event):
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is not None:
        sys.stderr.write("destroy client %d\n" % event.window)
        if cl.tiled:
            wk.untile(cl)
        wk.remove(cl)
        _clients.__delitem__(cl.id)

# def event_reparent_notify(event):
    # wk = current_workspace()
    # cl = scr.get_client(event.window)
    # evt = pack("=B3xIIIHH3x",
    #            21, event.event, event.window, event.parent,
    #            cl.geo_virt.x, cl.geo_virt.y)
    # con.core.SendEvent(False, event.window, EventMask.StructureNotify, evt)

def event_key_press(event):
    keyboard.press(event)

def event_key_release(event):
    keyboard.release(event)

def event_motion_notify(event):
    mouse.motion(event)

def event_button_press(event):
    mouse.press(event)

def event_button_release(event):
    mouse.release(event)

#|EventMask.LeaveWindow
#|EventMask.ButtonPress|EventMask.ButtonRelease
events = [EventMask.SubstructureRedirect|EventMask.SubstructureNotify|EventMask.EnterWindow|EventMask.StructureNotify|EventMask.PropertyChange|EventMask.FocusChange]

event_handlers = { EnterNotifyEvent:event_enter_notify,
                   ConfigureRequestEvent:event_configure_window_request,
                   MapRequestEvent:event_map_window,
                   DestroyNotifyEvent:event_destroy_notify,
                   KeyPressEvent:event_key_press,
                   KeyReleaseEvent:event_key_release,
                   MotionNotifyEvent:event_motion_notify,
                   ButtonPressEvent:event_button_press,
                   ButtonReleaseEvent:event_button_release,
                   }

def event_handler(event):
    hdl = event_handlers.get(event.__class__, None)
    if hdl is not None:
        sys.stderr.write("--> %s\n" % event.__class__.__name__)
        hdl(event)
    # else:
    #     sys.stderr.write("** Unhandled event ** %r %r\n" % (event.__class__.__name__, event.__dict__))

#
# Keyboard
#
class Keyboard:
    def __init__(self):
        self.__bindings = {}

    def attach(self, bindings):
        for m,k,f in bindings:
            if m is None:
                raise ValueError("missing modifier in keyboard bindings")

            if not self.__bindings.has_key(k):
                self.__bindings[k] = {}

            self.__bindings[k][m] = f
            con.core.GrabKey(False, current_client_id(), m, k, GrabMode.Async, GrabMode.Async)

    def detach(self):
        con.core.UngrabKey(False, current_client_id(), ModMask.Any)

    def press(self, event):
        sys.stderr.write("key press 0x%x: %r\n" % (event.child, event.__dict__))
        self.__bindings[event.detail][event.state]()

    def release(self, event):
        sys.stderr.write("key release 0x%x: %r\n" % (event.child, event.__dict__))

#
# Mouse
#
class Mouse:
    def __init__(self):
        self.__acting = None
        self.__c = None
        self.__x = 0
        self.__y = 0
        self.__up = False
        self.__left = False
        self.__bindings = {}

    def attach(self, bindings):
        for m,b,f in bindings:
            if m is None:
                raise ValueError("missing modifier in mouse bindings")

            if not self.__bindings.has_key(b):
                self.__bindings[b] = {}

            self.__bindings[b][m] = f

            bmask = eval("EventMask.Button%dMotion" % b)
            emask = EventMask.ButtonPress|EventMask.ButtonRelease|bmask
            con.core.GrabButton(False, current_client_id(), emask, GrabMode.Async, GrabMode.Async, 0, 0, b, m)

    def detach(self):
        con.core.UngrabButton(False, current_client_id(), ButtonMask.Any)

    def motion(self, event):
        if self.__acting is None:
            return

        dx = event.root_x - self.__x
        dy = event.root_y - self.__y

        self.__acting(self.__c, self.__up, self.__left, dx, dy)

        self.__x = event.event_x
        self.__y = event.event_y

    def press(self, event):
        sys.stderr.write("button press 0x%x: %r\n" % (event.child, event.__dict__))
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
        sys.stderr.write("button release 0x%x: %r\n" % (event.child, event.__dict__))
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


#
# Services
#
def get_screen_at(geo):
    for s in _screens:
        if geo.x >= s.x and geo.x < s.x+s.width:
            return s

def set_current_screen_at(geo):
    global focused_screen
    ns = get_screen_at(geo)
    if ns != focused_screen:
        focused_screen = ns
        update_workspace_info()

def set_current_screen_from(screen):
    global focused_screen
    if screen != focused_screen:
        focused_screen = screen
        update_workspace_info()

def current_screen():
    return focused_screen

def update_workspace_info():
    aw  = current_workspace()
    vwn = []
    hwn = []
    for w in _workspaces:
        if w.screen is None:
            hwn.append(w.name)
        elif w != aw:
            vwn.append(w.name)

    sys.stdout.write("%s %r %r\n" % (aw.name,vwn,hwn))
    sys.stdout.flush()

def current_workspace():
    return current_screen().active_workspace

def current_client():
    # may be None (no client)
    return current_workspace().focused_client

def current_client_id():
    c = current_client()
    if c is None:
        return current_workspace().screen.root
    return c.id

def tile(c):
    if c is not None and not c.tiled:
        c.workspace.tile(c)

def untile(c):
    if c is not None and c.tiled:
        c.workspace.untile(c)

def tile_client():
    tile(current_client())

def untile_client():
    untile(current_client())

def move_client(c, up, left, dx, dy):
    if c is not None:
        untile(c)
        c.move(dx, dy)

def resize_client(c, up, left, dx, dy):
    if c is not None:
        untile(c)
        c.resize(up, left, dx, dy)

def next_layout():
    current_workspace().next_layout()

def toggle_show_desktop():
    wk = current_workspace()
    wk.toggle_desktop()

def toggle_fullscreen():
    wk = current_workspace()
    wk.toggle_fullscreen()

def get_workspace_with(wk1, stp):
    n = 0
    for w in _workspaces:
        if w == wk1:
            break
        n += 1

    while True:
        n = (n+stp)%len(_workspaces)
        wk2 = _workspaces[n]
        if wk2 == wk1:
            return None
        if wk2.screen == None:
            return wk2

def get_workspace_at(n):
    if n >= len(_workspaces):
        return None

    return _workspaces[n]

def get_next_workspace_with(wk):
    return get_workspace_with(wk, 1)

def get_prev_workspace_with(wk):
    return get_workspace_with(wk, -1)

def send_to_workspace_with(nwk):
    sys.stderr.write("send_to_workspace\n")
    c = current_client()
    if nwk is None or c is None:
        return

    cwk = c.workspace
    tiled = c.tiled

    cwk.detach(c, False)
    nwk.attach(c)

    if nwk.screen is None:
        c.reparent(nwk.vroot)
        update = False
    else:
        update = True

    if tiled:
        nwk.tile(c, update)
    else:
        c.stack_above()

def send_to_workspace(n):
    wk = get_workspace_at(n)
    if wk is not None and wk != current_workspace():
        send_to_workspace_with(wk)

def send_to_next_workspace():
    send_to_workspace_with(get_next_workspace_with(current_workspace()))

def send_to_prev_workspace():
    send_to_workspace_with(get_prev_workspace_with(current_workspace()))

def goto_workspace(n):
    wk = get_workspace_at(n)
    if wk is not None and wk != current_workspace() and wk.screen is None:
        current_screen().set_workspace(wk)

def next_workspace():
    nwk = get_next_workspace_with(current_workspace())
    if nwk is not None:
        sys.stderr.write("next_workspace %s -> %s\n" % (current_workspace().name, nwk.name))
        current_screen().set_workspace(nwk)

def prev_workspace():
    nwk = get_prev_workspace_with(current_workspace())
    if nwk is not None:
        sys.stderr.write("prev_workspace %s -> %s\n" % (current_workspace().name, nwk.name))
        current_screen().set_workspace(nwk)

def next_client():
    current_workspace().next_client()

def prev_client():
    current_workspace().prev_client()

def layup_client():
    current_workspace().layup_client()

def laydown_client():
    current_workspace().laydown_client()

def spawn(*args):
    child = os.fork()
    if child != 0:
        os.waitpid(child, 0)
        return
    if os.fork() != 0:
        os._exit(0)
    os.setsid()
    os.execl(args[0], *args)

#
# Bindings
#
class KeyMap:
    up             = 111
    down           = 116
    left           = 113
    right          = 114
    tab            = 23
    space          = 65
    t              = 28
    d              = 40
    f              = 41
    s              = 39
    r              = 27
    n1             = 10
    n2             = 11
    n3             = 12
    n4             = 13
    n5             = 14
    n6             = 15
    n7             = 16
    n8             = 17
    n9             = 18
    n0             = 19

    mod_shift      = KeyButMask.Shift
    mod_ctrl       = KeyButMask.Control
    mod_alt        = KeyButMask.Mod1
    mod_win        = KeyButMask.Mod4
    mod_altgr      = KeyButMask.Mod5

workspaces = [ "1", "2", "3", "web" ]

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

                      (KeyMap.mod_alt, KeyMap.s, lambda:spawn("/usr/bin/xterm","-fg","lightgreen","-bg","black")),
                      (KeyMap.mod_alt, KeyMap.r, lambda:spawn("/usr/bin/gmrun")),
                      ]

mouse_bindings    = [ (KeyMap.mod_alt, 1, move_client),
                      (KeyMap.mod_alt, 3, resize_client),
                      ]

status_line = Gap(h=18)

# XXX: KeyButMask.Mod2 is always set (xpyb/Xephyr bug ?)
# def xhephyr_fix(x):
#     for n in range(len(x)):
#         x[n] = (x[n][0]|KeyButMask.Mod2, x[n][1], x[n][2])

# xhephyr_fix(keyboard_bindings)
# keyboard_bindings[7] = (keyboard_bindings[7][0], keyboard_bindings[7][1], lambda:os.system("DISPLAY=:1 xterm&"))
# xhephyr_fix(mouse_bindings)

#
# Main
#
# TODO:
# . extend _NET_WM support (_NET_VIRTUAL_ROOTS, _NET_WM_HINTS, ...)
#
keyboard = Keyboard()
mouse = Mouse()
_screens = []
_workspaces = []
_clients = {}
_ignore_next_enter_notify = False

con = xcb.connect()
setup = con.get_setup()
viewport = setup.roots[0]
xrandr = con(xcb.randr.key)

con.core.GrabServer()
while con.poll_for_event():
    pass

try:
    con.core.ChangeWindowAttributesChecked(viewport.root, CW.EventMask, events).check()
except BadAccess, e:
    sys.stderr.write("A window manager is already running !\n")
    con.disconnect()
    sys.exit(1)

ext_clients = acquire_ext_clients(viewport)

reply = xrandr.GetScreenResources(viewport.root).reply()

if len(workspaces) < reply.num_crtcs:
    sys.stderr.write("Not enough workspaces\n")
    con.disconnect()
    sys.exit(1)

atoms = {}
for n in atom_names:
    atoms[n] = con.core.InternAtom(False, len(n), n)
for n in atoms:
    atoms[n] = atoms[n].reply().atom

for w in workspaces:
    _workspaces.append(Workspace(w, viewport))

w = 0
screen_ids = unpack_from("%dI" % reply.num_crtcs, reply.crtcs.buf())
for sid in screen_ids:
    reply = xrandr.GetCrtcInfo(sid,0).reply()
    if reply.width == 0 or reply.height == 0:
        continue
    if status_line is not None and reply.x == status_line.x and reply.y == status_line.y:
        gap = status_line
    else:
        gap = None
    scr = Screen(viewport, reply.x, reply.y, reply.width, reply.height, _workspaces, gap)
    focused_screen = scr
    scr.set_workspace(_workspaces[w])
    _screens.append(scr)
    w += 1

add_ext_clients(ext_clients)

con.core.UngrabServer()
con.flush()
while con.poll_for_event():
    pass

keyboard.attach(keyboard_bindings)
mouse.attach(mouse_bindings)

while True:
    try:
        event = con.wait_for_event()
    except Exception, error:
        sys.stderr.write("panic: %s\n" % error.__class__.__name__)
        con.disconnect()
        sys.exit(1)

    event_handler(event)
    con.flush()

# mouse.detach()
# keyboard.detach()
# release_clients(viewport)
sys.stderr.write("exiting\n")
con.disconnect()
