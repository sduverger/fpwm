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

    def tile(self, client):
        if client.tiled:
            return

        client.tile()
        if self.__master is not None:
            self.__slaves.insert(0,self.__master)

        self.__master = client
        self.update()

    def untile(self, client):
        if not client.tiled:
            return

        client.untile()
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
    def __init__(self, event, screen):
        self.id = event.window
        self.parent = event.parent
        self.geo_real = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.geo_want = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.border_color = Screen.passive_color
        self.screen = screen
        self.tiled = False

    def focus(self):
        self.border_color = Screen.focused_color
        self.update()

    def unfocus(self):
        self.border_color = Screen.passive_color
        self.update()

    def check_size(self):
        if self.geo_real.w <= 20:
            self.geo_real.w = 20

        if self.geo_real.h <= 20:
            self.geo_real.h = 20

    def move(self, dx, dy):
        self.geo_real.x += dx
        self.geo_real.y += dy
        self.real_configure_notify()

    def resize(self, up, left, dx, dy):
        if up and left:
            self.move(dx, dy)
            dy = -dy
            dx = -dx
        elif up and not left:
            self.move(0, dy)
            dy = -dy
        elif not up and left:
            self.move(dx, 0)
            dx = -dx

        self.geo_real.w += dx
        self.geo_real.h += dy
        self.check_size()
        self.real_configure_notify()

    def update(self):
        if self.tiled:
            self.__update()

    def __update(self):
        mask  = EventMask.EnterWindow|EventMask.PropertyChange|EventMask.FocusChange
        values = [self.border_color, mask]
        con.core.ChangeWindowAttributesChecked(self.id, CW.BorderPixel|CW.EventMask, values)
        #con.core.MapWindow(self.id)

    def tile(self):
        if not self.tiled:
            self.tiled = True
            self.__update()

    def untile(self):
        if self.tiled:
            self.tiled = False
            self.stack_above()

    def destroy(self):
        pass

    def stack_above(self):
        con.core.ConfigureWindow(self.id, ConfigWindow.StackMode, [StackMode.Above])

    def real_configure_notify(self):
        mask = ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height|ConfigWindow.BorderWidth
        pkt = pack('=xx2xIH2xiiIII',
                   self.id, mask,
                   self.geo_real.x, self.geo_real.y,
                   self.geo_real.w, self.geo_real.h, self.geo_real.b)
        con.core.send_request(xcb.Request(pkt, 12, True, False), xcb.VoidCookie())

    def synthetic_configure_notify(self):
        # cf. xcb/xproto.h
        event = pack("=B3xIIIHHHHHBx",
                     22, self.id, self.id, 0,
                     self.geo_want.x, self.geo_want.y, self.geo_want.w, self.geo_want.h, self.geo_want.b,0)
        con.core.SendEvent(False, self.id, EventMask.StructureNotify, event)

    def moveresize(self):
        print "client moveresize -----XXXXXX-----"
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
    #XXX: get screen from event root
    scr = current_screen()
    client = scr.get_client(event.window)
    if client is None:
        vanilla_configure_window_request(event)
    else:
        client.configure(event)

def event_create_notify(event):
    #XXX: get screen from event root
    if event.override_redirect == 0:
        print "new client %d" % event.window
        current_screen().add_client(Client(event, current_screen()))

def event_destroy_notify(event):
    #XXX: get screen from event root
    scr = current_screen()
    client = scr.get_client(event.window)
    if client is not None:
        print "destroy client %d" % event.window
        if(client.tiled):
            scr.untile(client)
        scr.del_client(client)

def event_map_window(event):
    #XXX: get screen from event root
    scr = current_screen()
    client = scr.get_client(event.window)
    if client is not None:
        tile(client)
        con.core.MapWindow(event.window)

def event_enter_notify(event):
    #XXX: get screen from event root
    scr = current_screen()
    client = scr.get_client(event.event)
    if client is not None:
        scr.update_focus(client)

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
        print "key press:",event.detail, event.state
        self.__bindings[event.detail][event.state]()

    def release(self, event):
        print "key release:",event.detail, event.state

class Mouse:
    def __init__(self):
        self.__acting = None
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

        dx = event.event_x - self.__x
        dy = event.event_y - self.__y

        self.__acting(self.__up, self.__left, dx, dy)

        self.__x = event.event_x
        self.__y = event.event_y

    def press(self, event):
        print "button press:",event.__dict__
        if self.__acting is not None:
            return

        c = current_client()
        if c is None:
            return

        self.__acting = self.__bindings[event.detail][event.state]
        self.__x = event.event_x
        self.__y = event.event_y

        if self.__x < c.geo_real.x+(2*c.geo_real.b+c.geo_real.w)/2:
            self.__left = True
        else:
            self.__left = False

        if self.__y < c.geo_real.y+(2*c.geo_real.b+c.geo_real.h)/2:
            self.__up = True
        else:
            self.__up = False

    def release(self, event):
        print "button release:",event.__dict__
        self.__acting = None


#
# Services
#
def current_screen():
    return _screens[0]

def next_layout():
    current_screen().next_layout()

def current_client():
    # may be None (no client)
    return current_screen().focused_client

def current_client_id():
    c = current_client()
    if c is None:
        return current_screen().root
    return c.id

def tile(c):
    if c is not None and not c.tiled:
        c.screen.tile(c)

def untile(c):
    if c is not None and c.tiled:
        c.screen.untile(c)

def tile_client():
    tile(current_client())

def untile_client():
    untile(current_client())

def move_client(up, left, dx, dy):
    c = current_client()
    if c is not None:
        untile(c)
        c.move(dx, dy)

def resize_client(up, left, dx, dy):
    c = current_client()
    if c is not None:
        untile(c)
        c.resize(up, left, dx, dy)

desktop_toggle = False
def toggle_show_desktop():
    global desktop_toggle
    if not desktop_toggle:
        con.core.UnmapSubwindows(current_screen().root)
        desktop_toggle = True
    else:
        con.core.MapSubwindows(current_screen().root)
        desktop_toggle = False
#
# Bindings
#
class KeyMap:
    space          = 65
    t              = 28
    d              = 40


# XXX: KeyButMask.Mod2 is always set (xpyb/Xephyr bug ?)
keyboard_bindings = [ (KeyButMask.Mod2|KeyButMask.Mod1,                    KeyMap.space,    next_layout),
                      (KeyButMask.Mod2|KeyButMask.Mod1,                    KeyMap.t,        tile_client),
                      (KeyButMask.Mod2|KeyButMask.Mod1,                    KeyMap.d,        toggle_show_desktop),
                      ]

mouse_bindings    = [ (KeyButMask.Mod2|KeyButMask.Mod1,                    1,               move_client),
                      (KeyButMask.Mod2|KeyButMask.Mod1,                    3,               resize_client),
                      ]


#
# Main
#
keyboard = Keyboard()
mouse = Mouse()
_screens = []

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
keyboard.attach(keyboard_bindings)
mouse.attach(mouse_bindings)

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
