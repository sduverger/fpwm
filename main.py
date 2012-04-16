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

#
# Layouts
#
class LayoutTall:
    def __init__(self, screen):
        self.screen = screen
        self.master = None
        self.slaves = {}
        self.slaves_ordered = []

    def map(self, nc):
        nc.geo_real.b = 1
        nc.geo_real.x = 0
        nc.geo_real.y = 0
        nc.geo_real.h = self.screen.height - 2*nc.geo_real.b

        if self.master is not None:
            self.slaves[self.master.id] = self.master
            self.slaves_ordered.insert(0,self.master.id)

        self.master = nc

        if len(self.slaves_ordered) == 0:
            self.master.geo_real.w = (self.screen.width - 2*nc.geo_real.b)
        else:
            self.master.geo_real.w = (self.screen.width - 2*nc.geo_real.b)/2
            self.remap_slaves()

        self.master.manage()
        self.master.real_configure_notify()

    def remap_slaves(self):
        L = len(self.slaves_ordered)
        H = self.screen.height/L
        for i in range(L):
            c = self.slaves[self.slaves_ordered[i]]
            c.geo_real.x = self.screen.width/2
            c.geo_real.y = i*H
            c.geo_real.w = (self.screen.width - 2*c.geo_real.b)/2
            c.geo_real.h = H - (2*c.geo_real.b)
            c.real_configure_notify()

    def unmap(self, nc):
        if nc.id == self.master.id:
            self.master = None
            if len(self.slaves_ordered) != 0:
                nm = self.slaves[self.slaves_ordered[0]]
                self.slaves[nm.id] = None
                self.slaves_ordered = self.slaves_ordered[1:]
                self.map(nm)
        else:
            self.slaves_ordered.remove(nc.id)
            self.slaves[nc.id] = None

            if len(self.slaves_ordered) != 0:
                self.remap_slaves()
            else:
                nm = self.master
                self.master = None
                self.map(nm)

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
        self.layout = LayoutTall(self)

    def add_client(self, client):
        self.__clients[client.id] = client

    def del_client(self, client):
        self.__clients[client.id] = None

    def get_client(self, id):
        return self.__clients.get(id, None)

    def map(self, client):
        self.layout.map(client)

    def unmap(self, client):
        self.layout.unmap(client)

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

class Client:
    def __init__(self, event):
        self.id = event.window
        self.parent = event.parent
        self.geo_real = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.geo_want = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.managed = False

    def manage(self):
        if self.managed:
            return

        values = [EventMask.EnterWindow|EventMask.PropertyChange|EventMask.FocusChange]
        con.core.ChangeWindowAttributesChecked(self.id, CW.EventMask, values)
        self.managed = True

    def destroy(self):
        pass

    def real_configure_notify(self):
        mask = ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height|ConfigWindow.BorderWidth
        values = [self.geo_real.x, self.geo_real.y, self.geo_real.w, self.geo_real.h, self.geo_real.b]
        con.core.ConfigureWindow(self.id, mask, values)

    def synthetic_configure_notify(self):
        """ cf. xcb/xproto.h
865 #define XCB_CONFIGURE_NOTIFY 22
866 
867 /**
868  * @brief xcb_configure_notify_event_t
869  **/
870 typedef struct xcb_configure_notify_event_t {
871     uint8_t      response_type; /**<  */
872     uint8_t      pad0; /**<  */
873     uint16_t     sequence; /**<  */
874     xcb_window_t event; /**<  */
875     xcb_window_t window; /**<  */
876     xcb_window_t above_sibling; /**<  */
877     int16_t      x; /**<  */
878     int16_t      y; /**<  */
879     uint16_t     width; /**<  */
880     uint16_t     height; /**<  */
881     uint16_t     border_width; /**<  */
882     uint8_t      override_redirect; /**<  */
883     uint8_t      pad1; /**<  */
884 } xcb_configure_notify_event_t;
"""
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

#
# Main
#
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
