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
              #"_NET_WM_STATE_DEMANDS_ATTENTION"
              ]

con = xcb.connect()
con.core.GrabServer()

setup = con.get_setup()
screen= setup.roots[0]

atoms = {}
for n in atom_names:
    atoms[n] = con.core.InternAtom(False, len(n), n)

for n in atoms:
    atoms[n] = atoms[n].reply().atom


con.core.ChangeProperty(PropMode.Replace, screen.root, atoms["_NET_SUPPORTED"], Atom.ATOM, 32, len(atoms), atoms.itervalues())

virtual_root = con.generate_id()
con.core.CreateWindow(screen.root_depth, virtual_root,
                      screen.root, -1, -1, 1, 1, 0, WindowClass.CopyFromParent, screen.root_visual, 0, [])

print "Root window: %d | Virtual root: %d" % (screen.root, virtual_root)

def Flat(format, list):
    f={32:'I',16:'H',8:'B'}[format]
    return array(f, list).tostring()

con.core.ChangeProperty(PropMode.Replace, screen.root, atoms["_NET_SUPPORTING_WM_CHECK"], Atom.WINDOW, 32, 1, Flat(32,[virtual_root]))
con.core.ChangeProperty(PropMode.Replace, virtual_root, atoms["_NET_SUPPORTING_WM_CHECK"],Atom.WINDOW, 32, 1, Flat(32,[virtual_root]))

con.core.ChangeProperty(PropMode.Replace, virtual_root, atoms["_NET_WM_NAME"], Atom.STRING, 8, len(wmname), wmname)
con.core.ChangeProperty(PropMode.Replace, virtual_root, atoms["_NET_WM_PID"], Atom.CARDINAL, 32, 1, Flat(32, [os.getpid()]))

while con.poll_for_event():
    pass

try:
    con.core.ChangeWindowAttributesChecked(screen.root, CW.EventMask, events).check()
except BadAccess, e:
    print "A window manager is already running !"
    con.disconnect()
    sys.exit(1)

con.core.UngrabServer()
con.flush()

clients = {}

class Client:
    def __init__(self, event):
        self.id = event.window
        self.parent = event.parent

        self.x_rel = event.x
        self.y_rel = event.y

        self.width = event.width
        self.height = event.height
        self.border = event.border_width

# def client_resize():
#     mask = x|y|width|height
#     configure_window_request()

def client_configure_window(client, event):
    print "configuring client %d" % client.id
    #get x,y,w,h
    #get border
    #del sibling stack
    #if not client_resize():
    #    send_configure_notify(STRUCTURE_NOTIFY)

# ConfigureRequestEvent
# {'parent': 289, 'width': 10, 'stack_mode': 0, 'height': 17, 'sibling': 0, 'window': 4194317, 'y': 0, 'x': 0, 'border_width': 1, 'value_mask': 12}

# ConfigureRequestEvent
# {'parent': 289, 'width': 484, 'stack_mode': 0, 'height': 316, 'sibling': 0, 'window': 4194317, 'y': 0, 'x': 0, 'border_width': 1, 'value_mask': 12}

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
    if client:
        client_configure_window(client, event)
    else:
        vanilla_configure_window_request(event)

def event_create_notify(event):
    if event.override_redirect == 0:
        print "new client %d" % event.window
        clients[event.window] = Client(event)

def event_map_window(event):
    con.core.MapWindow(event.window)

event_handlers = { CreateNotifyEvent:event_create_notify,
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
