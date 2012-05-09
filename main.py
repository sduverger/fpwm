#!/usr/bin/env python

import sys, os

import xcb
from xcb.xproto import *

wmname = "fpwm"

events = [EventMask.SubstructureRedirect|EventMask.SubstructureNotify|EventMask.EnterWindow|EventMask.LeaveWindow|EventMask.StructureNotify|EventMask.PropertyChange|EventMask.ButtonPress|EventMask.ButtonRelease|EventMask.FocusChange]

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
# Layouts
#
class LayoutTall:
    def __init__(self, screen, master_mapper, slaves_mapper):
        self.screen = screen
        self.master = None
        self.slaves = {}
        self.slaves_ordered = []
        self.__master_mapper = master_mapper
        self.__slaves_mapper = slaves_mapper

    def map(self, c):
        if self.master is not None:
            self.slaves[self.master.id] = self.master
            self.slaves_ordered.insert(0,self.master.id)

        self.master = c
        self.__master_mapper()
        self.master.manage()
        self.master.real_configure_notify()
        self.__slaves_mapper()

    def unmap(self, c):
        if c.id == self.master.id:
            self.master = None
            if len(self.slaves_ordered) != 0:
                nm = self.slaves[self.slaves_ordered[0]]
                self.slaves[nm.id] = None
                self.slaves_ordered = self.slaves_ordered[1:]
                self.map(nm)
        else:
            self.slaves_ordered.remove(c.id)
            self.slaves[c.id] = None

            if len(self.slaves_ordered) == 0:
                nm = self.master
                self.master = None
                self.map(nm)
            else:
                self.__slaves_mapper()

class LayoutVTall(LayoutTall):
    def __init__(self, screen):
        LayoutTall.__init__(self, screen, self.__map_master, self.__map_slaves)

    def __map_master(self):
        self.master.geo_real.b = 1
        self.master.geo_real.x = 0
        self.master.geo_real.y = 0
        self.master.geo_real.h = self.screen.height - 2*self.master.geo_real.b

        if len(self.slaves_ordered) == 0:
            self.master.geo_real.w = self.screen.width - 2*self.master.geo_real.b
        else:
            self.master.geo_real.w = self.screen.width/2 - 2*self.master.geo_real.b

    def __map_slaves(self):
        if len(self.slaves_ordered) == 0:
            return
        L = len(self.slaves_ordered)
        H = self.screen.height/L
        for i in range(L):
            c = self.slaves[self.slaves_ordered[i]]
            c.geo_real.x = self.screen.width/2
            c.geo_real.y = i*H
            c.geo_real.w = self.screen.width/2 - 2*c.geo_real.b
            c.geo_real.h = H - 2*c.geo_real.b
            c.real_configure_notify()

class LayoutHTall(LayoutTall):
    def __init__(self, screen):
        LayoutTall.__init__(self, screen, self.__map_master, self.__map_slaves)

    def __map_master(self):
        self.master.geo_real.b = 1
        self.master.geo_real.x = 0
        self.master.geo_real.y = 0
        self.master.geo_real.w = self.screen.width - 2*self.master.geo_real.b

        if len(self.slaves_ordered) == 0:
            self.master.geo_real.h = self.screen.height - 2*self.master.geo_real.b
        else:
            self.master.geo_real.h = self.screen.height/2 - 2*self.master.geo_real.b

    def __map_slaves(self):
        if len(self.slaves_ordered) == 0:
            return
        L = len(self.slaves_ordered)
        W = self.screen.width/L
        for i in range(L):
            c = self.slaves[self.slaves_ordered[i]]
            c.geo_real.y = self.screen.height/2
            c.geo_real.x = i*W
            c.geo_real.h = self.screen.height/2 - 2*c.geo_real.b
            c.geo_real.w = W - (2*c.geo_real.b)
            c.real_configure_notify()

#
# Screens
#
class Screen:
    def __init__(self, screen):
        self.root = screen.root
        self.width = screen.width_in_pixels
        self.height = screen.height_in_pixels
        self.visual = screen.root_visual
        self.depth = screen.root_depth
        self.__clients = {}
        self.__layouts = [LayoutVTall(self), LayoutHTall(self)]
        self.current_layout = 0
        self.focused_client = None

    def setup(self, con, atoms):
        ChangeProperty(con.core, PropMode.Replace, self.root, atoms["_NET_SUPPORTED"], Atom.ATOM, 32, len(atoms), atoms.itervalues())
        self.vroot = con.generate_id()
        con.core.CreateWindow(self.depth, self.vroot, self.root, -1, -1, 1, 1, 0, WindowClass.CopyFromParent, self.visual, 0, [])
        print "Root window: %d | Virtual root: %d" % (self.root, self.vroot)
        ChangeProperty(con.core, PropMode.Replace, self.root,  atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, self.vroot)
        ChangeProperty(con.core, PropMode.Replace, self.vroot, atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, self.vroot)
        ChangeProperty(con.core, PropMode.Replace, self.vroot, atoms["_NET_WM_NAME"], Atom.STRING, 8, len(wmname), wmname)
        ChangeProperty(con.core, PropMode.Replace, self.vroot, atoms["_NET_WM_PID"], Atom.CARDINAL, 32, 1, os.getpid())

    def add_client(self, client):
        self.__clients[client.id] = client

    def del_client(self, client):
        if self.focused_client == client:
            client.unfocus()
        self.__clients.__delitem__(client.id)
        if len(self.__clients) == 0:
            self.focused_client = None

    def get_client(self, id):
        return self.__clients.get(id, None)

    def map(self, client):
        self.__layouts[self.current_layout].map(client)

    def unmap(self, client):
        self.__layouts[self.current_layout].unmap(client)

    def update_focus(self, client):
        if self.focused_client is not None:
            self.focused_client.unfocus()
        self.focused_client = client
        self.focused_client.focus()


