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
# Screen
#
class Screen:
    focused_color = 0x94bff3
    passive_color = 0x505050

    def __init__(self, screen, workspaces):
        self.root = screen.root
        self.width = screen.width_in_pixels
        self.height = screen.height_in_pixels
        self.visual = screen.root_visual
        self.depth = screen.root_depth
        self.workspaces = workspaces
        self.active_workspace = None

    def setup(self):
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
        master.geo_real.b = 1
        master.geo_real.x = 0
        master.geo_real.y = 0
        master.geo_real.h = self.workspace.screen.height - 2*master.geo_real.b

        if len(slaves) == 0:
            master.geo_real.w = self.workspace.screen.width - 2*master.geo_real.b
            do_slaves = False
        else:
            master.geo_real.w = self.workspace.screen.width/2 - 2*master.geo_real.b
            do_slaves = True

        master.real_configure_notify()
        return do_slaves

    def __map_slaves(self, slaves):
        L = len(slaves)
        if L != 0:
            H = self.workspace.screen.height/L
            for i in range(L):
                c = slaves[i]
                c.geo_real.x = self.workspace.screen.width/2
                c.geo_real.y = i*H
                c.geo_real.w = self.workspace.screen.width/2 - 2*c.geo_real.b
                c.geo_real.h = H - 2*c.geo_real.b
                c.real_configure_notify()

class LayoutHTall(LayoutTall):
    def __init__(self, workspace):
        LayoutTall.__init__(self, workspace, self.__map_master, self.__map_slaves)

    def __map_master(self, master, slaves):
        master.geo_real.b = 1
        master.geo_real.x = 0
        master.geo_real.y = 0
        master.geo_real.w = self.workspace.screen.width - 2*master.geo_real.b

        if len(slaves) == 0:
            master.geo_real.h = self.workspace.screen.height - 2*master.geo_real.b
            do_slaves = False
        else:
            master.geo_real.h = self.workspace.screen.height/2 - 2*master.geo_real.b
            do_slaves = True

        master.real_configure_notify()
        return do_slaves

    def __map_slaves(self, slaves):
        L = len(slaves)
        if L != 0:
            W = self.workspace.screen.width/L
            for i in range(L):
                c = slaves[i]
                c.geo_real.y = self.workspace.screen.height/2
                c.geo_real.x = i*W
                c.geo_real.h = self.workspace.screen.height/2 - 2*c.geo_real.b
                c.geo_real.w = W - (2*c.geo_real.b)
                c.real_configure_notify()

#
# Workspace
#
class Workspace:
    def __init__(self, name, vroot):
        self.name = name
        self.vroot = vroot
        self.screen = None
        self.__clients = {}
        self.__master = None
        self.__slaves = []
        self.__layouts = [LayoutVTall(self), LayoutHTall(self)]
        self.current_layout = 0
        self.focused_client = None
        self.__toggle_desktop = False

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

    def map(self, client):
        if client.never_tiled:
            self.__tile(client)
        client.map()

    def __tile(self, client):
        client.tile()
        if self.__master is not None:
            self.__slaves.insert(0,self.__master)

        self.__master = client
        self.update()

    def __untile(self, client):
        client.untile()
        if self.__master.id == client.id:
            self.__master = None
            if len(self.__slaves) == 0:
                return
            self.__master = self.__slaves.pop(0)
        else:
            self.__slaves.remove(client)

        self.update()

    def untile(self, client):
        if not client.tiled:
            return
        self.__untile(client)

    def tile(self, client):
        if client.tiled:
            return
        self.__tile(client)

    def update_focus(self, client):
        if self.focused_client is not None:
            self.focused_client.unfocus()
        self.focused_client = client
        self.focused_client.focus()

    def reparent(self, who):
        for c in self.__clients.itervalues():
            c.reparent(who)

    def set_passive(self):
        self.screen = None
        self.reparent(self.vroot)

    def set_active(self, screen):
        self.screen = screen
        self.reparent(self.screen.root)

    def next_layout(self):
        if self.screen == None:
            return

        self.current_layout = (self.current_layout+1)%len(self.__layouts)
        self.update()

    def toggle_desktop(self):
        if self.screen == None:
            return

        if not self.__toggle_desktop:
            con.core.UnmapSubwindows(self.screen.root)
            self.__toggle_desktop = True
        else:
            con.core.MapSubwindows(self.screen.root)
            self.__toggle_desktop = False


#
# Client
#
class Geometry:
    def __init__(self, x,y, w,h, b):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.b = b

