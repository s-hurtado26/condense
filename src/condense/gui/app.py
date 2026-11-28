"""The main window, assembled from the GUI mixins."""
from condense import __version__, updates
from condense.gui._common import *  # noqa: F401,F403
from condense.gui import rounded
from condense.gui.editor import EditorMixin
from condense.gui.history import HistoryMixin
from condense.gui.navigation import NavigationMixin
from condense.gui.review_marks import ReviewMarksMixin
from condense.gui.player import PlayerMixin
from condense.gui.queue_panel import QueueMixin
from condense.gui.rerun import RerunMixin
from condense.gui.settings_tab import SettingsTabMixin
from condense.gui.updates_ui import UpdatesMixin
from condense.gui.gpu_check import GpuCheckMixin
from condense.gui.file_dialogs import FileDialogsMixin
from condense.gui.cutting import CuttingMixin
from condense.gui.trim_dialog import TrimDialogMixin
from condense.gui.find import FindMixin
from condense.gui.project import ProjectMixin
from condense.gui.episodes import EpisodesMixin
from condense.gui.project_panel import ProjectPanelMixin
from condense.gui.coding_tab import CodingMixin
from condense.gui.coding_timeline import CodingTimelineMixin
from condense.gui.video import VideoMixin
from condense.gui.subtitles_ui import SubtitlesMixin
from condense.gui.maxqda_copy import MaxqdaCopyMixin
from condense.gui.comments import CommentsMixin
from condense.gui.renaming_ui import RenamingMixin
from condense.gui.storage_ui import StorageMixin
from condense.gui.gaps_ui import GapsMixin
from condense.gui.overview_ui import OverviewMixin
from condense.gui.memory_ui import MemoryMixin