#
# Clients
#
class Geometry:
    def __init__(self, x,y, w,h, b):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.b = b

focused_border_pixel = 0x94bff3
unfocused_border_pixel = 0x505050

class Client:
    def __init__(self, event):
        self.id = event.window
        self.parent = event.parent
        self.geo_real = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.geo_want = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.border_color = unfocused_border_pixel
        self.managed = False

    def focus(self):
        self.border_color = focused_border_pixel
        self.update()

    def unfocus(self):
        self.border_color = unfocused_border_pixel
        self.update()

    def update(self):
        if self.managed:
            self.__update()

    def __update(self):
        values = [self.border_color, EventMask.EnterWindow|EventMask.PropertyChange|EventMask.FocusChange]
        con.core.ChangeWindowAttributesChecked(self.id, CW.BorderPixel|CW.EventMask, values)
        #con.core.MapWindow(self.id)

    def manage(self):
        if self.managed:
            return

        self.managed = True
        self.__update()

    def destroy(self):
        pass

    def real_configure_notify(self):
        mask = ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height|ConfigWindow.BorderWidth
        values = [self.geo_real.x, self.geo_real.y, self.geo_real.w, self.geo_real.h, self.geo_real.b]
        con.core.ConfigureWindow(self.id, mask, values)

    def synthetic_configure_notify(self):
        # cf. xcb/xproto.h
        event = pack("=B3xIIIHHHHHBx",
                     22, self.id, self.id, 0,
                     self.geo_want.x, self.geo_want.y, self.geo_want.w, self.geo_want.h, self.geo_want.b,0)
        con.core.SendEvent(False, self.id, EventMask.StructureNotify, event)

    def moveresize(self):
        if self.geo_want.x != self.geo_real.x:
            self.geo_real.x = self.geo_want.x

        if self.geo_want.y != self.geo_real.y:
            self.geo_real.y = self.geo_want.y

        if self.geo_want.w != self.geo_real.w:
            self.geo_real.w = self.geo_want.w

        if self.geo_want.h != self.geo_real.h:
            self.geo_real.h = self.geo_want.h

        self.real_configure_notify()

    def configure(self, event):
        print "configuring client %d" % self.id

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

        if event.value_mask & (ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height):
            return self.moveresize()

        return self.synthetic_configure_notify()

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

#
# Events
#
def event_configure_window_request(event):
    scr = current_screen()
    client = scr.get_client(event.window)
    if client is None:
        vanilla_configure_window_request(event)
    else:
        client.configure(event)

def event_create_notify(event):
    if event.override_redirect == 0:
        print "new client %d" % event.window
        current_screen().add_client(Client(event))

def event_destroy_notify(event):
    scr = current_screen()
    client = scr.get_client(event.window)
    if client is not None:
        print "destroy client %d" % event.window
        if(client.managed):
            scr.unmap(client)
        scr.del_client(client)

def event_map_window(event):
    scr = current_screen()
    client = scr.get_client(event.window)
    if client is not None:
        scr.map(client)

    con.core.MapWindow(event.window)

def event_enter_notify(event):
    scr = current_screen()
    client = scr.get_client(event.event)
    if client is not None:
        scr.update_focus(client)

event_handlers = { CreateNotifyEvent:event_create_notify,
                   DestroyNotifyEvent:event_destroy_notify,
                   ConfigureRequestEvent:event_configure_window_request,
                   MapRequestEvent:event_map_window,
                   EnterNotifyEvent:event_enter_notify
                   }

def event_handler(event):
    hdl = event_handlers.get(event.__class__, None)
    if hdl is None:
        print "** Unhandled ** ",event.__class__.__name__, event.__dict__
    else:
        print "--> ",event.__class__.__name__
        hdl(event)

#
# Main
#
_screens = []

def current_screen():
    return _screens[0]

con = xcb.connect()
con.core.GrabServer()

setup = con.get_setup()

atoms = {}
for n in atom_names:
    atoms[n] = con.core.InternAtom(False, len(n), n)

for n in atoms:
    atoms[n] = atoms[n].reply().atom

for s in setup.roots:
    scr = Screen(s)
    scr.setup(con, atoms)
    _screens.append(scr)

while con.poll_for_event():
    pass

try:
    con.core.ChangeWindowAttributesChecked(current_screen().root, CW.EventMask, events).check()
except BadAccess, e:
    print "A window manager is already running !"
    con.disconnect()
    sys.exit(1)

con.core.UngrabServer()
con.flush()

while True:
    try:
        event = con.wait_for_event()
    except Exception, error:
        print error.__class__.__name__
        con.disconnect()
        sys.exit(1)

    event_handler(event)
    con.flush()

con.disconnect()
