#!/usr/bin/env python

# TODO
# . extends _NET_WM support (_NET_VIRTUAL_ROOTS, _NET_WM_HINTS, ...)
# . tasks (aka workspace lists)
# . 2d workspaces (next/prev/up/down)
# . add/remove workspaces into tasks (line,column)
# . split code into a package
# . debug function
# . "ignored windows" list
# . focus color out of Screen
# . only color focus active workspace ?
# . send InputFocus when Goto another visible workspace
# . manage FocusIn/FocusOut events
# . pager

import sys, os, signal
from   decimal import *
import xcb
from   xcb.xproto import *
import xcb.randr

#
# Status Line
#
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
        self.pprint(aw, vw, hw)

#
# Screen
#
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
#
# Layout
#
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


#
# Workspace
#
class Workspace:
    def __init__(self, name, viewport, layouts):
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
            # global _ignore_next_enter_notify
            # _ignore_next_enter_notify = True

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
        self.border_color = passive_color
        self.tiled = False
        self.never_tiled = True
        self.__set_workspace(workspace)
        self.__setup()

    def __set_workspace(self, workspace):
        self.workspace = workspace
        ChangeProperty(con.core, PropMode.Replace, self.id, _fp_wm_atoms["_FP_WM_WORKSPACE"], Atom.STRING, 8,
                       len(self.workspace.name), self.workspace.name)

    def __setup(self):
        mask  = EventMask.EnterWindow|EventMask.PropertyChange|EventMask.FocusChange
        con.core.ChangeWindowAttributes(self.id, CW.BorderPixel|CW.EventMask, [self.border_color,mask])

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

    def focus(self):
        self.border_color = focused_color
        self.update_border_color()
        con.core.SetInputFocus(InputFocus.PointerRoot, self.id, InputFocus._None)

    def unfocus(self):
        self.border_color = passive_color
        self.update_border_color()

    def update_border_color(self):
        con.core.ChangeWindowAttributes(self.id, CW.BorderPixel, [self.border_color])

    def reparent(self, who, wm_state):
        self.parent = who
        con.core.ReparentWindow(self.id, self.parent, self.geo_virt.x, self.geo_virt.y)
        ChangeProperty(con.core, PropMode.Replace, self.id, _wm_atoms["WM_STATE"], Atom.CARDINAL, 32, 1, wm_state)

    def map(self):
        ChangeProperty(con.core, PropMode.Replace, self.id, _wm_atoms["WM_STATE"], Atom.CARDINAL, 32, 1, 1)
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

    def attach(self, workspace, teleport):
        if not teleport:
            geo_abs = self.absolute_geometry()
            self.geo_virt.x = geo_abs.x - workspace.screen.x
            self.geo_virt.y = geo_abs.y - workspace.screen.y

        self.__set_workspace(workspace)

    def send_config_window(self, x, y, w, h, b):
        sys.stderr.write("r_configure 0x%x: x %d y %d w %d h %d\n" % (self.id, x, y, w, h))
        mask = ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height|ConfigWindow.BorderWidth
        pkt = pack('=xx2xIH2xiiIII', self.id, mask, x, y, w, h, b)
        con.core.send_request(xcb.Request(pkt, 12, True, False), xcb.VoidCookie())

    def real_configure_notify(self):
        geo_abs = self.absolute_geometry()
        self.send_config_window(geo_abs.x, geo_abs.y, self.geo_virt.w, self.geo_virt.h, self.geo_virt.b)

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
# Events
#
def event_enter_notify(event):
    sys.stderr.write("enter notify 0x%x: %r\n" % (event.event, event.__dict__))
    global _ignore_next_enter_notify

    cl = _clients.get(event.event)
    if cl is None:
        return

    if _ignore_next_enter_notify:
        _ignore_next_enter_notify = False
        sys.stderr.write("** ignored **\n")
        return

    if not set_current_screen_from(cl.workspace.screen):
        sys.stderr.write("no screen for client 0x%x on workspace %s\n" % (cl.id, cl.workspace.name))
        return

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

