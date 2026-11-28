"""Layout widgets: FlowFrame (wrapping toolbar) and ScrollFrame."""
import sys
import tkinter as tk
from tkinter import ttk
from typing import List

IS_MAC = sys.platform == "darwin"
MOD = "Command" if IS_MAC else "Control"
# Shortcuts used while typing in the segment box (speaker numbers): ⌃ on the Mac, where it is free next to ⌘;
# Alt elsewhere, because Ctrl+1–3 switch tabs there.
EDIT_MOD = "Control" if IS_MAC else "Alt"
EDIT_MOD_LABEL = "⌃" if IS_MAC else "Alt+"

# Bits of a key event's state that make a key a shortcut (⌘C, Ctrl+1 …) rather than a plain key. Each platform
# packs different things into those bits:
#   Mac:     Control 0x4, ⌘ (Mod1) 0x8, ⌥ (Mod2) 0x10. Tk also sets Mod3 (keypad) and Mod4 (fn) on the arrow,
#            forward-delete, Home/End and keypad keys, so those two must not count, or ↑/↓ stop working.
#   Windows: Control 0x4, Alt 0x20000. Mod1 (0x8) there is Num Lock.
#   Linux:   Control 0x4, Alt (Mod1) 0x8, Super (Mod4) 0x40. Num Lock is Mod2 (0x10).
if IS_MAC:
    SHORTCUT_MODS = 0x4 | 0x8 | 0x10
elif sys.platform == "win32":
    SHORTCUT_MODS = 0x4 | 0x20000
else:
    SHORTCUT_MODS = 0x4 | 0x8 | 0x40


def is_shortcut(event) -> bool:
    """True when Control, ⌘, ⌥ or Alt is held with the key (Shift, Caps Lock, Num Lock and the Mac's fn do not count)."""
    try:
        return bool(int(getattr(event, "state", 0) or 0) & SHORTCUT_MODS)
    except (TypeError, ValueError):
        return False


def screen_rects(root) -> List[tuple]:
    """(x, y, width, height) of every display, in the coordinates Tk uses for window positions. Tk itself only
    knows the main display, which is why windows used to stop growing at its size on a larger external monitor."""
    rects: List[tuple] = []
    try:
        if IS_MAC:
            import ctypes
            import ctypes.util

            class _Point(ctypes.Structure):
                _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

            class _Size(ctypes.Structure):
                _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

            class _Rect(ctypes.Structure):
                _fields_ = [("origin", _Point), ("size", _Size)]

            path = (ctypes.util.find_library("CoreGraphics")
                    or "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
            cg = ctypes.cdll.LoadLibrary(path)
            cg.CGGetActiveDisplayList.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
                                                  ctypes.POINTER(ctypes.c_uint32)]
            cg.CGGetActiveDisplayList.restype = ctypes.c_int32
            cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
            cg.CGDisplayBounds.restype = _Rect
            ids, n = (ctypes.c_uint32 * 16)(), ctypes.c_uint32(0)
            if cg.CGGetActiveDisplayList(16, ids, ctypes.byref(n)) == 0:
                for i in range(min(n.value, 16)):
                    r = cg.CGDisplayBounds(ids[i])  # global points, main display at 0,0, y downwards, like Tk
                    rects.append((int(r.origin.x), int(r.origin.y), int(r.size.width), int(r.size.height)))
        elif sys.platform == "win32":
            import ctypes
            m = ctypes.windll.user32.GetSystemMetrics  # the virtual screen spanning every monitor
            x, y, w, h = m(76), m(77), m(78), m(79)
            if w > 0 and h > 0:
                rects.append((x, y, w, h))
        else:
            w, h = root.winfo_vrootwidth(), root.winfo_vrootheight()  # X11: the root window covers every monitor
            if w > 0 and h > 0:
                rects.append((0, 0, w, h))
    except Exception:
        rects = []
    rects = [r for r in rects if r[2] > 0 and r[3] > 0]
    return rects or [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]


