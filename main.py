#!/usr/bin/env python

import sys, os

import xcb
from xcb.xproto import *

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
# Layouts
#
class LayoutTall:
    def __init__(self, screen, master_mapper, slaves_mapper):
        self.screen = screen
        self.__master_mapper = master_mapper
        self.__slaves_mapper = slaves_mapper

    def update(self, master, slaves):
        if master == None:
            return
        do_slaves = self.__master_mapper(master, slaves)
        master.manage()
        master.real_configure_notify()
        if do_slaves:
            self.__slaves_mapper(slaves)

class LayoutVTall(LayoutTall):
    def __init__(self, screen):
        LayoutTall.__init__(self, screen, self.__map_master, self.__map_slaves)

    def __map_master(self, master, slaves):
        master.geo_real.b = 1
        master.geo_real.x = 0
        master.geo_real.y = 0
        master.geo_real.h = self.screen.height - 2*master.geo_real.b

        if len(slaves) == 0:
            master.geo_real.w = self.screen.width - 2*master.geo_real.b
            return False

        master.geo_real.w = self.screen.width/2 - 2*master.geo_real.b
        return True

    def __map_slaves(self, slaves):
        L = len(slaves)
        if L != 0:
            H = self.screen.height/L
            for i in range(L):
                c = slaves[i]
                c.geo_real.x = self.screen.width/2
                c.geo_real.y = i*H
                c.geo_real.w = self.screen.width/2 - 2*c.geo_real.b
                c.geo_real.h = H - 2*c.geo_real.b
                c.real_configure_notify()

class LayoutHTall(LayoutTall):
    def __init__(self, screen):
        LayoutTall.__init__(self, screen, self.__map_master, self.__map_slaves)

    def __map_master(self, master, slaves):
        master.geo_real.b = 1
        master.geo_real.x = 0
        master.geo_real.y = 0
        master.geo_real.w = self.screen.width - 2*master.geo_real.b

        if len(slaves) == 0:
            master.geo_real.h = self.screen.height - 2*master.geo_real.b
            return False

        master.geo_real.h = self.screen.height/2 - 2*master.geo_real.b
        return True

    def __map_slaves(self, slaves):
        L = len(slaves)
        if L != 0:
            W = self.screen.width/L
            for i in range(L):
                c = slaves[i]
                c.geo_real.y = self.screen.height/2
                c.geo_real.x = i*W
                c.geo_real.h = self.screen.height/2 - 2*c.geo_real.b
                c.geo_real.w = W - (2*c.geo_real.b)
                c.real_configure_notify()

#
# Screens
#
class Screen:
    focused_color = 0x94bff3
    passive_color = 0x505050

    def __init__(self, screen):
        self.root = screen.root
        self.width = screen.width_in_pixels
        self.height = screen.height_in_pixels
        self.visual = screen.root_visual
        self.depth = screen.root_depth
        self.__clients = {}
        self.__master = None
        self.__slaves = []
        self.__layouts = [LayoutVTall(self), LayoutHTall(self)]
        self.current_layout = 0
        self.focused_client = None

    def setup(self):
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
            self.focused_client = None

        self.__clients.__delitem__(client.id)
        if len(self.__clients) == 0 and self.focused_client != None:
            self.focused_client = None

    def get_client(self, id):
        return self.__clients.get(id, None)

    def update(self):
        if self.__master != None:
            self.__layouts[self.current_layout].update(self.__master, self.__slaves)

    def next_layout(self):
        self.current_layout = (self.current_layout+1)%len(self.__layouts)
        self.update()

    def map(self, client):
        if self.__master is not None:
            self.__slaves.insert(0,self.__master)

        self.__master = client
        self.update()

    def unmap(self, client):
        if self.__master.id == client.id:
            self.__master = None
            if len(self.__slaves) == 0:
                return
            self.__master = self.__slaves.pop(0)
        else:
            self.__slaves.remove(client)

        self.update()

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

class Client:
    def __init__(self, event):
        self.id = event.window
        self.parent = event.parent
        self.geo_real = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.geo_want = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.border_color = Screen.passive_color
        self.managed = False

    def focus(self):
        self.border_color = Screen.focused_color
        self.update()

    def unfocus(self):
        self.border_color = Screen.passive_color
        self.update()

    def update(self):
        if self.managed:
            self.__update()

    def __update(self):
        mask  = EventMask.EnterWindow|EventMask.PropertyChange|EventMask.FocusChange
        values = [self.border_color, mask]
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