def event_property_notify(event):
    sys.stderr.write("PropertyNotify %s: %s\n" % (con.core.GetAtomName(event.atom).reply().name.buf(), event.__dict__))

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
                   PropertyNotifyEvent:event_property_notify,
                   }

def event_handler(event):
    hdl = event_handlers.get(event.__class__, None)
    if hdl is not None:
        sys.stderr.write("--> %s\n" % event.__class__.__name__)
        hdl(event)
    else:
        sys.stderr.write("** Unhandled event ** %r %r\n" % (event.__class__.__name__, event.__dict__))

#
# Keyboard
#
class Keyboard:
    def __init__(self):
        self.__bindings = {}

    def attach(self, bindings, root):
        self.__root = root
        for m,k,f in bindings:
            if m is None:
                raise ValueError("missing modifier in keyboard bindings")

            if not self.__bindings.has_key(k):
                self.__bindings[k] = {}

            self.__bindings[k][m] = f
            con.core.GrabKey(False, self.__root, m, k, GrabMode.Async, GrabMode.Async)

    def detach(self):
        con.core.UngrabKey(False, self.__root, ModMask.Any)

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
            con.core.GrabButton(False, self.__root, emask, GrabMode.Async, GrabMode.Async, 0, 0, b, m)

    def detach(self):
        con.core.UngrabButton(False, self.__root, ButtonMask.Any)

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
        sys.stderr.write("no ext client found\n")
        return clients
    children = unpack_from("%dI" % reply.children_len, reply.children.buf())
    for cid in children:
        wa = con.core.GetWindowAttributes(cid).reply()
        if wa.map_state == MapState.Unmapped or wa.override_redirect:
            continue
        clients.append(cid)
    return clients

def add_ext_clients(ext_clients):
    for cid in ext_clients:
        geo = con.core.GetGeometry(cid).reply()
        gm = Geometry(geo.x, geo.y, geo.width, geo.height, 1)
        sys.stderr.write("ext client at x %d y %d w %d h %d b %d\n" % (gm.x, gm.y, gm.w, gm.h, gm.b))

        r = con.core.GetProperty(False, cid, _fp_wm_atoms["_FP_WM_WORKSPACE"], Atom.STRING, 0, 10).reply()
        lost_client = True
        if r.value_len != 0:
            for w in _workspaces:
                if w.name == str(r.value.buf()):
                    wk = w
                    lost_client = False
                    break

        if lost_client:
            sc = get_screen_at(gm)
            if sc is None:
                gm.x = 0
                gm.y = 0
                gm.w = 320
                gm.h = 240
                sc = get_screen_at(gm)
            wk = sc.active_workspace

        cl = Client(cid, _viewport.root, wk, gm)
        _clients[cid] = cl
        wk.add(cl)
        sys.stderr.write("acquired client 0x%x\n" % cid)

def release_clients():
    for c in _clients.itervalues():
        con.core.ReparentWindow(c.id, _viewport.root, c.geo_virt.x, c.geo_virt.y)
        c.send_config_window(c.geo_virt.x, c.geo_virt.y, c.geo_virt.w, c.geo_virt.h, c.geo_virt.b)

def Flat(format, data):
    f={32:'I',16:'H',8:'B'}[format]
    if not hasattr(data, "__iter__") and not hasattr(data, "__getitem__"):
        data = [data]
    return array(f, data).tostring()

def ChangeProperty(core, mode, window, property, type, format, data_len, data):
    core.ChangeProperty(mode, window, property, type, format, data_len, Flat(format, data))

def get_atoms(names, store):
    for n in names:
        store[n] = con.core.InternAtom(False, len(n), n)
    for n in store:
        store[n] = store[n].reply().atom

def proper_disconnect(msg):
    sys.stderr.write("%s\n" % msg)
    release_clients()
    mouse.detach()
    keyboard.detach()
    con.flush()
    con.disconnect()

def event_sigterm(signum, frame):
    proper_disconnect("received SIGTERM")
    sys.exit(0)

def event_sigint(signum, frame):
    proper_disconnect("received SIGINT")
    sys.exit(0)