def geometry_fits(w: int, h: int, x: int, y: int, rects: List[tuple], min_w: int = 900, min_h: int = 600) -> bool:
    """A saved window can be restored when it is big enough, no bigger than the screens put together, and its title
    bar (the strip you drag it by) lies on a display that is still connected."""
    if not rects or w < min_w or h < min_h:
        return False
    left = min(r[0] for r in rects)
    top = min(r[1] for r in rects)
    right = max(r[0] + r[2] for r in rects)
    bottom = max(r[1] + r[3] for r in rects)
    if w > right - left or h > bottom - top:
        return False
    grab_x, grab_y = x + min(w // 2, 200), y + 10
    return any(rx <= grab_x < rx + rw and ry <= grab_y < ry + rh for rx, ry, rw, rh in rects)


def kbd(text: str) -> str:
    """Shortcut labels are written with Mac symbols; on Linux and Windows they read Ctrl+S, Ctrl+Shift+O, Ctrl+Enter."""
    if IS_MAC:
        return text
    for a, b in (("⌘-click", "Ctrl+click"), ("⇧-click", "Shift+click"), ("⇧⌘", "Ctrl+Shift+"), ("⌘⇧", "Ctrl+Shift+"),
                 ("⌘↩", "Ctrl+Enter"), ("⌘", "Ctrl+"), ("⇧", "Shift+"), ("⌃", "Ctrl+"), ("↩", "Enter")):
        text = text.replace(a, b)
    return text


class FlowFrame(tk.Frame):
    """Lays its children out left-to-right and wraps them onto new rows when space runs out — or, with one_line, keeps
    one row: the buttons that don't fit go into a "⋯" menu at its end (in their order), instead of onto a second row
    that makes the toolbars look chopped. Separators (thin lines between groups) are dropped where a row ends."""

    def __init__(self, master, padx: int = 6, pady: int = 4, one_line: bool = False, extra_menu=None, align: str = "left",
                 more_before_last: bool = False, **kw):
        """extra_menu (one_line): a function giving a PopupMenu whose entries the ⋯ menu always ends with; then ⋯ is
        always there — the row's own menu and, when space runs out, the buttons that did not fit."""
        super().__init__(master, **kw)
        self.extra_menu = extra_menu
        self.align = align  # (one_line) "right": the row ends at the right edge
        self.more_before_last = more_before_last  # (one_line) ⋯ before the last button (the main action stays last)
        self._items: List = []
        self._padx, self._pady = padx, pady
        self._last_width = None
        self.one_line = one_line
        self._more = None
        self.hidden: List = []  # (one_line) the buttons in the ⋯ menu now
        self.bind("<Configure>", self._on_configure)

    def add(self, widget):
        self._items.append(widget)
        self.after_idle(self.relayout)
        return widget

    def remove(self, widget):
        """Take one child out (and destroy it); the rest close up."""
        if widget in self._items:
            self._items.remove(widget)
        if widget in self.hidden:
            self.hidden.remove(widget)
        widget.destroy()
        self.after_idle(self.relayout)

    def clear(self):
        """Remove the children but keep the current height until the new ones are laid out: shrinking to nothing and
        growing back would make everything below jump on each refresh (e.g. the speaker chips on every ↑/↓)."""
        for w in self._items:
            w.destroy()
        self._items = []
        self.after_idle(self.relayout)

    def _on_configure(self, event):
        if event.width != self._last_width:
            self._last_width = event.width
            self.relayout()

    @staticmethod
    def _is_separator(w) -> bool:
        return bool(getattr(w, "condense_separator", False))

    @staticmethod
    def _can_hide(w) -> bool:
        """Buttons (and dropdowns) can go into the ⋯ menu; fields, switches and labels stay on the row."""
        return ((isinstance(w, ttk.Button) or getattr(w, "condense_invoke", None) is not None)
                and not getattr(w, "condense_keep", False))

    def relayout(self):
        if self.one_line:
            return self._relayout_one_line()
        width = self.winfo_width()
        if width <= 1:
            width = 10_000
        x = y = row_h = 0
        for w in self._items:
            ww, wh = w.winfo_reqwidth(), w.winfo_reqheight()
            if x > 0 and x + ww > width:
                x, y, row_h = 0, y + row_h + self._pady, 0
            w.place(in_=self, x=x, y=y)
            x += ww + self._padx
            row_h = max(row_h, wh)
        total_h = max(1, y + row_h)
        if int(self.cget("height")) != total_h:
            self.configure(height=total_h)

    def _more_button(self):
        if self._more is None:
            from condense.gui import rounded
            self._more = ttk.Button(self, text="⋯", style=rounded.style_for(self, "Tool"), command=self._open_more, takefocus=0)
            self._more.condense_keep = True
        return self._more

    def _open_more(self):
        from condense.gui.popup import PopupMenu
        menu = PopupMenu(self.winfo_toplevel())
        btn = self._more
        extra = self.extra_menu() if self.extra_menu else None
        for w in self.hidden:
            label = str(w.cget("text")).replace(" ▾", "")
            sub = getattr(w, "menu", None)
            if sub is not None:  # a dropdown: its own menu, opened where ⋯ is
                menu.add_command(label=label + " …", command=lambda m=sub: m.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height()))
            elif getattr(w, "condense_invoke", None) is not None:  # a chip (a label that acts as a button)
                menu.add_command(label=label, command=w.condense_invoke)
            else:
                menu.add_command(label=label, command=w.invoke, state="disabled" if "disabled" in str(w.cget("state")) else "normal")
        if extra is not None:
            if self.hidden and extra.items:
                menu.add_separator()
            menu.items.extend(extra.items)
        menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())
        return menu

    def _relayout_one_line(self):
        width = self.winfo_width()
        if width <= 1:
            width = 10_000
        items = list(self._items)
        sizes = [(w.winfo_reqwidth(), w.winfo_reqheight()) for w in items]
        needed = sum(ww for ww, _ in sizes) + self._padx * max(0, len(items) - 1)
        hide = set()
        if self.extra_menu is not None:
            needed += self._more_button().winfo_reqwidth() + self._padx
        if needed > width:
            more_w = self._more_button().winfo_reqwidth() + self._padx
            budget = width - more_w
            used = 0
            stop = False
            for i, (w, (ww, _wh)) in enumerate(zip(items, sizes)):  # keep from the left while it fits; hideable later ones go
                if not stop and used + ww <= budget:
                    used += ww + self._padx
                    continue
                stop = True
                if self._can_hide(w) or self._is_separator(w):
                    hide.add(i)
                else:  # a field or switch can't go into a menu: it stays, a button before it goes instead
                    used += ww + self._padx
                    for j in range(i - 1, -1, -1):
                        if j not in hide and (self._can_hide(items[j]) or self._is_separator(items[j])):
                            hide.add(j)
                            used -= sizes[j][0] + self._padx
                            if used <= budget:
                                break
        x = row_h = 0
        shown = [i for i in range(len(items)) if i not in hide]
        while shown and self._is_separator(items[shown[-1]]):  # no separator at the end of the row
            hide.add(shown.pop())
        self.hidden = [items[i] for i in sorted(hide) if not self._is_separator(items[i])]
        order = []
        for i, w in enumerate(items):
            if i in hide:
                w.place_forget()
                continue
            order.append(w)
        if self.hidden or self.extra_menu is not None:
            more = self._more_button()
            if self.more_before_last and order:
                order.insert(len(order) - 1, more)
            else:
                order.append(more)
        elif self._more is not None:
            self._more.place_forget()
        places = []
        for w in order:
            places.append((w, x))
            x += w.winfo_reqwidth() + self._padx
            row_h = max(row_h, w.winfo_reqheight())
        shift = max(0, width - (x - self._padx)) if self.align == "right" and width < 10_000 else 0
        for w, wx in places:
            w.place(in_=self, x=wx + shift, y=0)
        total_h = max(1, row_h)
        if int(self.cget("height")) != total_h:
            self.configure(height=total_h)