class Client:
    def __init__(self, event, workspace):
        self.id = event.window
        self.parent = event.parent
        self.geo_real = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.geo_want = Geometry(event.x, event.y, event.width, event.height, event.border_width)
        self.border_color = Screen.passive_color
        self.workspace = workspace
        self.tiled = False
        self.never_tiled = True
        self.__min_w = 20
        self.__min_h = 20
        self.__setup()

    def __setup(self):
        mask  = EventMask.EnterWindow|EventMask.PropertyChange|EventMask.FocusChange
        con.core.ChangeWindowAttributes(self.id, CW.EventMask, [mask])

    def move(self, dx, dy):
        self.geo_real.x += dx
        self.geo_real.y += dy
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

        if self.geo_real.w < self.__min_w:
            self.geo_real.w = self.__min_w

        if self.geo_real.w == self.__min_w and dx < 0:
            dx = 0
            mx = 0

        if self.geo_real.h < self.__min_h:
            self.geo_real.h = self.__min_h

        if self.geo_real.h == self.__min_h and dy < 0:
            dy = 0
            my = 0

        if dx == 0 and dy == 0:
            return

        if mx != 0 or my != 0:
            self.move(mx, my)

        self.geo_real.w += dx
        self.geo_real.h += dy
        self.real_configure_notify()

    def reparent(self, who):
        self.parent = who
        con.core.ReparentWindow(self.id, self.parent, self.geo_real.x, self.geo_real.y)

    def focus(self):
        #con.core.SetInputFocus(InputFocus.PointerRoot, self.id, InputFocus._None)
        self.border_color = Screen.focused_color
        self.update_border_color()

    def unfocus(self):
        self.border_color = Screen.passive_color
        self.update_border_color()

    def update_border_color(self):
        con.core.ChangeWindowAttributes(self.id, CW.BorderPixel, [self.border_color])

    def map(self):
        con.core.MapWindow(self.id)

    def tile(self):
        if self.never_tiled:
            self.never_tiled = False
            self.tiled = True
        elif not self.tiled:
            self.tiled = True

    def untile(self):
        if self.tiled:
            self.tiled = False

    def destroy(self):
        pass

    def stack_above(self):
        con.core.ConfigureWindow(self.id, ConfigWindow.StackMode, [StackMode.Above])

    def real_configure_notify(self):
        mask = ConfigWindow.X|ConfigWindow.Y|ConfigWindow.Width|ConfigWindow.Height|ConfigWindow.BorderWidth
        pkt = pack('=xx2xIH2xiiIII', self.id, mask,
                   self.geo_real.x, self.geo_real.y,
                   self.geo_real.w, self.geo_real.h, self.geo_real.b)
        con.core.send_request(xcb.Request(pkt, 12, True, False), xcb.VoidCookie())

    def synthetic_configure_notify(self):
        event = pack("=B3xIIIHHHHHBx", 22, self.id, self.id, 0,
                     self.geo_want.x, self.geo_want.y,
                     self.geo_want.w, self.geo_want.h, self.geo_want.b, 0)
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
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is None:
        vanilla_configure_window_request(event)
    else:
        cl.configure(event)

def event_create_notify(event):
    if event.override_redirect == 0:
        print "new client %d" % event.window
        wk = current_workspace()
        wk.add_client(Client(event, wk))

def event_destroy_notify(event):
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is not None:
        print "destroy client %d" % event.window
        if(cl.tiled):
            wk.untile(cl)
        wk.del_client(cl)

def event_map_window(event):
    wk = current_workspace()
    cl = wk.get_client(event.window)
    if cl is not None:
        wk.map(cl)

def event_enter_notify(event):
    wk = current_workspace()
    cl = wk.get_client(event.event)
    if cl is not None:
        wk.update_focus(cl)

def event_reparent_notify(event):
    pass
    # wk = current_workspace()
    # cl = scr.get_client(event.window)
    # evt = pack("=B3xIIIHH3x",
    #            21, event.event, event.window, event.parent,
    #            cl.geo_real.x, cl.geo_real.y)
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