#
# WM API
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

    if screen is None:
        return False

    if screen != focused_screen:
        focused_screen = screen
        update_workspace_info()

    return True

def current_screen():
    return focused_screen

def update_workspace_info():
    aw  = current_workspace()
    vw = []
    hw = []
    for w in _workspaces:
        if w.screen is None:
            hw.append(w)
        elif w != aw:
            vw.append(w)

    status_line.update(aw, vw, hw)

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
    c = current_client()
    if nwk is None or c is None:
        return

    cwk = c.workspace
    tiled = c.tiled

    sys.stderr.write("send_to_workspace %s -> %s\n" % (cwk.name, nwk.name))

    cwk.detach(c, tiled)
    nwk.attach(c, True)

    if nwk.screen is None:
        c.reparent(nwk.vroot, 0)
        update = False
    else:
        update = True

    if tiled:
        nwk.tile(c)
        c.stack_below()
    elif update:
        c.real_configure_notify()
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
    nwk = get_workspace_at(n)
    if nwk is not None and nwk != current_workspace() and nwk.screen is None:
        sys.stderr.write("goto_workspace %s -> %s\n" % (current_workspace().name, nwk.name))
        current_screen().set_workspace(nwk)

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

def increase_layout(stp):
    wk = current_workspace()
    wk.current_layout().increase(stp)
    wk.update()

def decrease_layout(stp):
    wk = current_workspace()
    wk.current_layout().decrease(stp)
    wk.update()

def spawn(*args):
    child = os.fork()
    if child != 0:
        os.waitpid(child, 0)
        return
    os.close(sys.stdout.fileno())
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
    l              = 46
    h              = 43
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

layouts = [LayoutVTall, LayoutHTall]

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

mouse_bindings    = [ (KeyMap.mod_alt, 1, move_client),
                      (KeyMap.mod_alt, 3, resize_client),
                      ]

def pretty_print(aw, vw, hw):
    sys.stdout.write("> %s < :: %s [%s | %s]\n" % (aw.name, aw.current_layout().name,
                                                   " ".join(map(lambda w: w.name,vw)),
                                                   " ".join(map(lambda w: w.name, hw))))
    sys.stdout.flush()

status_line = StatusLine(pretty_print, Gap(h=18))

focused_color = 0xff0000 # 0x94bff3
passive_color = 0x505050


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
keyboard = Keyboard()
mouse = Mouse()
_screens = []
_workspaces = []
_clients = {}
_ignore_next_enter_notify = False

wmname = "fpwm"

con = xcb.connect()
setup = con.get_setup()
_viewport = setup.roots[0]
xrandr = con(xcb.randr.key)

con.core.GrabServer()
while con.poll_for_event():
    pass

try:
    con.core.ChangeWindowAttributesChecked(_viewport.root, CW.EventMask, events).check()
except BadAccess, e:
    sys.stderr.write("A window manager is already running !\n")
    con.disconnect()
    sys.exit(1)

ext_clients = acquire_ext_clients(_viewport)

reply = xrandr.GetScreenResources(_viewport.root).reply()

if len(workspaces) < reply.num_crtcs:
    sys.stderr.write("Not enough workspaces\n")
    con.disconnect()
    sys.exit(1)

_wm_atoms = {}
_wm_atom_names = ["WM_STATE"]
get_atoms(_wm_atom_names, _wm_atoms)

