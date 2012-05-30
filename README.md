FPWM
====

A fucking python tiling window manager.

What is it ?
------------

Fpwm is a tiling window manager written in python. One can configure it and access its internals using python. It's a little bit what xmonad offers, without the purely functional approach of Haskell.

What fpwm offers ?
------------------

* tiling, floating clients
* multi-screens (xrandr)
* multi-workspaces (shared between screens)
* multi-layouts (per workspace)
* keyboard/mouse bindings
* cycle/resize layouts
* move/resize client
* next/prev client
* up/down client into a layout
* next/prev workspaces
* goto/sendto workspace
* status info and available space (ie. for dzen)
* toggle fullscreen/show desktop
* spawn external programs
* ignored clients
* quake console

Why another tiling window manager ?
-----------------------------------

* wanted to know how it works
* used to xmonad ... but Haskell
* easy to read/understand
* simple/stupid, minimalistic and highly configurable
* good for imperative minds and not functional ones ... even if i should admit xmonad really rocks !

Limitations ?
-------------

* you will cry blood if you're a good python programmer
* there are bugs, they will be fixed
* check TODO and BUGS files

How to use it ?
---------------

* ensure to have xcb libs (>= 1.8) and python xcb bindings (python-xpyb under Debian)
* clone it `git clone git@github.com:sduverger/fpwm.git`
* ninja it `mv fpwm .fpwm`
* edit `config.py`
* run it `~/.fpwm/fpwm.py | dzen2 -w <screen_width> -x <screen_offset>`