event_handlers = { CreateNotifyEvent:event_create_notify,
                   DestroyNotifyEvent:event_destroy_notify,
                   ConfigureRequestEvent:event_configure_window_request,
                   MapRequestEvent:event_map_window,
                   EnterNotifyEvent:event_enter_notify,
                   ReparentNotifyEvent:event_reparent_notify,
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
        print "key press:",event.detail, event.state
        self.__bindings[event.detail][event.state]()

    def release(self, event):
        print "key release:",event.detail, event.state

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

        dx = event.event_x - self.__x
        dy = event.event_y - self.__y

        self.__acting(self.__c, self.__up, self.__left, dx, dy)

        self.__x = event.event_x
        self.__y = event.event_y

    def press(self, event):
        print "button press:",event.__dict__
        if self.__acting is not None or event.child == 0:
            return

        self.__c = current_workspace().get_client(event.child)
        if self.__c is None:
            return

        self.__c.stack_above()

        self.__acting = self.__bindings[event.detail][event.state]
        self.__x = event.event_x
        self.__y = event.event_y

        if self.__x < self.__c.geo_real.x+(2*self.__c.geo_real.b+self.__c.geo_real.w)/2:
            self.__left = True
        else:
            self.__left = False

        if self.__y < self.__c.geo_real.y+(2*self.__c.geo_real.b+self.__c.geo_real.h)/2:
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
    #XXX: should be "focused" screen
    return _screens[0]

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

def get_next_workspace_from(wk1):
    n = 0
    for w in _workspaces:
        if w == wk1:
            break
        n += 1

    while True:
        n = (n+1)%len(_workspaces)
        wk2 = _workspaces[n]
        if wk2.screen == None:
            return wk2
        if w == wk1:
            return None

def get_workspace_at(wk1, stp):
    n = 0
    for w in _workspaces:
        if w == wk1:
            break
        n += 1

    while True:
        n = (n+stp)%len(_workspaces)
        wk2 = _workspaces[n]
        if wk2.screen == None:
            return wk2
        if w == wk1:
            return None

def next_workspace_from(wk1):
    return get_workspace_at(wk1, 1)

def prev_workspace_from(wk1):
    return get_workspace_at(wk1, -1)

def next_workspace():
    nwk = next_workspace_from(current_workspace())
    if nwk is not None:
        current_screen().set_workspace(nwk)

def prev_workspace():
    nwk = prev_workspace_from(current_workspace())
    if nwk is not None: 
        current_screen().set_workspace(nwk)

def spawn(*args):
    print "spawn",args
    os.spawnle(os.P_NOWAIT, args[0], *args)

#
# Bindings
#
class KeyMap:
    left           = 113
    right          = 114
    space          = 65
    t              = 28
    d              = 40
    s              = 39
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

workspaces = [ "1", "2", "3", "4" ]

keyboard_bindings = [ (KeyMap.mod_alt, KeyMap.space, next_layout),
                      (KeyMap.mod_alt, KeyMap.t,     tile_client),
                      (KeyMap.mod_alt, KeyMap.d,     toggle_show_desktop),
                      (KeyMap.mod_alt, KeyMap.right, next_workspace),
                      (KeyMap.mod_alt, KeyMap.left,  prev_workspace),
                      (KeyMap.mod_alt, KeyMap.s,     lambda:spawn("/usr/bin/xterm","-bg","lightgreen",{"DISPLAY":":1"})),
                      ]

mouse_bindings    = [ (KeyMap.mod_alt, 1, move_client),
                      (KeyMap.mod_alt, 3, resize_client),
                      ]


# XXX: KeyButMask.Mod2 is always set (xpyb/Xephyr bug ?)
def xhephyr_wtf(k, m):
    for n in range(len(k)):
        k[n] = (k[n][0]|KeyButMask.Mod2, k[n][1], k[n][2])
    for n in range(len(m)):
        m[n] = (m[n][0]|KeyButMask.Mod2, m[n][1], m[n][2])

xhephyr_wtf(keyboard_bindings, mouse_bindings)

#
# Main
#
# TODO:
#
# - create _NET_VIRTUAL_ROOTS list
# - manage xrandr
#
# BUGS:
#
# - firefox popups goes away when then mouse enters
# - Mod.ctrl is always set under "my" Xephyr/python-xcb
#
keyboard = Keyboard()
mouse = Mouse()
_screens = []
_workspaces = []

con = xcb.connect()
con.core.GrabServer()

setup = con.get_setup()

atoms = {}
for n in atom_names:
    atoms[n] = con.core.InternAtom(False, len(n), n)

for n in atoms:
    atoms[n] = atoms[n].reply().atom

if len(workspaces) < len(setup.roots):
    print "Not enough workspaces"
    con.disconnect()
    sys.exit(1)

dflt_scr = setup.roots[0]
for w in workspaces:
    vroot = con.generate_id()
    con.core.CreateWindow(dflt_scr.root_depth, vroot, dflt_scr.root,
                          -1, -1, 1, 1, 0, WindowClass.CopyFromParent,
                          dflt_scr.root_visual, 0, [])
    wk = Workspace(w, vroot)
    _workspaces.append(wk)

while con.poll_for_event():
    pass

w = 0
for s in setup.roots:
    try:
        con.core.ChangeWindowAttributesChecked(s.root, CW.EventMask, events).check()
    except BadAccess, e:
        print "A window manager is already running !"
        con.disconnect()
        sys.exit(1)

    scr = Screen(s, _workspaces)
    scr.setup()
    scr.set_workspace(_workspaces[w])
    _screens.append(scr)
    w += 1

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