class ScrollFrame(tk.Frame):
    """Vertically scrollable container; put content into .inner."""

    def __init__(self, master, bg: str, **kw):
        super().__init__(master, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))

    def contains(self, widget) -> bool:
        path = str(widget)
        return path.startswith(str(self.canvas)) and "popdown" not in path

    def scroll(self, units: int) -> None:
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(units, "units")


class Tooltip:
    """A short text shown when the mouse rests on a widget (text may be a callable, asked each time)."""
    DELAY_MS = 550

    def __init__(self, widget, text, bg: str = "#2a3040", fg: str = "#e8eaef", font=None):
        self.widget, self.text, self.bg, self.fg, self.font = widget, text, bg, fg, font
        self.win = None
        self._job = None
        self._shown = None
        widget.bind("<Enter>", self._schedule, add="+")
        if callable(text):  # what it says depends on where the mouse is (a row of a list): follow it
            widget.bind("<Motion>", self._moved, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._job = self.widget.after(self.DELAY_MS, self._show)

    def _moved(self, _event=None):
        if self.win is not None:
            try:
                now = self.text()
            except Exception:  # noqa: BLE001
                now = None
            if now != self._shown:
                self._hide()
                self._schedule()
        elif self._job is None:
            self._schedule()

    def _cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self):
        self._job = None
        text = self.text() if callable(self.text) else self.text
        if not text or self.win is not None:
            return
        try:
            if callable(self.text):  # beside the mouse (the widget may be a whole list)
                x, y = self.widget.winfo_pointerx() + 14, self.widget.winfo_pointery() + 18
            else:
                x = self.widget.winfo_rootx() + 12
                y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            win = tk.Toplevel(self.widget)
            win.condense_free = True  # (not tied to a window: Condense makes other new windows transient)
            win.wm_overrideredirect(True)
            try:  # macOS: a help window, which never becomes the active window (it took the keys from the app)
                if str(win.tk.call("tk", "windowingsystem")) == "aqua":
                    win.tk.call("::tk::unsupported::MacWindowStyle", "style", win._w, "help", "noActivates")
            except tk.TclError:
                pass
            win.configure(bg=self.bg)
            tk.Label(win, text=text, bg=self.bg, fg=self.fg, font=self.font, justify=tk.LEFT, padx=8, pady=4,
                     wraplength=420).pack()
            win.wm_geometry(f"+{x}+{y}")
            self.win = win
            self._shown = text
        except tk.TclError:
            self.win = None

    def _hide(self, _event=None):
        self._cancel()
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