class CondenseApp(QueueMixin, SettingsTabMixin, EditorMixin, NavigationMixin, HistoryMixin, ReviewMarksMixin, PlayerMixin, RerunMixin, VideoMixin, UpdatesMixin, GpuCheckMixin, FileDialogsMixin, CuttingMixin, TrimDialogMixin, FindMixin, ProjectMixin, EpisodesMixin, ProjectPanelMixin, CodingMixin, CodingTimelineMixin, CommentsMixin, RenamingMixin, SubtitlesMixin, MaxqdaCopyMixin, StorageMixin, GapsMixin, OverviewMixin, MemoryMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Condense — Video, Audio & Transcripts")
        self.configure(bg=THEME["bg_root"])
        self.settings = SettingsStore.load()

        self.f: Dict[str, "tkfont.Font"] = {
            name: tkfont.Font(self, family=fam, size=size, weight=weight, slant=FONT_SLANTS.get(name, "roman"))
            for name, (fam, size, weight) in FONT_SPECS.items()
        }
        self.ui_scale = 1.0
        self._flows: List[FlowFrame] = []

        self._set_initial_geometry()
        self.minsize(900, 600)
        # Tk's default maximum is the size of the main display: on a larger external monitor the window stopped
        # growing there, and full screen left a dark band that came back after switching apps.
        self.maxsize(16384, 16384)

        self.jobs: List[Dict] = []
        self.job_counter = 0
        self.msg_queue: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: Optional[PipelineWorker] = None
        self._persist: Dict[str, object] = {}
        self._combo_values: Dict[str, List[str]] = {}

        self.active_doc: Optional[TranscriptDocument] = None
        self._undo_stacks: Dict[str, Tuple[List, List]] = {}  # per transcript path: (undo, redo) of (label, zlib-packed file text)
        self.word_spans: List[Dict] = []
        self.line_spans: Dict[int, List[int]] = {}
        self.low_conf: List[int] = []
        self.current_span: Optional[int] = None
        self._play_proc: Optional[subprocess.Popen] = None

        self.gpu_info: Dict = {"gpu_name": "Detecting hardware…"}
        self.deps: Dict[str, Optional[str]] = {}

        self._configure_styles()
        self._init_updates()
        self._build_menubar()
        self._build_header()
        self._build_footer()  # before the main area, so it is never pushed off-screen
        self._build_main_layout()
        self._keep_new_windows_in_front()
        self._apply_settings()
        self._set_zoom(float(self.settings.get("ui_scale", 1.0)), save=False)
        self._set_transcript_size(float(self.settings.get("transcript_scale", 1.0)), save=False)
        self._load_queue()
        self.after(400, self._reopen_after_restart)  # after Restart (Memory window): the transcript, where you were

        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_class("TCombobox", "<MouseWheel>", self._on_mousewheel)  # scrolling must not change values
        if not IS_MAC:  # X11: the wheel arrives as buttons 4 (up) and 5 (down)
            for button, units in (("<Button-4>", -3), ("<Button-5>", 3)):
                self.bind_all(button, lambda e, u=units: self._on_mousewheel(e, u), add="+")
                self.bind_class("TCombobox", button, lambda e, u=units: self._on_mousewheel(e, u))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self.createcommand("tk::mac::Quit", self._on_close)
            self.createcommand("tk::mac::ShowPreferences", lambda: self.notebook.select(self.tab_settings))
        except Exception:
            pass

        threading.Thread(target=self._probe_system, daemon=True).start()
        self.after(100, self._poll_queue)

    # ================================================================== styles, fonts, zoom
    def _set_initial_geometry(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        saved = str(self.settings.get("geometry") or "")
        m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", saved)
        if m:
            w, h, x, y = (int(v) for v in m.groups())
            if geometry_fits(w, h, x, y, screen_rects(self)):  # also on an external monitor that is still connected
                self.geometry(saved)
                return
        w = max(900, min(1360, int(sw * 0.85)))
        h = max(600, min(860, int(sh * 0.82)))
        w, h = min(w, sw), min(h, sh - 60)
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(25, (sh - h) // 2 - 20)}")

    def _configure_styles(self):
        T, f = THEME, self.f
        style = ttk.Style(self)
        style.theme_use("clam")
        self.style = style
        # clam draws light outlines and bevels by default: the same dark colours everywhere instead
        style.configure(".", background=T["bg_root"], foreground=T["fg_primary"], font=f["body"], bordercolor=T["border"],
                        lightcolor=T["bg_panel"], darkcolor=T["bg_panel"], focuscolor=T["bg_soft"], troughcolor=T["bg_panel"],
                        selectbackground=T["bg_selected"], selectforeground="#ffffff", insertcolor=T["fg_primary"])
        style.configure("TFrame", background=T["bg_panel"])
        style.configure("TLabel", background=T["bg_panel"], foreground=T["fg_primary"], font=f["body"])

        # red is for the one main action of a place (Run Pending Tasks, + Videos, Save & next, a dialog's own button)
        style.configure("Primary.TButton", background=T["accent"], foreground="#ffffff", borderwidth=0, font=f["body_bold"], padding=(12, 5),
                        bordercolor=T["accent"], lightcolor=T["accent"], darkcolor=T["accent"], focuscolor=T["accent"])
        style.map("Primary.TButton", background=[("active", T["accent_hover"]), ("disabled", T["bg_card"])], foreground=[("disabled", T["fg_dim"])])
        # everything else: quiet buttons, a soft fill without an outline
        soft = dict(background=T["bg_soft"], borderwidth=0, relief="flat", bordercolor=T["bg_soft"], lightcolor=T["bg_soft"],
                    darkcolor=T["bg_soft"], focuscolor=T["bg_soft"])
        style.configure("Tool.TButton", foreground=T["fg_primary"], font=f["small_bold"], padding=(8, 3), width=-3, **soft)
        style.map("Tool.TButton", background=[("active", T["bg_soft_hover"])], foreground=[("disabled", T["fg_dim"])])
        style.configure("Play.TButton", foreground=T["accent"], font=f["body_bold"], padding=(10, 3), width=-2, **soft)  # ▶ / ❚❚
        style.map("Play.TButton", background=[("active", T["bg_soft_hover"])])
        # a switch (Code | Edit …): its parts side by side, the chosen one lighter
        style.configure("Seg.TButton", foreground=T["fg_secondary"], font=f["small_bold"], padding=(12, 3), width=-3, **soft)
        style.map("Seg.TButton", background=[("active", T["bg_soft_hover"])], foreground=[("active", T["fg_primary"])])
        sel = dict(soft, background=T["bg_selected"], bordercolor=T["bg_selected"], lightcolor=T["bg_selected"],
                   darkcolor=T["bg_selected"], focuscolor=T["bg_selected"])
        style.configure("SegOn.TButton", foreground="#ffffff", font=f["small_bold"], padding=(12, 3), width=-3, **sel)
        style.map("SegOn.TButton", background=[("active", T["bg_selected"])])
        # the segment's ✓: grey, green once it is checked
        style.configure("Check.TButton", foreground=T["fg_dim"], font=f["body_bold"], padding=(8, 2), width=-2, **soft)
        style.map("Check.TButton", background=[("active", T["bg_soft_hover"])], foreground=[("active", T["ok"])])
        style.configure("CheckOn.TButton", foreground=T["ok"], font=f["body_bold"], padding=(8, 2), width=-2, **soft)
        style.map("CheckOn.TButton", background=[("active", T["bg_soft_hover"])])
        # rounded corners for all of these (image elements); where Tk can't make the images they stay square
        self._round_images = rounded.install(style, self, T)
        self._scale_images = rounded.install_scale(style, self, T)  # sliders: a thin line, a small round knob
        style.configure("Horizontal.TScale", background=T["bg_card"])  # (the player row's colour, behind the knob)

        # tabs: text, and a thin red line under the open one (an image element: clam can't draw only one edge)
        style.configure("TNotebook", background=T["bg_root"], borderwidth=0, tabmargins=(0, 0, 0, 2), bordercolor=T["bg_root"],
                        lightcolor=T["bg_root"], darkcolor=T["bg_root"])
        self._tab_images = self._make_tab_images()
        if self._tab_images:
            try:
                off, hover, on = self._tab_images
                style.element_create("Clean.tab", "image", off, ("selected", on), ("active", hover), border=(2, 2, 2, 3), sticky="nsew")
                style.layout("TNotebook.Tab", [("Clean.tab", {"sticky": "nswe", "children": [
                    ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [("Notebook.label", {"side": "top", "sticky": ""})]})]})])
            except tk.TclError:
                pass
        style.configure("TNotebook.Tab", background=T["bg_root"], foreground=T["fg_secondary"], padding=(14, 5, 14, 6), font=f["small_bold"], borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", T["bg_root"])], foreground=[("selected", T["fg_primary"]), ("active", T["fg_primary"])])

        style.configure("TCombobox", fieldbackground=T["bg_input"], background=T["bg_card"], foreground=T["fg_primary"], arrowcolor=T["fg_secondary"],
                        bordercolor=T["border"], lightcolor=T["bg_input"], darkcolor=T["bg_input"], padding=(4, 1))
        style.map("TCombobox", fieldbackground=[("readonly", T["bg_input"])], foreground=[("readonly", T["fg_primary"])],
                  selectbackground=[("readonly", T["bg_input"])], selectforeground=[("readonly", T["fg_primary"])])
        self.option_add("*TCombobox*Listbox.background", T["bg_card"])
        self.option_add("*TCombobox*Listbox.foreground", T["fg_primary"])
        self.option_add("*TCombobox*Listbox.selectBackground", T["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.font", f["body"])

        style.configure("Queue.Treeview", background=T["bg_input"], foreground=T["fg_primary"], fieldbackground=T["bg_input"], borderwidth=0, font=f["body"],
                        bordercolor=T["bg_input"], lightcolor=T["bg_input"], darkcolor=T["bg_input"])  # no frame around a list
        # list headings: light, small grey words on the list's own colour — not a bar
        style.configure("Queue.Treeview.Heading", background=T["bg_input"], foreground=T["fg_dim"], font=f["small"], relief="flat", padding=(4, 3),
                        bordercolor=T["bg_input"], lightcolor=T["bg_input"], darkcolor=T["bg_input"])
        style.map("Queue.Treeview.Heading", background=[("active", T["bg_card"])], foreground=[("active", T["fg_secondary"])])
        style.map("Queue.Treeview", background=[("selected", "#2b3348")], foreground=[("selected", "#ffffff")])

        # a 2 px line under the status bar: invisible while nothing runs (its trough is the footer's colour)
        style.configure("Horizontal.TProgressbar", troughcolor=T["bg_panel"], background=T["accent"], thickness=2, borderwidth=0,
                        bordercolor=T["bg_panel"], lightcolor=T["accent"], darkcolor=T["accent"])
        # thin scrollbars without arrows: a soft thumb in a trough the colour of the panel
        for orient, sticky in (("Vertical", "ns"), ("Horizontal", "ew")):
            style.configure(f"{orient}.TScrollbar", background=T["bg_soft"], troughcolor=T["bg_panel"], arrowcolor=T["fg_dim"],
                            bordercolor=T["bg_panel"], lightcolor=T["bg_soft"], darkcolor=T["bg_soft"], gripcount=0, arrowsize=9,
                            borderwidth=0, relief="flat")
            style.map(f"{orient}.TScrollbar", background=[("active", T["bg_soft_hover"]), ("pressed", T["bg_selected"])])
            try:
                style.layout(f"{orient}.TScrollbar", [(f"{orient}.Scrollbar.trough", {"sticky": sticky, "children": [
                    (f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            except tk.TclError:
                pass

    def _make_tab_images(self):
        """(normal, hover, open) images for a tab: the tab's colour, with a 2 px line at the bottom when open."""
        T = THEME
        try:
            def img(line):
                im = tk.PhotoImage(master=self, width=12, height=12)
                im.put(T["bg_root"], to=(0, 0, 12, 12))
                if line:
                    im.put(line, to=(0, 10, 12, 12))
                return im
            return img(None), img(T["border"]), img(T["accent"])
        except Exception:
            return None

    def _set_zoom(self, scale: float, save: bool = True):
        self.ui_scale = min(1.8, max(0.7, round(scale, 2)))
        for name, (_fam, base, _w) in FONT_SPECS.items():
            extra = self.transcript_scale if name == "transcript" else 1.0
            self.f[name].configure(size=max(7, int(round(base * self.ui_scale * extra))))
        self.style.configure("Queue.Treeview", rowheight=int(self.f["body"].metrics("linespace") * 1.45) + 4)
        for flow in self._flows:
            self.after_idle(flow.relayout)
        if save:
            self.settings["ui_scale"] = self.ui_scale
            SettingsStore.save(self.settings)

    def _keep_new_windows_in_front(self):
        """Every window Condense opens comes to the front with the keyboard focus, above the window it was opened from
        (Speakers from the Project overview used to appear behind it on some desktops)."""
        self._front = {"last": self, "seen": set()}

        def remember(event):
            try:
                top = event.widget.winfo_toplevel()
            except Exception:
                return
            if top is not None and top.winfo_class() in ("Toplevel", "Tk"):
                self._front["last"] = top

        def raise_new(event):
            w = event.widget
            if not isinstance(w, tk.Toplevel) or str(w) in self._front["seen"]:
                return
            self._front["seen"].add(str(w))
            opener = self._front.get("last")
            try:
                # stays above the window it was opened from — except windows of their own (the video): on macOS a
                # transient window can't go to another screen, it disappears when dragged there
                if opener is not None and opener is not w and opener.winfo_exists() and not getattr(w, "condense_free", False):
                    w.transient(opener)
            except Exception:
                pass

            def front():
                try:
                    if w.winfo_exists():
                        w.lift()
                        w.focus_force()
                except Exception:
                    pass
            self.after_idle(front)
            self.after(120, front)  # some window managers place the window only after mapping it

        self.bind_all("<FocusIn>", remember, add="+")
        self.bind_class("Toplevel", "<Map>", raise_new, add="+")

    def _dropdown(self, parent, text: str, items: List[Tuple]):
        """A button that opens a menu. items: (label, command) · ("-",) · ("check", label, BooleanVar) ·
        ("cascade", label, [items])."""
        menu = self._make_menu(items)
        btn = self._tool(parent, text, lambda: None)
        btn.configure(command=lambda: menu.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height()))
        btn.menu = menu
        return btn

    def _placeholder(self, entry, var, text: str):
        """A dim hint inside an empty entry ("Search codes"), gone while you type or the entry has the focus."""
        bg = entry.cget("bg")
        hint = tk.Label(entry, text=text, font=self.f["small"], fg=THEME["fg_dim"], bg=bg, cursor="xterm")
        def update(*_):
            try:
                empty = not var.get() and self.focus_get() is not entry
            except Exception:  # noqa: BLE001
                empty = not var.get()
            if empty:
                hint.place(x=4, rely=0.5, anchor="w")
            else:
                hint.place_forget()
        hint.bind("<Button-1>", lambda e: entry.focus_set())
        entry.bind("<FocusIn>", update, add="+")
        entry.bind("<FocusOut>", update, add="+")
        var.trace_add("write", update)
        update()
        return hint

    def _make_menu(self, items: List[Tuple]) -> PopupMenu:
        def build(menu, entries):
            for it in entries:
                if it[0] == "-":
                    menu.add_separator()
                elif it[0] == "check":
                    menu.add_checkbutton(label=it[1], variable=it[2])
                elif it[0] == "cascade":
                    sub = PopupMenu(self, parent=menu)
                    build(sub, it[2])
                    menu.add_cascade(label=it[1], menu=sub)
                else:
                    menu.add_command(label=it[0], command=it[1])
        menu = PopupMenu(self)
        build(menu, items)
        return menu

    TRANSCRIPT_SIZES = [0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.5]

    @property
    def transcript_scale(self) -> float:
        return float(self.__dict__.get("_transcript_scale") or self.settings.get("transcript_scale") or 1.0)

    def _set_transcript_size(self, scale: float, save: bool = True):
        """The transcript and the segment box only, on top of View ▸ Larger/Smaller Text (which sizes everything)."""
        self._transcript_scale = min(self.TRANSCRIPT_SIZES[-1], max(self.TRANSCRIPT_SIZES[0], round(float(scale), 2)))
        _fam, base, _w = FONT_SPECS["transcript"]
        self.f["transcript"].configure(size=max(7, int(round(base * self.ui_scale * self._transcript_scale))))
        lbl = self.__dict__.get("lbl_text_size")
        if lbl is not None:
            lbl.config(text=f"{self._transcript_scale * 100:.0f}%")
        var = self.__dict__.get("var_text_size")
        if var is not None and abs(var.get() - self._transcript_scale * 100) > 2.6:
            var.set(self._transcript_scale * 100)  # buttons, keys, wheel move the slider too (not while dragging it)
        if save:
            self.settings["transcript_scale"] = self._transcript_scale
            SettingsStore.save(self.settings)

    def _transcript_size_step(self, direction: int):
        cur = self.transcript_scale
        sizes = self.TRANSCRIPT_SIZES
        if direction > 0:
            nxt = next((s for s in sizes if s > cur + 1e-6), sizes[-1])
        else:
            nxt = next((s for s in reversed(sizes) if s < cur - 1e-6), sizes[0])
        self._set_transcript_size(nxt)

    def _flow(self, parent, **kw) -> FlowFrame:  # (one_line=True: one row, what doesn't fit in a ⋯ menu)
        flow = FlowFrame(parent, **kw)
        self._flows.append(flow)
        return flow

    # ================================================================== small widget helpers
    def _label(self, parent, text: str, font: str = "body", fg: Optional[str] = None, bg: Optional[str] = None, **kw):
        return tk.Label(parent, text=text, bg=bg or THEME["bg_card"], fg=fg or THEME["fg_primary"], font=self.f[font], **kw)

    def _wrapping_label(self, parent, text: str, **kw):
        kw.setdefault("justify", tk.LEFT)
        kw.setdefault("anchor", "w")
        lbl = self._label(parent, text, **kw)
        lbl.bind("<Configure>", lambda e: lbl.configure(wraplength=max(120, e.width - 4)))
        return lbl

    def _check(self, parent, text: str, var, bg: Optional[str] = None, fg: Optional[str] = None, font: str = "body"):
        bg = bg or THEME["bg_card"]
        fg = fg or THEME["fg_primary"]
        style_name = f"C{bg[1:]}{fg[1:]}{font}.TCheckbutton"
        self.style.configure(style_name, background=bg, foreground=fg, font=self.f[font], indicatorbackground=THEME["bg_input"],
                             indicatorforeground="#ffffff", focuscolor=bg, padding=(0, 1))
        self.style.map(style_name, background=[("active", bg)], foreground=[("active", fg)],
                       indicatorbackground=[("selected", THEME["accent"]), ("active", THEME["bg_input"])])
        return ttk.Checkbutton(parent, text=text, variable=var, style=style_name)

    def _tool(self, parent, text: str, cmd, primary: bool = False, tip: Optional[str] = None):
        """A button. tip: what it does and its key, shown on hover — labels stay plain words (no "(M)", "⌘S")."""
        b = ttk.Button(parent, text=text, style=rounded.style_for(parent, "Primary" if primary else "Tool"), command=cmd)
        self._no_focus(b)
        if tip:
            self._tip(b, tip)
        return b

    def _heading(self, parent, text: str, bg: Optional[str] = None, **kw):
        """The one heading style of the window (Tasks, Codebook, Codings, Timeline, Settings cards): small, bold,
        grey, in normal case — the content is what stands out, not its label."""
        return self._label(parent, text, font="section", fg=THEME["fg_secondary"], bg=bg, **kw)

    def _no_focus(self, widget):
        """Buttons and sliders in the main window don't take the keyboard focus when clicked: after ⟲ / ⟳, ▶, Step or
        a switch, the arrows, Return and the other keys still go to the transcript. (Dialogs keep theirs for Tab.)"""
        try:
            if widget.winfo_toplevel() is self:
                widget.configure(takefocus=0)
        except Exception:  # noqa: BLE001
            pass
        return widget

    def _back_to_transcript(self, _event=None):
        """After a choice in a list (Paragraphs, Show) or a typed speed: the keys go to the transcript again."""
        pt = self.__dict__.get("preview_text")
        if pt is not None and self.tx_mode == "edit":
            self.after_idle(pt.focus_set)
        else:
            cd = self.__dict__.get("cd_text")
            if cd is not None:
                self.after_idle(cd.focus_set)

    def _tip(self, widget, text):
        """A tooltip in the app's style; shortcuts written with Mac symbols read Ctrl+… on Linux and Windows."""
        return Tooltip(widget, (lambda: kbd(text())) if callable(text) else kbd(text), font=self.f["small"])

    def _entry(self, parent, var, show: str = "", width: int = 20, font: str = "mono_small"):
        return tk.Entry(parent, textvariable=var, bg=THEME["bg_input"], fg=THEME["fg_primary"], insertbackground=THEME["fg_primary"], relief=tk.FLAT,
                        highlightthickness=1, highlightbackground=THEME["border"], highlightcolor=THEME["accent"], font=self.f[font], show=show, width=width)

    def _separator(self, parent):
        sep = tk.Frame(parent, bg=THEME["border"], width=1, height=self.f["small"].metrics("linespace") + 8)
        sep.condense_separator = True  # (a one-line toolbar drops it where the row ends)
        return sep

    # ================================================================== menu bar
    def _build_menubar(self):
        mb = tk.Menu(self)
        if IS_MAC:
            app_menu = tk.Menu(mb, name="apple", tearoff=0)
            app_menu.add_command(label=f"About Condense {__version__}", command=self._show_about)
            app_menu.add_command(label="Check for Updates…", command=self._check_updates)
            app_menu.add_separator()
            app_menu.add_command(label="Setup & Status…", command=self._show_setup_modal)
            app_menu.add_command(label=self._install_label(), command=self._install_desktop_shortcut)
            mb.add_cascade(menu=app_menu)

        acc = "Command-" if IS_MAC else "Ctrl+"
        file_menu = tk.Menu(mb, tearoff=0)
        file_menu.add_command(label="Add Videos…", accelerator=f"{acc}O", command=self._add_videos)
        file_menu.add_command(label="New Merge Task…", command=self._add_merge_task)
        file_menu.add_command(label="Add Folder…", command=self._add_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Open Transcript…", accelerator=f"{acc}Shift-O" if IS_MAC else "Ctrl+Shift+O", command=self._open_transcript)
        file_menu.add_command(label="Show Output Folder", command=self._open_selected_job_folder)
        file_menu.add_command(label="Re-export Open Transcript", command=self._reexport_open_transcript)
        file_menu.add_command(label="Export Trimmed Video & Transcript…", command=self._export_trimmed_dialog)
        if not IS_MAC:
            file_menu.add_separator()
            file_menu.add_command(label="Setup & Status…", command=self._show_setup_modal)
            file_menu.add_command(label=self._install_label(), command=self._install_desktop_shortcut)
        mb.add_cascade(label="File", menu=file_menu)
        self._build_project_menu(mb)

        em = tk.Menu(mb, tearoff=0)
        em.add_command(label="Undo Transcript Change", accelerator=f"{acc}Z", command=self._undo)
        em.add_command(label="Redo Transcript Change", accelerator=f"{acc}Shift-Z" if IS_MAC else "Ctrl+Shift+Z", command=self._redo)
        em.add_separator()
        em.add_command(label="Mark Segment Checked & Next", accelerator=f"{acc}Return" if IS_MAC else "Ctrl+Enter", command=self._check_and_next)
        em.add_command(label="Mark Whole Transcript Checked (100 %)",
                       command=lambda: self.active_doc is not None and self._mark_transcripts_checked([self.active_doc.path], True))
        em.add_command(label="Mark Whole Transcript Not Checked",
                       command=lambda: self.active_doc is not None and self._mark_transcripts_checked([self.active_doc.path], False))
        em.add_command(label="Toggle Segment Checked  (C)", command=self._toggle_checked)
        em.add_command(label="Find & Replace…", accelerator=f"{acc}F", command=self._toggle_find)
        em.add_command(label="Search All Transcripts…", command=self._search_all_dialog)
        em.add_separator()
        em.add_command(label="Cut / Restore Selected Segments  (X)", command=self._toggle_cut)
        em.add_command(label="Restore All Cuts…", command=self._restore_all_cuts)
        em.add_command(label="Split Segment Before Word  (S)", command=self._split_at_current_word)
        em.add_command(label="Merge Segment with Next  (M)", command=self._merge_with_next)
        em.add_command(label="Delete Segment  (Del)", command=self._delete_segment)
        em.add_separator()
        em.add_command(label="Episodes (Interviews, Phases)…", command=self._episodes_dialog)
        em.add_command(label="Mark Selection as Episode  (E)", command=self._mark_episode)
        em.add_command(label="Find Interview Clips in Recording…", command=self._link_clips_dialog)
        em.add_command(label="Select All Segments  (⌘A in transcript)" if IS_MAC else "Select All Segments  (Ctrl+A in transcript)", command=self._select_all_segments)
        em.add_separator()
        mm = tk.Menu(em, tearoff=0)
        for label, text, key in MARKERS:
            mm.add_command(label=f"{label}   {text.replace('{t}', 't')}", accelerator=f"Control-Shift-{key}" if IS_MAC else f"Ctrl+Shift+{key}",
                           command=lambda t=text: self._insert_marker(t))
        em.add_cascade(label="Insert Marker", menu=mm)
        self.marker_menu = mm
        em.add_separator()
        em.add_command(label="Re-transcribe Passage…", accelerator=f"{acc}Shift-R" if IS_MAC else "Ctrl+Shift+R", command=self._retranscribe_dialog)
        em.add_command(label="Re-run Speaker Detection…", command=self._rediarize_dialog)
        em.add_separator()
        em.add_command(label="Restore Backup…", command=self._restore_backup)
        em.add_command(label="Show Backups Folder", command=self._show_backups)
        mb.add_cascade(label="Edit", menu=em)

        q = tk.Menu(mb, tearoff=0)
        q.add_command(label="Run Pending Tasks", accelerator=f"{acc}R", command=self._start_pipeline)
        q.add_command(label="Stop", accelerator=f"{acc}.", command=self._stop_pipeline)
        q.add_separator()
        q.add_command(label="Move Up", command=self._move_up)
        q.add_command(label="Move Down", command=self._move_down)
        q.add_command(label="Remove Selected", command=self._remove_selected)
        q.add_command(label="Combine Selected into One Merge Task", command=self._combine_selected)
        q.add_command(label="Split Merge Task into Single Tasks", command=self._split_merge_task)
        q.add_command(label="Apply Current Settings to Selected", command=self._task_use_current_settings)
        q.add_command(label="Reset Selected to Pending", command=self._reset_selected_jobs)
        q.add_command(label="Clear Completed", command=self._clear_completed_jobs)
        mb.add_cascade(label="Queue", menu=q)
        self.queue_menu = q

        v = tk.Menu(mb, tearoff=0)
        v.add_command(label="Larger Text", accelerator=f"{acc}+", command=lambda: self._set_zoom(self.ui_scale + 0.1))
        v.add_command(label="Smaller Text", accelerator=f"{acc}-", command=lambda: self._set_zoom(self.ui_scale - 0.1))
        v.add_command(label="Actual Size", accelerator=f"{acc}0", command=lambda: self._set_zoom(1.0))
        v.add_separator()
        v.add_command(label="Larger Transcript Text", accelerator=f"{acc}Option-+" if IS_MAC else "Ctrl+Alt++",
                      command=lambda: self._transcript_size_step(+1))
        v.add_command(label="Smaller Transcript Text", accelerator=f"{acc}Option--" if IS_MAC else "Ctrl+Alt+-",
                      command=lambda: self._transcript_size_step(-1))
        v.add_command(label="Default Transcript Text", command=lambda: self._set_transcript_size(1.0))
        v.add_separator()
        self.var_show_pct = tk.BooleanVar(value=False)
        v.add_checkbutton(label="Show % on Uncertain Words", variable=self.var_show_pct, command=self._rerender)
        self.var_show_video = tk.BooleanVar(value=True)
        self.var_side_panel = tk.BooleanVar(value=not self.settings.get("side_collapsed"))
        v.add_checkbutton(label="Show Video Preview", variable=self.var_show_video, command=self._toggle_video_panel)
        v.add_checkbutton(label="Show Tasks & Project Panel", variable=self.var_side_panel, accelerator=f"{acc}B",
                          command=lambda: self._toggle_side_panel(bool(self.var_side_panel.get())))
        v.add_separator()
        v.add_command(label="Settings", accelerator=f"{acc}1", command=lambda: self.notebook.select(self.tab_settings))
        v.add_command(label="Console", accelerator=f"{acc}2", command=lambda: self.notebook.select(self.tab_console))
        v.add_command(label="Transcript: Edit", accelerator=f"{acc}3", command=lambda: self._set_tx_mode("edit"))
        v.add_command(label="Transcript: Code", accelerator=f"{acc}4", command=lambda: self._set_tx_mode("code"))
        v.add_command(label="Switch Code / Edit", accelerator=f"{acc}E", command=lambda: self._set_tx_mode())
        v.add_separator()
        v.add_command(label="Keyboard Shortcuts", accelerator=f"{acc}/", command=self._show_shortcuts)
        mb.add_cascade(label="View", menu=v)

        pm = tk.Menu(mb, tearoff=0)
        pm.add_command(label="Play / Pause", accelerator="Esc", command=self._toggle_play)
        pm.add_command(label="Back (one step)", accelerator=f"{acc}[", command=lambda: self._skip(-1))
        pm.add_command(label="Forward (one step)", accelerator=f"{acc}]", command=lambda: self._skip(+1))
        pm.add_command(label="Back (three steps)", accelerator=f"⇧{acc}[" if IS_MAC else "Ctrl+Shift+[", command=lambda: self._skip(-1, big=True))
        pm.add_command(label="Forward (three steps)", accelerator=f"⇧{acc}]" if IS_MAC else "Ctrl+Shift+]", command=lambda: self._skip(+1, big=True))
        steps = tk.Menu(pm, tearoff=0)
        self.var_skip_step = tk.IntVar(value=self._skip_step())
        for sec in self.SKIP_STEPS:
            steps.add_radiobutton(label=f"{sec} seconds", variable=self.var_skip_step, value=sec, command=lambda s=sec: self._set_skip_step(s))
        pm.add_cascade(label="Step", menu=steps)
        pm.add_command(label="Go to Time…", accelerator=f"{acc}J", command=self._goto_time_dialog)
        pm.add_separator()
        pm.add_command(label="Faster", accelerator=f"{acc}Shift-." if IS_MAC else "Ctrl+Shift+.", command=lambda: self._speed_step(+1))
        pm.add_command(label="Slower", accelerator=f"{acc}Shift-," if IS_MAC else "Ctrl+Shift+,", command=lambda: self._speed_step(-1))
        pm.add_command(label="Normal Speed", command=lambda: (self.var_speed.set("1×"), self._on_speed_change()))
        pm.add_separator()
        pm.add_command(label="Save Segment Edit", accelerator=f"{acc}S", command=self._save_segment_edit)
        pm.add_command(label="Insert Missing Segment…", accelerator=f"{acc}I", command=self._insert_segment_dialog)
        pm.add_command(label="Replay Segment  (R)", command=self._replay_segment)
        pm.add_command(label="Next Segment  (↓)", command=lambda: self._move_segment(+1))
        pm.add_command(label="Previous Segment  (↑)", command=lambda: self._move_segment(-1))
        pm.add_command(label="Next Uncertain Word  (→)", command=lambda: self._jump_low_conf(+1))
        pm.add_command(label="Previous Uncertain Word  (←)", command=lambda: self._jump_low_conf(-1))
        mb.add_cascade(label="Playback", menu=pm)

        hm = tk.Menu(mb, name="help", tearoff=0)
        hm.add_command(label="Test GPU…", command=self._test_gpu)
        hm.add_command(label="Check for Updates…", command=self._check_updates)
        hm.add_checkbutton(label="Check for Updates Automatically", variable=self.var_update_auto, command=self._toggle_update_auto)
        hm.add_separator()
        guide = "docs/install-mac.md" if IS_MAC_PLATFORM else ("docs/install-windows.md" if PLATFORM == "windows" else "docs/install-linux.md")
        hm.add_command(label="User Guide", command=lambda: self._open_url(f"https://github.com/{updates.REPO}/blob/main/docs/user-guide.md"))
        hm.add_command(label="Installation & Troubleshooting Guide", command=lambda: self._open_url(f"https://github.com/{updates.REPO}/blob/main/{guide}"))
        hm.add_command(label="What's New (Release Notes)", command=lambda: self._open_url(updates.RELEASES_PAGE))
        hm.add_command(label="Report a Problem…", command=lambda: self._open_url(f"https://github.com/{updates.REPO}/issues/new/choose"))
        if not IS_MAC:
            hm.add_separator()
            hm.add_command(label=f"About Condense {__version__}", command=self._show_about)
        mb.add_cascade(label="Help", menu=hm)
        self.configure(menu=mb)

        keys = {
            "o": self._add_videos, "O": self._open_transcript, "r": self._start_pipeline, "period": self._stop_pipeline,
            "equal": lambda: self._set_zoom(self.ui_scale + 0.1), "plus": lambda: self._set_zoom(self.ui_scale + 0.1),
            "minus": lambda: self._set_zoom(self.ui_scale - 0.1), "0": lambda: self._set_zoom(1.0),
            "1": lambda: self.notebook.select(self.tab_settings), "2": lambda: self.notebook.select(self.tab_console),
            "3": lambda: self._set_tx_mode("edit"), "4": lambda: self._set_tx_mode("code"),
            "bracketleft": lambda: self._skip(-1), "bracketright": lambda: self._skip(+1),
            "braceleft": lambda: self._skip(-1, big=True), "braceright": lambda: self._skip(+1, big=True),
            "j": self._goto_time_dialog,
            "s": self._save_segment_edit,
            "i": self._insert_segment_dialog,
            "slash": self._show_shortcuts,
            "f": self._toggle_find,
            "b": self._toggle_side_panel,
        }
        # Use the <Mod-Key-x> form: in Tk "<Command-1>" would mean Command + mouse button 1.
        for key, fn in keys.items():
            self.bind_all(f"<{MOD}-Key-{key}>", lambda e, fn=fn: (fn(), "break")[-1])
        alt = "Option" if IS_MAC else "Alt"
        for key, d in (("equal", +1), ("plus", +1), ("minus", -1)):
            self.bind_all(f"<{MOD}-{alt}-Key-{key}>", lambda e, d=d: (self._transcript_size_step(d), "break")[-1])
        self.bind_all("<Escape>", self._toggle_play)  # works while typing in the segment editor
        if not IS_MAC:
            # On macOS the menu's ⌘↩ works wherever the focus is (Tk hands accelerators to the system menu). On Linux and
            # Windows menu accelerators are only labels, so Ctrl+Enter is bound for the whole window here — also
            # while the transcript (not the text box) has the focus.
            for seq in ("<Control-Key-Return>", "<Control-Key-KP_Enter>"):
                self.bind_all(seq, self._check_and_next_key)
        self.bind_all(f"<{MOD}-Key-z>", self._undo_key)
        self.bind_all(f"<{MOD}-Key-R>", lambda e: (self._retranscribe_dialog(), "break")[-1])
        self.bind_all(f"<{MOD}-Shift-Key-r>", lambda e: (self._retranscribe_dialog(), "break")[-1])
        self.bind_all(f"<{MOD}-Shift-Key-z>", self._redo_key)
        self.bind_all(f"<{MOD}-Key-Z>", self._redo_key)
        for _label, text, key in MARKERS:
            # With Shift, Tk reports the capital letter. Plain Ctrl+letter only on the Mac (where ⌃ is not ⌘): on Linux and
            # Windows Ctrl+C is copy and Ctrl+I inserts a segment, so markers are Ctrl+Shift+letter there.
            for seq in ((f"<Control-Shift-Key-{key}>", f"<Control-Key-{key}>") if IS_MAC else (f"<Control-Shift-Key-{key}>",)):
                self.bind_all(seq, lambda e, t=text: (self._insert_marker(t), "break")[-1])
        # Shift turns . and , into > and < — bind both spellings so the shortcut works on every keyboard layout
        for seq, d in ((f"<{MOD}-Key-greater>", +1), (f"<{MOD}-Shift-Key-period>", +1), (f"<{MOD}-Key-less>", -1), (f"<{MOD}-Shift-Key-comma>", -1)):
            self.bind_all(seq, lambda e, d=d: (self._speed_step(d), "break")[-1])

    # ================================================================== header & footer
    def _build_header(self):
        header = tk.Frame(self, bg=THEME["bg_panel"], padx=14, pady=7)
        header.pack(fill=tk.X, side=tk.TOP)
        self._tool(header, "Setup & Status", self._show_setup_modal).pack(side=tk.RIGHT)
        self._build_project_button(header)
        self._label(header, "Condense", font="title", bg=THEME["bg_panel"]).pack(side=tk.LEFT)
        # the computer in a few words — a dot and "GPU ready"; the details on hover and in Setup & Status
        hw = tk.Frame(header, bg=THEME["bg_panel"], cursor="hand2")
        hw.pack(side=tk.LEFT, padx=(16, 10))
        self.hw_dot = tk.Label(hw, text="●", font=self.f["small"], fg=THEME["ok"], bg=THEME["bg_panel"])
        self.hw_dot.pack(side=tk.LEFT, padx=(0, 5))
        self.sub_lbl = self._label(hw, "", font="small", fg=THEME["fg_secondary"], bg=THEME["bg_panel"])
        self.sub_lbl.pack(side=tk.LEFT)
        self.hw_details = ""
        for w in (hw, self.hw_dot, self.sub_lbl):
            w.bind("<Button-1>", lambda e: self._show_setup_modal())
        self._tip(self.sub_lbl, lambda: self.hw_details + "\n(click for Setup & Status)")
        self._update_header()

    def _update_header(self):
        g = self.gpu_info
        if g.get("warning"):
            self.hw_details = f"{g.get('gpu_name')}  ·  ⚠ {g['warning']}"
            self.hw_dot.configure(fg=THEME["warn"])
            w = str(g["warning"])
            self.sub_lbl.configure(text="⚠ " + (w if len(w) <= 70 else w[:69].rstrip() + "…"), fg=THEME["warn"])  # all of it on hover
            return
        vram = (g.get("gpu_test") or {}).get("vram_gb")
        parts = [str(g.get("gpu_name")) + (f" ({vram:g} GB)" if vram and g.get("torch_gpu") else "")]
        if "mlx_ok" in g:
            parts.append(f"MLX {'✓' if g['mlx_ok'] else '✗'}")
            parts.append(f"Metal {'✓' if g['mps_ok'] else '✗'}")
            parts.append("VideoToolbox ✓")
        if "torch_gpu" in g:
            parts.append(f"{g.get('gpu_api') or 'PyTorch'} {'✓' if g['torch_gpu'] else '✗'}")
            if "hw_encoders" in g:
                names = {"hevc_nvenc": "NVENC", "hevc_amf": "AMF", "hevc_qsv": "Quick Sync"}
                parts.append(" ".join(names[e] for e in g["hw_encoders"]) + " ✓" if g["hw_encoders"] else "GPU encoder ✗")
            else:
                parts.append(f"VA-API {'✓' if g.get('vaapi_ok') else '✗'}")
        ok = g.get("mlx_ok", g.get("torch_gpu", True))
        self.hw_details = "  ·  ".join(parts)
        self.hw_dot.configure(fg=THEME["ok"] if ok else THEME["warn"])
        self.sub_lbl.configure(text="GPU ready" if ok else "No GPU — transcribing on the CPU", fg=THEME["fg_secondary"] if ok else THEME["warn"])

    def _build_footer(self):
        footer = tk.Frame(self, bg=THEME["bg_panel"], padx=14, pady=4)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        row = tk.Frame(footer, bg=THEME["bg_panel"])
        row.pack(fill=tk.X)
        self.btn_stop = self._tool(row, "■ Stop", self._stop_pipeline)
        self.btn_stop.configure(state=tk.DISABLED)
        self.btn_stop.pack(side=tk.RIGHT, padx=(6, 0))
        self.btn_run = self._tool(row, "▶  Run Pending Tasks", self._start_pipeline, primary=True)
        self.btn_run.pack(side=tk.RIGHT)
        self._build_memory_meter(row)
        self.lbl_status = self._wrapping_label(row, kbd("Ready. Add videos (⌘O) or a merge task, check the task details, then Run (⌘R)."),
                                               font="small", fg=THEME["fg_secondary"], bg=THEME["bg_panel"])
        self.lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self.progress_var = tk.DoubleVar(value=0.0)
        ttk.Progressbar(footer, variable=self.progress_var, maximum=100.0, style="Horizontal.TProgressbar").pack(fill=tk.X, pady=(5, 0))

    # ================================================================== main split
    def _build_main_layout(self):
        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.FLAT, bd=0, bg=THEME["bg_root"], showhandle=False)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=(6, 4))
        left = tk.Frame(self.paned, bg=THEME["bg_panel"], padx=10, pady=8)
        right = tk.Frame(self.paned, bg=THEME["bg_root"])
        self.paned.add(left, minsize=300, stretch="always")
        self.paned.add(right, minsize=480, stretch="always")
        self.side_left, self.side_right = left, right
        self.side_collapsed = False
        # collapsed, the side panel is a thin strip at the left: the analysis (Transcript, Coding) gets the room
        self.side_strip = tk.Frame(self, bg=THEME["bg_panel"], padx=2, pady=6)
        self._tool(self.side_strip, "▸", self._toggle_side_panel).pack(fill=tk.X)
        for name, which in (("Tasks", "tasks"), ("Project", "project")):
            lab = tk.Label(self.side_strip, text="\n".join(name), font=self.f["small"], fg=THEME["fg_secondary"], bg=THEME["bg_panel"],
                           cursor="hand2", pady=8)
            lab.pack(fill=tk.X, pady=(10, 0))
            lab.bind("<Button-1>", lambda e, w=which: self._toggle_side_panel(show=w))
        self.after(80, self._restore_sash)

        # Tasks and the project's recordings share the left side; the project tab is shown when a project is open
        self.left_tabs = ttk.Notebook(left)
        self.left_tabs.pack(fill=tk.BOTH, expand=True)
        self.tab_tasks = tk.Frame(self.left_tabs, bg=THEME["bg_panel"], padx=8, pady=8)
        self.tab_project = tk.Frame(self.left_tabs, bg=THEME["bg_panel"], padx=8, pady=8)
        self.left_tabs.add(self.tab_tasks, text="Tasks")
        self.left_tabs.add(self.tab_project, text="Project")
        self._build_queue_panel(self.tab_tasks)
        self._build_project_panel(self.tab_project)
        if self._project_dir() is not None:
            self.left_tabs.select(self.tab_project)
        hide = self._tool(left, "◂", self._toggle_side_panel)
        hide.place(relx=1.0, x=0, y=-4, anchor="ne")  # top right, beside the Tasks / Project tabs
        if self.settings.get("side_collapsed"):
            self.after(120, lambda: self._toggle_side_panel(False))

        # the tabs on top; under them one timeline, shown for the Transcript and the Coding tab (its height can be dragged)
        self.right_area = tk.PanedWindow(right, orient=tk.VERTICAL, sashwidth=6, bd=0, bg=THEME["bg_root"], showhandle=False)
        self.right_area.pack(fill=tk.BOTH, expand=True)
        self.notebook = ttk.Notebook(self.right_area)
        self.right_area.add(self.notebook, minsize=300, stretch="always")
        self.tl_frame = tk.Frame(self.right_area, bg=THEME["bg_panel"], padx=6, pady=2)
        self.tl_shown = False
        self.tab_settings = tk.Frame(self.notebook, bg=THEME["bg_panel"])
        self.tab_console = tk.Frame(self.notebook, bg=THEME["bg_panel"], padx=8, pady=8)
        self.tab_preview = tk.Frame(self.notebook, bg=THEME["bg_panel"], padx=10, pady=8)
        self.notebook.add(self.tab_settings, text="Settings")
        self.notebook.add(self.tab_console, text="Console")
        self.notebook.add(self.tab_preview, text="Transcript")
        self._build_settings_tab()
        self._build_console_tab()
        self._build_preview_tab()
        self._build_coding_tab()
        self._build_cd_timeline(self.tl_frame)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._tl_show_for_tab(), add="+")
        self.after(50, self._tl_show_for_tab)

    def _tl_visible(self) -> bool:
        """Is the timeline on screen (the Transcript tab open, in Code or Edit mode)?"""
        try:
            return self.notebook.select() == str(self.tab_preview)
        except Exception:
            return False

    def _tl_show_for_tab(self):
        want = self._tl_visible()
        if want and not self.tl_shown:
            height = int(self.settings.get("timeline_height", 170))
            try:  # a short screen: the tab's text keeps its room, the timeline gets what is left
                area_h = int(self.right_area.winfo_height())
                if area_h > 200:
                    height = max(110, min(height, area_h - self._tl_keep()))
            except Exception:
                pass
            self.right_area.add(self.tl_frame, minsize=70, height=height, stretch="never")
            self.tl_shown = True
            self.after_idle(lambda: self._cdt_draw(request_frames=True))
        elif not want and self.tl_shown:
            try:
                self.settings["timeline_height"] = max(70, int(self.tl_frame.winfo_height()))
            except Exception:
                pass
            self.right_area.forget(self.tl_frame)
            self.tl_shown = False
        return self.tl_shown

    def _toggle_side_panel(self, show=None):
        """Collapse the Tasks / Project panel to a strip at the left, or bring it back (show: True, False, "tasks" or
        "project" — which tab to show; None toggles)."""
        want = self.side_collapsed if show is None else bool(show)  # toggling: shown when it was collapsed
        if want and self.side_collapsed:
            self.side_strip.pack_forget()
            self.paned.add(self.side_left, before=self.side_right, minsize=300, stretch="always")
            self.side_collapsed = False
            self.after(60, self._restore_sash)
        elif not want and not self.side_collapsed:
            try:
                self.settings["sash_fraction"] = round(self.paned.sash_coord(0)[0] / max(1, self.paned.winfo_width()), 3)
            except Exception:
                pass
            self.paned.forget(self.side_left)
            self.side_strip.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=(6, 4), before=self.paned)
            self.side_collapsed = True
        if show in ("tasks", "project"):
            self.left_tabs.select(self.tab_tasks if show == "tasks" else self.tab_project)
        self.var_side_panel.set(not self.side_collapsed)
        self.settings["side_collapsed"] = self.side_collapsed
        self.after(150, lambda: self._video_resized(self._video_screen()))  # more room: fit the picture again
        return not self.side_collapsed

    def _restore_sash(self):
        if self.side_collapsed:
            return
        if self.paned.winfo_width() <= 1:
            self.after(100, self._restore_sash)
            return
        try:
            frac = min(0.6, max(0.22, float(self.settings.get("sash_fraction", 0.36))))
            self.paned.sash_place(0, int(self.paned.winfo_width() * frac), 0)
        except Exception:
            pass

    # ================================================================== settings persistence
    def _apply_settings(self):
        for key, value in (self.settings.get("vars") or {}).items():
            var = self._persist.get(key)
            if var is None or (key in self._combo_values and value not in self._combo_values[key]):
                continue
            try:
                var.set(value)
            except Exception:
                pass
        self.lbl_hb_q.config(text=self._quality_text(self.var_hb_quality.get()))
        if self.var_remember_token.get():
            self._stored_token = SecretStore.load()
            if self._stored_token:
                self.var_hf_token.set(self._stored_token)

    def _save_settings(self):
        values = {}
        for key, var in self._persist.items():
            try:
                values[key] = var.get()
            except Exception:
                pass
        self.settings["vars"] = values
        self.settings["ui_scale"] = self.ui_scale
        self._remember_position()
        try:
            try:
                full = bool(int(self.attributes("-fullscreen")))
            except Exception:
                full = False
            if not full:  # a full-screen size would reopen as an oversized ordinary window
                self.settings["geometry"] = self.geometry()
            if not self.__dict__.get("side_collapsed"):
                self.settings["sash_fraction"] = round(self.paned.sash_coord(0)[0] / max(1, self.paned.winfo_width()), 3)
        except Exception:
            pass
        SettingsStore.save(self.settings)

    def _on_close(self):
        if self.worker is not None and self.worker.is_alive():
            if not messagebox.askyesno("Quit?", "A pipeline run is in progress. Stop it and quit?", parent=self):
                return
            self.stop_event.set()
            proc = self.worker.current_proc
            if proc is not None and proc.poll() is None:
                proc.terminate()
        try:
            self._autosave_edit(rerender=False)
        except Exception:
            pass
        self._sync_token()
        self._save_settings()
        self._save_queue()
        self._player_pause()
        self._video_stop()
        proc = self.__dict__.get("_rerun_proc")
        if proc is not None and proc.poll() is None:
            proc.terminate()
        self._wait_for_exports()
        self.destroy()

    # ================================================================== dialogs
    def _show_about(self):
        how = "installed with the installer — updates: Help ▸ Check for Updates" if updates.update_command() else "a development copy (update with git pull)"
        messagebox.showinfo("About Condense", f"Condense {__version__}\n\nLocal video, audio and transcript processing for qualitative research.\n"
                                              f"This copy is {how}.\n\nMIT licence · https://github.com/{updates.REPO}", parent=self)

    @staticmethod
    def _install_label() -> str:
        if IS_MAC_PLATFORM:
            return "Install App in ~/Applications"
        return "Add Condense to the Start Menu" if PLATFORM == "windows" else "Add Condense to the App Menu"

    def _install_desktop_shortcut(self):
        try:
            paths = AppInstaller.install_shortcut()
            where = ("Launchpad / Spotlight; drag it to the Dock" if IS_MAC_PLATFORM else
                     "Start menu and Desktop; right-click to pin it to the taskbar" if PLATFORM == "windows" else
                     "find it in your app menu; pin it to the dock from there")
            self._append_log(f"Installed {paths['app']} ({where}).", "SUCCESS")
            if paths.get("desktop_icon"):
                self._append_log(f"Desktop link: {paths['desktop_icon']}", "INFO")
            self._append_log(f"App launches log to {paths['log']}", "INFO")
        except Exception as exc:
            self._append_log(f"Failed to install app: {exc}", "ERROR")
        self.notebook.select(self.tab_console)

    def _show_setup_modal(self):
        win = tk.Toplevel(self)
        win.title("Setup & Status")
        win.geometry("720x520")
        win.minsize(480, 320)
        win.configure(bg=THEME["bg_panel"])
        bar = tk.Frame(win, bg=THEME["bg_panel"])
        bar.pack(fill=tk.X, padx=14, pady=(12, 0))
        self._tool(bar, self._install_label(), lambda: (win.destroy(), self._install_desktop_shortcut())).pack(side=tk.LEFT)
        self._tool(bar, "Keyboard Shortcuts", self._show_shortcuts).pack(side=tk.LEFT, padx=(6, 0))
        self._tool(bar, "Test GPU", lambda: (win.destroy(), self._test_gpu())).pack(side=tk.LEFT, padx=(6, 0))
        txt = tk.Text(win, bg="#0b0c10", fg="#a7f3d0", font=self.f["mono_small"], padx=12, pady=12, wrap=tk.WORD, highlightthickness=0)
        txt.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)
        status = ["# Status"]
        if self.deps:
            for name, label in (("ffmpeg", "ffmpeg"), ("handbrake", "HandBrakeCLI"), ("whisper", "Whisper"), ("losslesscut", "LosslessCut")):
                status.append(f"  {'✓' if self.deps.get(name) else '✗'} {label}: {self.deps.get(name) or 'not found'}")
        else:
            status.append("  (still detecting…)")
        status.append(f"  Python for Whisper: {MacAppInstaller.find_best_python()}  (override: CONDENSE_WHISPER_PYTHON)")
        if self.gpu_info.get("accel_status"):
            status.append(f"  Acceleration: {self.gpu_info['accel_status']}")
        if self.gpu_info.get("media_engine"):
            status.append(f"  Video encoding: {self.gpu_info['media_engine']}")
        status.append(f"  Token storage: {SecretStore.LABEL if SecretStore.available() else 'not available'}")
        status.append(f"  Settings file: {SettingsStore.PATH}")
        status.append(f"  App launcher log: {log_file()}")
        if IS_MAC_PLATFORM:
            guide = (
                "# Install or update (from the Condense folder)\n"
                "./scripts/install-mac.sh                   # Homebrew tools, ~/.condense/env, the app\n"
                "./scripts/install-mac.sh --with-pyannote   # + neural speaker detection\n\n"
                "# Optional: LosslessCut for trimming before transcription\n"
                "brew install --cask losslesscut\n\n"
                "Full guide: docs/install-mac.md\n")
        elif PLATFORM == "windows":
            guide = (
                "# Install or update (PowerShell)\n"
                "irm https://raw.githubusercontent.com/s-hurtado26/condense/main/install.ps1 | iex\n\n"
                "# Check what PyTorch sees\n"
                f"& \"{MacAppInstaller.find_best_python()}\" -c \"import torch; print(torch.cuda.is_available(), torch.version.hip or torch.version.cuda)\"\n\n"
                "Full guide: docs/install-windows.md\n")
        else:
            guide = (
                "# Install or update (from the Condense folder)\n"
                "./scripts/install-linux.sh --gpu rocm      # AMD; or --gpu cuda (NVIDIA) / --gpu cpu\n"
                "./scripts/install-linux.sh --venv ~/rocm_whisper_env   # reuse a PyTorch env that already works\n\n"
                "# Check what PyTorch sees\n"
                f"{MacAppInstaller.find_best_python()} -c \"import torch; print(torch.cuda.is_available(), torch.version.hip or torch.version.cuda)\"\n\n"
                "Full guide: docs/install-linux.md\n")
        txt.insert("1.0", "\n".join(status) + "\n\n" + guide + "\nKeyboard shortcuts: View ▸ Keyboard Shortcuts\n")
        txt.config(state=tk.DISABLED)



def launch_gui() -> None:
    if os.name == "nt":
        try:  # sharp text on high-resolution screens (otherwise Windows scales the window up and blurs it)
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = CondenseApp()
    app.mainloop()