_net_wm_atoms = {}
_net_wm_atom_names = ["_NET_SUPPORTED", "_NET_SUPPORTING_WM_CHECK", "_NET_WM_NAME", "_NET_WM_PID"]
# "_NET_STARTUP_ID", "_NET_CLIENT_LIST", "_NET_CLIENT_LIST_STACKING", "_NET_NUMBER_OF_DESKTOPS",
# "_NET_CURRENT_DESKTOP", "_NET_DESKTOP_NAMES", "_NET_ACTIVE_WINDOW", "_NET_DESKTOP_GEOMETRY",
# "_NET_CLOSE_WINDOW", "_NET_WM_STRUT_PARTIAL", "_NET_WM_ICON_NAME", "_NET_WM_VISIBLE_ICON_NAME",
# "_NET_WM_DESKTOP", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DESKTOP", "_NET_WM_WINDOW_TYPE_DOCK",
# "_NET_WM_WINDOW_TYPE_TOOLBAR", "_NET_WM_WINDOW_TYPE_MENU", "_NET_WM_WINDOW_TYPE_UTILITY",
# "_NET_WM_WINDOW_TYPE_SPLASH", "_NET_WM_WINDOW_TYPE_DIALOG", "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU",
# "_NET_WM_WINDOW_TYPE_POPUP_MENU", "_NET_WM_WINDOW_TYPE_TOOLTIP", "_NET_WM_WINDOW_TYPE_NOTIFICATION",
# "_NET_WM_WINDOW_TYPE_COMBO", "_NET_WM_WINDOW_TYPE_DND", "_NET_WM_WINDOW_TYPE_NORMAL", "_NET_WM_ICON",
# "_NET_WM_STATE", "_NET_WM_STATE_STICKY", "_NET_WM_STATE_SKIP_TASKBAR", "_NET_WM_STATE_FULLSCREEN",
# "_NET_WM_STATE_MAXIMIZED_HORZ", "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_ABOVE",
# "_NET_WM_STATE_BELOW", "_NET_WM_STATE_MODAL", "_NET_WM_STATE_HIDDEN", "_NET_WM_STATE_DEMANDS_ATTENTION"

get_atoms(_net_wm_atom_names, _net_wm_atoms)

ChangeProperty(con.core,PropMode.Replace,_viewport.root,
               _net_wm_atoms["_NET_SUPPORTED"], Atom.ATOM, 32, len(_net_wm_atoms), _net_wm_atoms.itervalues())

wm_win = con.generate_id()
con.core.CreateWindow(_viewport.root_depth,wm_win,_viewport.root,-1,-1,1,1,0,WindowClass.CopyFromParent,_viewport.root_visual,0,[])

ChangeProperty(con.core, PropMode.Replace, _viewport.root, _net_wm_atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, wm_win)
ChangeProperty(con.core, PropMode.Replace, wm_win, _net_wm_atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, wm_win)
ChangeProperty(con.core, PropMode.Replace, wm_win, _net_wm_atoms["_NET_WM_NAME"], Atom.STRING, 8, len(wmname), wmname)
ChangeProperty(con.core, PropMode.Replace, wm_win, _net_wm_atoms["_NET_WM_PID"], Atom.CARDINAL, 32, 1, os.getpid())

_fp_wm_atoms = {}
_fp_wm_atom_names = ["_FP_WM_WORKSPACE"]
get_atoms(_fp_wm_atom_names, _fp_wm_atoms)

for w in workspaces:
    _workspaces.append(Workspace(w, _viewport, layouts))

w = 0
screen_ids = unpack_from("%dI" % reply.num_crtcs, reply.crtcs.buf())
for sid in screen_ids:
    reply = xrandr.GetCrtcInfo(sid,0).reply()
    if reply.width == 0 or reply.height == 0:
        continue
    if status_line is not None and reply.x == status_line.gap.x:
        gap = status_line.gap
    else:
        gap = None
    scr = Screen(_viewport, reply.x, reply.y, reply.width, reply.height, _workspaces, gap)
    focused_screen = scr
    scr.set_workspace(_workspaces[w])
    _screens.append(scr)
    w += 1

add_ext_clients(ext_clients)

for w in _workspaces:
    if w.screen is not None:
        w.update()
    else:
        w.set_passive()

con.core.UngrabServer()
con.flush()
while con.poll_for_event():
    pass

keyboard.attach(keyboard_bindings, _viewport.root)
mouse.attach(mouse_bindings, _viewport.root)
signal.signal(signal.SIGTERM, event_sigterm)
signal.signal(signal.SIGINT, event_sigint)

while True:
    try:
        event_handler(con.wait_for_event())
        con.flush()
    except Exception, error:
        proper_disconnect("main: %s\n" % error.__class__.__name__)
        raise error
