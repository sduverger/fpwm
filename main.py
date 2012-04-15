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

con = xcb.connect()
con.core.GrabServer()

setup = con.get_setup()

class LayoutTall:
    def __init__(self, screen):
        self.screen = screen
        self.master = None
        self.slaves = []

    def map(self, nc, clist):
        if not nc.tilled:
            # become master
            nc.tilled = True
            nc.geo_real.b = 1
            nc.geo_real.w = (self.screen.width - 2*nc.geo_real.b)/2
            nc.geo_real.x = 0
            nc.geo_real.y = 0

            nc.geo_real.h = self.screen.height - 2*nc.geo_real.b
            nc.real_configure_notify()

            if self.master is None:
                self.master = nc.id
                return

            if len(self.slaves) == 0 :
                self.slaves.append(clist[self.master])
                self.master = nc.id
            else:
                self.slaves.append(nc)

            l = len(self.slaves)
            h = (self.screen.height/l) - (l*2*nc.geo_real.b)
            for i in range(l):
                c = self.slaves[i]
                c.geo_real.x = self.screen.width/2 + 2*nc.geo_real.b
                c.geo_real.y = i*(h + 2*nc.geo_real.b)
                c.geo_real.h = h
                c.real_configure_notify()

class Screen:
    def __init__(self, screen):
        self.root = screen.root
        self.width = screen.width_in_pixels
        self.height = screen.height_in_pixels
        self.visual = screen.root_visual
        self.depth = screen.root_depth
        self.__clients = {}
        self.layout = LayoutTall(self)

    def add_client(self, client):
        self.__clients[client.id] = client

    def del_client(self, client):
        self.__clients[client.id] = None

    def get_client(self, id):
        return self.__client.get(id, None)

    def map(self, client):
        c = self.__clients[client.id]
        self.layout.map(c, self.__clients)

screens = []
for s in setup.roots:
    screens.append(Screen(s))

def current_screen():
    return screens[0]

atoms = {}
for n in atom_names:
    atoms[n] = con.core.InternAtom(False, len(n), n)

for n in atoms:
    atoms[n] = atoms[n].reply().atom

con.core.ChangeProperty(PropMode.Replace, screens[0].root, atoms["_NET_SUPPORTED"], Atom.ATOM, 32, len(atoms), atoms.itervalues())

virtual_root = con.generate_id()
con.core.CreateWindow(screens[0].depth, virtual_root,
                      screens[0].root, -1, -1, 1, 1, 0, WindowClass.CopyFromParent, screens[0].visual, 0, [])

print "Root window: %d | Virtual root: %d" % (screens[0].root, virtual_root)

def Flat(format, list):
    f={32:'I',16:'H',8:'B'}[format]
    return array(f, list).tostring()

con.core.ChangeProperty(PropMode.Replace, screens[0].root, atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, Flat(32,[virtual_root]))
con.core.ChangeProperty(PropMode.Replace, virtual_root, atoms["_NET_SUPPORTING_WM_CHECK"],Atom.WINDOW, 32, 1, Flat(32,[virtual_root]))

con.core.ChangeProperty(PropMode.Replace, virtual_root, atoms["_NET_WM_NAME"], Atom.STRING, 8, len(wmname), wmname)
con.core.ChangeProperty(PropMode.Replace, virtual_root, atoms["_NET_WM_PID"], Atom.CARDINAL, 32, 1, Flat(32, [os.getpid()]))

while con.poll_for_event():
    pass

try:
    con.core.ChangeWindowAttributesChecked(screens[0].root, CW.EventMask, events).check()
except BadAccess, e:
    print "A window manager is already running !"
    con.disconnect()
    sys.exit(1)

con.core.UngrabServer()
con.flush()

clients = {}

class Geometry:
    def __init__(self, x,y, w,h, b):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.b = b

class Client:
    def __init__(self, event):
        self.id = event.window
        self.parent = event.parent
        self.geo_real = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.geo_want = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.screen = current_screen()
        self.tilled = False
        self.screen.add_client(self)

    def destroy(self):
        self.screen.del_client(self)

    def real_configure_notify(self):
        mask = ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height|ConfigWindow.BorderWidth
        values = [self.geo_real.x, self.geo_real.y, self.geo_real.w, self.geo_real.h, self.geo_real.b]
        con.core.ConfigureWindow(self.id, mask, values)

    def synthetic_configure_notify(self):
        e = ConfigureNotifyEvent(self.parent)
        e.x = self.geo_want.x
        e.y = self.geo_want.y
        e.width = self.geo_want.w
        e.height = self.geo_want.h
        e.border_width = self.geo_want.b
        e.override_redirect = 0
        e.above_sibling = 0
        e.window = self.id
        con.core.SendEvent(False, self.id, EventMask.StructureNotify, e)

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

def event_configure_window_request(event):
    client = clients.get(event.window, None)
    if client is None:
        vanilla_configure_window_request(event)
    else:
        client.configure(event)

def event_create_notify(event):
    if event.override_redirect == 0:
        print "new client %d" % event.window
        clients[event.window] = Client(event)

def event_destroy_notify(event):
    clients[event.window].destroy()
    clients[event.window] = None

def event_map_window(event):
    client = clients.get(event.window, None)
    if client is not None:
        client.screen.map(client)

    con.core.MapWindow(event.window)


event_handlers = { CreateNotifyEvent:event_create_notify,
                   DestroyNotifyEvent:event_destroy_notify,
                   ConfigureRequestEvent:event_configure_window_request,
                   MapRequestEvent:event_map_window
                   }

def event_handler(event):
    hdl = event_handlers.get(event.__class__, None)
    if hdl is None:
        print "** Unhandled ** ",event.__class__.__name__, event.__dict__
    else:
        print "--> ",event.__class__.__name__
        hdl(event)

# event loop
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