def event_key_press(event):
    keyboard.action(event.detail, event.state)

def event_key_release(event):
    print "Release:",event.detail, event.state, event.time

def event_motion_notify(event):
    mouse.motion(event)

def event_button_press(event):
    mouse.press(event)

def event_button_release(event):
    mouse.release(event)

#|EventMask.LeaveWindow
#|EventMask.ButtonPress|EventMask.ButtonRelease
events = [EventMask.SubstructureRedirect|EventMask.SubstructureNotify|EventMask.EnterWindow|EventMask.StructureNotify|EventMask.PropertyChange|EventMask.FocusChange]

event_handlers = { CreateNotifyEvent:event_create_notify,
                   DestroyNotifyEvent:event_destroy_notify,
                   ConfigureRequestEvent:event_configure_window_request,
                   MapRequestEvent:event_map_window,
                   EnterNotifyEvent:event_enter_notify,
                   KeyPressEvent:event_key_press,
                   KeyReleaseEvent:event_key_release,
                   MotionNotifyEvent:event_motion_notify,
                   ButtonPressEvent:event_button_press,
                   ButtonReleaseEvent:event_button_release,
                   }

def event_handler(event):
    hdl = event_handlers.get(event.__class__, None)
    if hdl is None:
        print "** Unhandled ** ",event.__class__.__name__, event.__dict__
    else:
        print "--> ",event.__class__.__name__
        hdl(event)

#
# Keyboard & Mouse
#
class Mappings:
    # XXX: Mod2 is always set on KeyEvent (python-xcb or Xephyr bug ?)
    modifier = KeyButMask.Mod1|KeyButMask.Mod2
    space = 65
    move_button = 1
    resize_button = 3

class Keyboard:
    def __init__(self):
        self.__hotkeys = {
            Mappings.space: lambda: current_screen().next_layout()
            }

    def attach(self):
        c = current_client()
        con.core.GrabKey(False, c, Mappings.modifier, 0, GrabMode.Async, GrabMode.Async)

    def detach(self):
        c = current_client()
        con.core.UngrabKey(False, c, ModMask.Any)

    def action(self, key, mods):
        act = self.__hotkeys.get(key, None)
        if act is not None:
            act()

#
# We thought we can update mask to prevent other button press/release while move/resize
# however this did not work as expected so we do it our own way
#
class Mouse:
    def __init__(self):
        self.__mv_b_mask = eval("EventMask.Button%dMotion" % Mappings.move_button)
        self.__rz_b_mask = eval("EventMask.Button%dMotion" % Mappings.resize_button)

    def attach(self):
        mask = EventMask.ButtonPress|EventMask.ButtonRelease|EventMask.Button1Motion|EventMask.Button3Motion
        button = 0 #any
        con.core.GrabButton(False, current_client(), mask, GrabMode.Async, GrabMode.Async, 0, 0, button, Mappings.modifier)

    def detach(self):
        con.core.UngrabButton(False, current_client(), ButtonMask.Any)

    def motion(self, event):
        # several buttons may be selected, however move is higher priority for us
        if event.state & self.__mv_b_mask:
            return self.move(event)
        elif event.state & self.__rz_b_mask:
            return self.resize(event)

    def move(self, event):
        print "move"

    def resize(self, event):
        print "resize"

    def press(self, event):
        button = event.detail
        print "press", button

    def release(self, event):
        button = event.detail
        print "release", button

#
# Main
#
keyboard = Keyboard()
mouse = Mouse()
_screens = []

def current_screen():
    return _screens[0]

def current_client():
    c = current_screen().focused_client
    if c is None:
        return current_screen().root
    return c.id

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
    scr.setup()
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
keyboard.attach()
mouse.attach()

while True:
    try:
        event = con.wait_for_event()
    except Exception, error:
        print error.__class__.__name__
        con.disconnect()
        sys.exit(1)

    event_handler(event)
    con.flush()

mouse.detach()
keyboard.detach()
con.disconnect()
