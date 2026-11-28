"""Right-click and ▾ menus drawn by Condense in its own theme.

Tk's popup menus look dated on Linux, and the app released their grab straight after opening them, so on Linux a click
elsewhere did not close them. PopupMenu takes the calls Condense makes on tk.Menu (add_command, add_separator,
add_checkbutton, add_cascade, tk_popup, grab_release) and draws a themed popup that closes on a click outside it, Esc,
or when the app loses the focus. ↑/↓, Return, → and ← work as in a menu. The menu bar stays the system's own.

On macOS Tk's popup menus are the system's own menus, which look and behave as Mac users expect: there PopupMenu
builds and shows a native menu instead.
"""
import tkinter as tk
from typing import Callable, Dict, List, Optional

from condense.gui.theme import THEME


class PopupMenu:
    PAD_X = 14
    HOVER = "#2b3245"  # a row under the mouse
    ROW_PAD_Y = 4

    def __init__(self, master, font=None, parent: Optional["PopupMenu"] = None):
        self.master = master
        self.font = font if font is not None else (getattr(master, "f", None) or {}).get("body")
        self.parent = parent
        self.items: List[Dict] = []
        self.win = None
        self.rows: List = []      # (item index, row frame) for the rows that can be chosen
        self.active: Optional[int] = None  # index into self.rows
        self.child: Optional["PopupMenu"] = None
        self._poll = None
        self._opened_at = 0.0

    # ----- the tk.Menu calls Condense uses -----
    def add_command(self, label: str = "", command: Optional[Callable] = None, state: str = "normal", accelerator: str = "", **_):
        self.items.append({"kind": "command", "label": label, "command": command, "state": str(state), "accel": accelerator})

    def add_separator(self, **_):
        self.items.append({"kind": "separator"})

    def add_checkbutton(self, label: str = "", variable=None, command: Optional[Callable] = None, **_):
        self.items.append({"kind": "check", "label": label, "variable": variable, "command": command, "state": "normal"})

    def add_cascade(self, label: str = "", menu: Optional["PopupMenu"] = None, **_):
        if menu is not None:
            menu.parent = self
        self.items.append({"kind": "cascade", "label": label, "menu": menu, "state": "normal"})

    def tk_popup(self, x: int, y: int, entry=None):
        if self.native():
            self.native_menu().tk_popup(int(x), int(y))  # macOS: the system's own menu
            return
        self.post(x, y)

    def native(self) -> bool:
        try:
            return str(self.master.tk.call("tk", "windowingsystem")) == "aqua"
        except Exception:
            return False

    def native_menu(self, master=None) -> tk.Menu:
        """The same entries as a Tk (on macOS: system) menu."""
        menu = tk.Menu(master if master is not None else self.master, tearoff=0)
        for it in self.items:
            if it["kind"] == "separator":
                menu.add_separator()
            elif it["kind"] == "check":
                menu.add_checkbutton(label=it["label"], variable=it.get("variable"), command=it.get("command"))
            elif it["kind"] == "cascade":
                if it.get("menu") is not None:
                    menu.add_cascade(label=it["label"], menu=it["menu"].native_menu(menu))
            else:
                menu.add_command(label=it["label"], command=it.get("command"), state=it.get("state", "normal"),
                                 accelerator=it.get("accel", ""))
        return menu

    def grab_release(self):
        pass  # the popup keeps its grab until it closes (releasing it at once is what left Tk's menus open)

    def labels(self) -> List[str]:
        return [it.get("label", "") for it in self.items if it["kind"] != "separator"]

    def invoke(self, label_or_index):
        """Choose an entry, as a click would (tests, keyboard)."""
        it = self._item(label_or_index)
        if it is None or it.get("state") == "disabled":
            return None
        self.unpost(all_levels=True)
        if it["kind"] == "check" and it.get("variable") is not None:
            it["variable"].set(not bool(it["variable"].get()))
        cmd = it.get("command")
        return cmd() if cmd else None

    def _item(self, key) -> Optional[Dict]:
        if isinstance(key, int):
            return self.items[key] if 0 <= key < len(self.items) else None
        return next((it for it in self.items if it.get("label") == key), None)

    # ----- showing it -----
    @property
    def is_open(self) -> bool:
        return self.win is not None

    def post(self, x: int, y: int):
        self.unpost()
        T = THEME
        win = tk.Toplevel(self.parent.win if self.parent is not None and self.parent.win is not None else self.master)
        self.win = win
        win.withdraw()
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        border = tk.Frame(win, bg=T["border"], padx=1, pady=1)
        border.pack(fill=tk.BOTH, expand=True)
        body = tk.Frame(border, bg=T["bg_panel"], padx=4, pady=4)
        body.pack(fill=tk.BOTH, expand=True)
        self.rows, self.active = [], None
        for i, it in enumerate(self.items):
            if it["kind"] == "separator":
                tk.Frame(body, bg=T["border"], height=1).pack(fill=tk.X, padx=6, pady=4)
                continue
            disabled = it.get("state") == "disabled"
            row = tk.Frame(body, bg=T["bg_panel"], cursor="" if disabled else "hand2")
            row.pack(fill=tk.X)
            mark = "✓" if it["kind"] == "check" and it.get("variable") is not None and bool(it["variable"].get()) else ""
            fg = T["fg_dim"] if disabled else T["fg_primary"]
            cells = [tk.Label(row, text=mark, width=2, bg=T["bg_panel"], fg=T["fg_primary"], font=self.font, anchor="w"),
                     tk.Label(row, text=it.get("label", ""), bg=T["bg_panel"], fg=fg, font=self.font, anchor="w",
                              padx=2, pady=self.ROW_PAD_Y)]
            right = "›" if it["kind"] == "cascade" else it.get("accel", "")
            cells.append(tk.Label(row, text=right, bg=T["bg_panel"], fg=T["fg_dim"], font=self.font, anchor="e", padx=self.PAD_X // 2))
            cells[0].pack(side=tk.LEFT, padx=(4, 0))
            cells[1].pack(side=tk.LEFT, fill=tk.X, expand=True)
            cells[2].pack(side=tk.RIGHT)
            if disabled:
                continue
            n = len(self.rows)
            self.rows.append((i, row, cells))
            for w in [row] + cells:
                w.bind("<Enter>", lambda e, n=n: self._highlight(n, open_cascade=True))
                w.bind("<ButtonRelease-1>", lambda e, i=i: self._choose(i))
        win.bind("<ButtonPress>", self._on_press, add="+")
        for seq, fn in (("<Escape>", lambda e: self._escape()), ("<Up>", lambda e: self._move(-1)), ("<Down>", lambda e: self._move(+1)),
                        ("<Return>", lambda e: self._choose_active()), ("<KP_Enter>", lambda e: self._choose_active()),
                        ("<Right>", lambda e: self._open_active_cascade()), ("<Left>", lambda e: self._escape(only_self=True))):
            win.bind(seq, lambda e, fn=fn: (fn(), "break")[-1])
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = max(0, min(int(x), sw - w - 2))
        y = int(y) if int(y) + h <= sh else max(0, int(y) - h)
        win.geometry(f"+{x}+{y}")
        win.deiconify()
        win.lift()
        if self.parent is None:
            try:  # where the keys went before: they go back there when the menu closes
                self._prev_focus = self.master.focus_get()
            except Exception:
                self._prev_focus = None
            self._grab()
            import time
            self._opened_at = time.monotonic()
            self._poll = win.after(300, self._check_focus)
        try:
            win.focus_force()
        except Exception:
            pass

    def _grab(self):
        win = self.win
        try:
            if str(win.tk.call("tk", "windowingsystem")) == "x11":
                win.grab_set_global()  # as Tk's own combobox lists do on X11: a click anywhere comes here first
            else:
                win.grab_set()
        except Exception:
            try:
                win.grab_set()
            except Exception:
                pass

    def unpost(self, all_levels: bool = False):
        if self.child is not None:
            self.child.unpost()
            self.child = None
        win, self.win = self.win, None
        if win is not None:
            if self._poll is not None:
                try:
                    win.after_cancel(self._poll)
                except Exception:
                    pass
                self._poll = None
            try:
                win.grab_release()
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass
            prev = self.__dict__.get("_prev_focus")
            self._prev_focus = None
            if self.parent is None and prev is not None:
                try:  # without this the keys went nowhere after a menu (on Linux): no ↑/↓ or Return in the transcript
                    if prev.winfo_exists():
                        prev.focus_force()
                except Exception:
                    pass
        if all_levels and self.parent is not None:
            self.parent.unpost(all_levels=True)

    # ----- events -----
    def _inside(self, x_root: int, y_root: int) -> bool:
        m: Optional[PopupMenu] = self
        while m is not None and m.win is not None:
            wx, wy = m.win.winfo_rootx(), m.win.winfo_rooty()
            if wx <= x_root < wx + m.win.winfo_width() and wy <= y_root < wy + m.win.winfo_height():
                return True
            m = m.child
        return False

    def _on_press(self, event):
        root = self
        while root.parent is not None:
            root = root.parent
        if not root._inside(event.x_root, event.y_root):
            root.unpost()

    def _check_focus(self):
        """Close when another application gets the focus (the grab only covers this one)."""
        self._poll = None
        if self.win is None:
            return
        try:
            focused = self.win.focus_displayof()
        except Exception:
            focused = None
        if focused is None:
            self.unpost()
            return
        self._poll = self.win.after(300, self._check_focus)

    def _highlight(self, n: Optional[int], open_cascade: bool = False):
        T = THEME
        for k, (_, row, cells) in enumerate(self.rows):
            bg = self.HOVER if k == n else T["bg_panel"]
            for w in [row] + cells:
                w.configure(bg=bg)
        self.active = n
        if n is None:
            return
        it = self.items[self.rows[n][0]]
        if self.child is not None and (it["kind"] != "cascade" or it.get("menu") is not self.child):
            self.child.unpost()
            self.child = None
        if open_cascade and it["kind"] == "cascade":
            self._open_cascade(n)

    def _open_cascade(self, n: int):
        it = self.items[self.rows[n][0]]
        sub = it.get("menu")
        if sub is None or (self.child is sub and sub.is_open):
            return
        row = self.rows[n][1]
        sub.parent = self
        self.child = sub
        sub.post(row.winfo_rootx() + row.winfo_width() + 4, row.winfo_rooty() - 5)

    def _move(self, d: int):
        if not self.rows:
            return
        n = 0 if self.active is None and d > 0 else (len(self.rows) - 1 if self.active is None else (self.active + d) % len(self.rows))
        self._highlight(n)

    def _choose(self, i: int):
        it = self.items[i]
        if it["kind"] == "cascade":
            self._open_cascade(next(k for k, r in enumerate(self.rows) if r[0] == i))
            return
        self.invoke(i)

    def _choose_active(self):
        if self.active is not None:
            self._choose(self.rows[self.active][0])

    def _open_active_cascade(self):
        if self.active is not None and self.items[self.rows[self.active][0]]["kind"] == "cascade":
            self._open_cascade(self.active)
            if self.child is not None:
                self.child._move(+1)
                try:
                    self.child.win.focus_force()
                except Exception:
                    pass

    def _escape(self, only_self: bool = False):
        if only_self and self.parent is None:
            return
        parent = self.parent
        self.unpost()
        if parent is not None:
            parent.child = None
            try:
                parent.win.focus_force()
            except Exception:
                pass
