"""Code mode of the Transcript tab: the project's codebook on the left, the open transcript with a coloured stripe
for every coding, and the transcript's codings below. Edit mode (editor.py) is the same tab with the segment editor;
⌘E / Ctrl+E switches, and the player, the video and the timeline belong to both.

Code words: select them in the text, then double-click a code (or press Return to use the selected code, or 1–9 for
the recent codes, or N for a new code). Code by time — what happens without words, or before the transcript is
checked: mark a range on the timeline below (coding_timeline.py) and code it the same way. Codings are saved in the transcript (with backups and undo); the codebook in the study folder.
"""
import bisect

from condense.core import coding as cod
from condense.core import episodes as eplib
from condense.core import project as proj
from condense.gui import textrender
from condense.gui._common import *  # noqa: F401,F403

STRIPE_W, STRIPE_GAP, MAX_COLS = 5, 3, 8


class CodingMixin:
    # ================================================================== building
    def _build_coding_tab(self):
        """Code mode of the Transcript tab: the codebook left of the text, the transcript with stripes, the codings under
        it; its toolbar in place of the Edit toolbar. The player, the video and the timeline are the tab's own."""
        T = THEME
        self._cd = {"doc": None, "words": [], "line_words": {}, "resolved": [], "sel": None, "tl_drag": None,
                    "recent": [], "rendered_for": None}
        # ---- codebook (or: open a project first) ----
        self.cd_left = tk.Frame(self.tx_paned, bg=T["bg_panel"], padx=4)
        self.cd_none = tk.Frame(self.cd_left, bg=T["bg_panel"])
        self.cd_none_lbl = self._wrapping_label(self.cd_none, "", font="small", fg=T["fg_secondary"], bg=T["bg_panel"])
        self.cd_none_lbl.pack(fill=tk.X, pady=(0, 8))
        row = tk.Frame(self.cd_none, bg=T["bg_panel"])
        row.pack(fill=tk.X)
        self._tool(row, "New Project…", self._new_project_dialog, primary=True).pack(side=tk.LEFT)
        self._tool(row, "Open Project…", self._open_project_dialog).pack(side=tk.LEFT, padx=(6, 0))

        left = self.cd_book = tk.Frame(self.cd_left, bg=T["bg_panel"])
        hdr = tk.Frame(left, bg=T["bg_panel"])
        hdr.pack(fill=tk.X)
        self._heading(hdr, "Codebook", bg=T["bg_panel"]).pack(side=tk.LEFT)
        self.var_cd_search = tk.StringVar(value="")
        ent = self._entry(left, self.var_cd_search, font="small", width=20)
        ent.pack(fill=tk.X, pady=(6, 4))
        self._placeholder(ent, self.var_cd_search, "Search codes")
        self.var_cd_search.trace_add("write", lambda *a: self._cd_fill_codebook())
        # one row: + Code, + Subcode, Edit…; the rest (and what doesn't fit) in ⋯
        bar = self._flow(left, padx=3, pady=3, bg=T["bg_panel"], one_line=True, extra_menu=lambda: self.cd_book_menu)
        bar.pack(fill=tk.X)
        bar.add(self._tool(bar, "+ Code", lambda: self._cd_new_code(parent=None), tip="A new top-level code"))
        bar.add(self._tool(bar, "+ Subcode", lambda: self._cd_new_code(parent=self._cd_selected_code()), tip="A new code under the chosen one"))
        bar.add(self._tool(bar, "Edit…", lambda: self._cd_edit_code(self._cd_selected_code()), tip="Name, colour and description of the chosen code"))
        self.cd_book_menu = self._make_menu([
            ("Merge into another code…", lambda: self._cd_merge_dialog(self._cd_selected_code())),
            ("Delete code…", lambda: self._cd_delete_code(self._cd_selected_code())),
            ("-",),
            ("Show on the timeline / hide", lambda: self._cdt_set_shown(self._cd_selected_code(),
                                                                         self._cd_selected_code() not in self._cdt_shown_codes())),
            ("Timeline: back to the codes used", lambda: [self._cdt_set_shown(c, False) for c in self._cdt_shown_codes()]),
            ("-",),
            ("Refresh counts", lambda: self._cd_fill_codebook(recount=True)),
        ])
        tf = tk.Frame(left, bg=T["bg_panel"])
        tf.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        tree = ttk.Treeview(tf, columns=("n",), show="tree", style="Queue.Treeview", selectmode="browse")
        tree.column("#0", width=200, stretch=True)
        tree.column("n", width=44, anchor="e", stretch=False)
        sb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.bind("<Double-Button-1>", lambda e: self._cd_apply(self._cd_selected_code()))
        tree.bind("<<TreeviewSelect>>", lambda e: (self._cd_show_code_info(), self._cd_fill_list()))
        for seq in ("<Button-3>",) + (("<Button-2>", "<Control-Button-1>") if IS_MAC else ()):
            tree.bind(seq, self._cd_code_menu)
        self.cd_tree = tree
        self.lbl_cd_info = self._wrapping_label(left, "", font="small", fg=T["fg_secondary"], bg=T["bg_panel"])
        self.lbl_cd_info.pack(fill=tk.X, pady=(6, 0))

        # ---- the Code toolbar (in place of the Edit toolbar) ----
        top = self._flow(self.mode_holder, padx=4, pady=5, bg=T["bg_panel"], one_line=True)  # one row; the rest in ⋯
        self.cd_bar = top
        top.add(self._tool(top, "Code selection", lambda: self._cd_apply(self._cd_selected_code()),
                           tip="Code the selection with the chosen code  ↩   (or 1–9 for a recent code)"))
        top.add(self._tool(top, "New code", lambda: self._cd_new_code(parent=self._cd_selected_code(), apply=True),
                           tip="A new code for the selection  N"))
        top.add(self._tool(top, "By time…", lambda: self._cd_time_dialog(*(self._cdt_mark() or (None, None))),
                           tip="Code a stretch of the video by its times (I and O on the timeline)"))
        top.add(self._tool(top, "✎ Comment", lambda: self._comment_dialog(), tip="Comment on the selection or the open segment  M"))
        top.add(self._separator(top))
        top.add(self._tool(top, "▶ Selection", self._cd_play_selection, tip="Play what is selected"))
        top.add(self._tool(top, "⇔ Video", self._cd_video_size, tip="Make the video larger or smaller"))
        self._cd_recent_items: List = []  # the recent codes: chips at the end of the same row (what doesn't fit: in ⋯)
        # ---- the transcript with stripes, the codings under it (in the tab's text column) ----
        body = tk.PanedWindow(self.tx_paned, orient=tk.VERTICAL, sashwidth=6, bd=0, bg=T["bg_panel"], showhandle=False)
        self.cd_body = body
        right = tk.Frame(body, bg=T["bg_panel"])
        body.add(right, minsize=160, stretch="always")
        self.lbl_cd_doc = self._label(right, "", font="small_bold", bg=T["bg_panel"], anchor="w")
        self.lbl_cd_doc.pack(fill=tk.X, pady=(0, 2))
        txt_frame = tk.Frame(right, bg="#0b0d13")
        txt_frame.pack(fill=tk.BOTH, expand=True)
        self.cd_stripes = tk.Canvas(txt_frame, width=STRIPE_W * 3, bg="#0b0d13", highlightthickness=0, bd=0)
        self.cd_stripes.pack(side=tk.LEFT, fill=tk.Y)
        self.cd_text = tk.Text(txt_frame, bg="#0b0d13", fg=T["fg_primary"], font=self.f["transcript"], relief=tk.FLAT, padx=12, pady=10,
                               wrap=tk.WORD, highlightthickness=0, cursor="xterm", spacing1=2, spacing3=2, exportselection=False,
                               selectbackground="#3b4a63", inactiveselectbackground="#3b4a63")
        csb = ttk.Scrollbar(txt_frame, orient=tk.VERTICAL, command=self.cd_text.yview)
        self.cd_text.configure(yscrollcommand=lambda a, b: (csb.set(a, b), self._cd_draw_stripes()))
        csb.pack(side=tk.RIGHT, fill=tk.Y)
        self.cd_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        t = self.cd_text
        t.tag_config("SPK", font=self.f["small_bold"], spacing1=10)  # small and quiet, as in Edit mode
        t.tag_config("TS", foreground=T["fg_dim"], font=self.f["small"])
        t.tag_config("EP", font=self.f["small_bold"], spacing1=8)
        t.tag_config("CODED", underline=True)
        t.tag_config("PLAYING", background="#1d3a2e")
        t.tag_config("KSEL", background="#47395c")
        t.tag_config("MOMENT", font=self.f["small_bold"], spacing1=6, spacing3=4)
        t.tag_raise("sel")
        # read-only, but selectable: block typing, keep selection keys
        t.bind("<Key>", self._cd_key)
        for d in range(1, 10):  # speakers (more specific than <Key>, so it doesn't depend on which state bit Alt is)
            t.bind(f"<{EDIT_MOD}-Key-{d}>", lambda e, d=d: (self._assign_speaker_number(d), "break")[-1])
        t.bind("<Double-Button-1>", self._cd_play_word)
        t.bind("<ButtonRelease-1>", lambda e: self._cd_click(e))
        for seq in ("<Button-3>",) + (("<Button-2>", "<Control-Button-1>") if IS_MAC else ()):
            t.bind(seq, self._cd_text_menu)
        self.cd_stripes.bind("<Button-1>", self._cd_stripe_click)
        self.cd_text.bind("<Configure>", lambda e: self._cd_draw_stripes())

        # ---- codings of this transcript ----
        lst = tk.Frame(body, bg=T["bg_panel"])
        body.add(lst, minsize=110, height=190)
        lbar = tk.Frame(lst, bg=T["bg_panel"])
        lbar.pack(fill=tk.X, pady=(4, 2))
        self.lbl_cd_list = self._heading(lbar, "Codings", bg=T["bg_panel"])
        self.lbl_cd_list.pack(side=tk.LEFT)
        self.var_cd_only = tk.BooleanVar(value=False)
        self._check(lbar, "only the selected code", self.var_cd_only, bg=T["bg_panel"], font="small").pack(side=tk.LEFT, padx=(10, 0))
        self.var_cd_only.trace_add("write", lambda *a: self._cd_fill_list())
        acts = self._flow(lbar, padx=4, pady=2, bg=T["bg_panel"], one_line=True, align="right")  # what doesn't fit: in ⋯
        acts.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        acts.add(self._tool(acts, "Memo…", lambda: self._cd_memo(self._cd_list_selected()), tip="A memo on the chosen coding"))
        acts.add(self._tool(acts, "Change code…", lambda: self._cd_change_code(self._cd_list_selected()), tip="Give the chosen coding another code"))
        acts.add(self._tool(acts, "Delete", lambda: self._cd_remove(self._cd_list_selected()), tip="Delete the chosen coding  Del"))
        # columns that fit the pane: all but the time share the room, none narrower than its heading
        cl = ttk.Treeview(lst, columns=("time", "code", "who", "text"), show="headings", style="Queue.Treeview", height=6, selectmode="browse")
        for c, w, mw, title in (("time", 64, 64, "Time"), ("code", 120, 70, "Code"), ("who", 90, 70, "Speaker"),
                                ("text", 260, 90, "Coded text / memo")):
            cl.heading(c, text=title, anchor="w")
            cl.column(c, width=w, minwidth=mw, anchor="w", stretch=c != "time")
        cl.pack(fill=tk.BOTH, expand=True)
        cl.bind("<Configure>", lambda e: self._cd_fit_columns(e.width), add="+")
        cl.bind("<<TreeviewSelect>>", lambda e: self._cd_select_coding(self._cd_list_selected(), from_list=True))
        cl.bind("<Double-Button-1>", lambda e: self._cd_play_coding(self._cd_list_selected()))
        cl.bind("<Delete>", lambda e: self._cd_remove(self._cd_list_selected()))
        self.cd_list = cl
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._cd_on_tab(), add="+")
        self._cd_show_state()
        for seq in (f"<{MOD}-Key-e>", f"<{MOD}-Key-E>"):
            self.bind_all(seq, lambda e: (self._set_tx_mode(), "break")[-1])
        self._bind_comment_keys()
        self._mode_buttons()
        mode = self.settings.get("tx_mode")
        if mode == "code":
            self.after_idle(lambda: self._set_tx_mode("code", select_tab=False))

    def _cd_fit_columns(self, width: int):
        """The codings list's columns share the pane's width (Tk only clips them): the time as it is, the rest in parts."""
        cl = self.__dict__.get("cd_list")
        if cl is None or width <= 1:
            return
        rest = max(0, width - 66)
        for c, part, least in (("code", 0.28, 70), ("who", 0.22, 64), ("text", 0.50, 90)):
            try:
                cl.column(c, width=max(least, int(rest * part)))
            except Exception:  # noqa: BLE001
                return

    # ================================================================== state
    def _cd_project(self) -> Optional[Path]:
        doc = self.active_doc
        if doc is not None:
            f = proj.find_project_file(Path(doc.path).parent)
            if f is not None:
                return f.parent
        return self._project_dir()

    def _cd_codebook(self) -> Optional["cod.Codebook"]:
        project = self._cd_project()
        if project is None:
            return None
        cb = self.__dict__.get("_cd_cb")
        if cb is None or cb.path.parent != project:
            cb = self._cd_cb = cod.Codebook.for_project(project)
            self._cd_counts = None
        return cb

    def _cd_show_state(self):
        project = self._cd_project()
        if project is None:
            self.cd_book.pack_forget()
            self.cd_none_lbl.config(text="Coding works in a project: the codebook is kept in the study's folder and shared by all its "
                                         "transcripts. Open or create the project of this study first.")
            self.cd_none.pack(fill=tk.X, padx=6, pady=10)
            return False
        self.cd_none.pack_forget()
        self.cd_book.pack(fill=tk.BOTH, expand=True)
        return True

    def _cd_visible(self) -> bool:
        """Is Code mode on screen (the Transcript tab open, in Code mode)?"""
        if self.__dict__.get("tx_mode") != "code":
            return False
        try:
            return self.notebook.select() == str(self.tab_preview)
        except Exception:
            return False

    # ================================================================== Code / Edit
    def _mode_buttons(self):
        code = self.__dict__.get("tx_mode") == "code"
        self.btn_mode_code.configure(style=rounded.style_for(self.btn_mode_code.master, "SegOn" if code else "Seg"))
        self.btn_mode_edit.configure(style=rounded.style_for(self.btn_mode_edit.master, "Seg" if code else "SegOn"))

    def _tx_word_now(self) -> Optional[Tuple[int, int]]:
        """(segment, word) of where you are in the mode shown: the word clicked or selected, else the playhead's."""
        doc = self.active_doc
        if doc is None:
            return None
        if self.__dict__.get("tx_mode") == "code":
            words = self._cd.get("words") or []
            span = self._cd_selection_words()
            n = span[0] if span else self._cd.get("word")
            if n is not None and n < len(words) and self._cd.get("doc") is doc:
                return words[n][3], words[n][4]
        else:
            i = self.__dict__.get("current_span")
            spans = self.__dict__.get("word_spans") or []
            if i is not None and i < len(spans):
                sp = spans[i]
                if sp.get("seg") is not None:
                    return sp["seg"], sp.get("w", 0)
        return None

    def _set_tx_mode(self, mode: Optional[str] = None, select_tab: bool = True):
        """Code (codebook, stripes, codings) or Edit (segment editor, speakers, review marks) — one transcript, one
        video, one timeline. ⌘E / Ctrl+E switches; you stay at the same place in the transcript."""
        cur = self.__dict__.get("tx_mode", "edit")
        mode = ("edit" if cur == "code" else "code") if mode is None else mode
        if select_tab:
            self.notebook.select(self.tab_preview)
        if mode == cur:
            if mode == "code":
                self._cd_refresh()
            return mode
        here = self._tx_word_now()
        pos = self._current_pos() if self.active_doc is not None else None
        video = self.video_frame if self.__dict__.get("_video_panel_shown") else None
        try:  # the widths now: the video column keeps its width, the text gets the rest
            total = int(self.tx_paned.winfo_width())
            video_w = int(video.winfo_width()) if video is not None else 0
        except Exception:
            total, video_w = 0, 0
        if mode == "code":
            self._autosave_edit(rerender=False)  # a correction still being typed is kept
            if self.__dict__.get("_find_visible"):
                self._hide_find()
            self.tx_bar.pack_forget()
            self.cd_bar.pack(fill=tk.X, pady=5)
            self.tx_paned.forget(self.tx_text_frame)
            kw = {"before": video} if video is not None else {}
            book_w = int(self.settings.get("codebook_width", 260))
            self.tx_paned.add(self.cd_left, minsize=200, width=book_w, stretch="never", **kw)
            self.tx_paned.add(self.cd_body, minsize=320, stretch="always", **kw)
            self._tx_place_sashes(total, video_w, [book_w] if video is not None else [])
        else:
            try:
                self.settings["codebook_width"] = max(200, int(self.cd_left.winfo_width()))
            except Exception:
                pass
            self.cd_bar.pack_forget()
            self.tx_bar.pack(fill=tk.X, pady=5)
            self.tx_paned.forget(self.cd_left)
            self.tx_paned.forget(self.cd_body)
            kw = {"before": video} if video is not None else {}
            self.tx_paned.add(self.tx_text_frame, minsize=300, stretch="always", **kw)
            self._tx_place_sashes(total, video_w, [])
        self.tx_mode = mode
        self.settings["tx_mode"] = mode
        self._mode_buttons()
        if mode == "code":
            self._cd_refresh()
            if here is not None:
                self._cd_show_word(*here)
            elif pos is not None:
                self._cd_follow_to(pos)
            try:
                self.cd_text.focus_set()
            except Exception:
                pass
        else:
            if here is not None:
                key = (here[0], here[1])
                i = (self.__dict__.get("span_lookup") or {}).get(key)
                if i is not None:
                    self._select_span(i)
            try:
                self.preview_text.focus_set()
            except Exception:
                pass
        self.after(150, lambda: self._video_resized(self._video_screen()))  # the column changed: fit the picture again
        self._cdt_draw()
        fit = (self.__dict__.get("cdt") or {}).get("fit_h")
        if fit:  # Edit mode needs more height for the tab (the segment editor): the timeline gives it back
            self.after_idle(lambda: self._cdt_fit_height(fit))
        return mode

    def _tx_place_sashes(self, total: int, video_w: int, lefts: List[int]):
        """After a mode switch: the panes on the left at their widths, the video column as wide as before, the text
        in between (a pane added next to the video otherwise starts with no width and stays hidden)."""
        if total <= 0 or video_w <= 0:
            return None
        sash = 6
        x = 0
        try:
            self.update_idletasks()
            places = []
            for w in lefts:
                x += w
                places.append(x)
                x += sash
            places.append(max(x + 320, total - video_w - sash))
            for k, at in enumerate(places):
                self.tx_paned.sash_place(k, at, 0)
        except Exception:
            return None
        return places

    def _cd_top_word(self) -> Optional[Tuple[float, int]]:
        """(time, y on screen) of the first word in view of Code mode's text."""
        t, doc, words = self.cd_text, self._cd.get("doc"), self._cd.get("words") or []
        try:
            line0 = int(str(t.index("@0,0")).split(".")[0])
            for line in range(line0, line0 + 60):
                for n in self._cd.get("line_words", {}).get(line, []):
                    w = words[n]
                    bb = t.bbox(f"{w[0]}.{w[1]}")
                    if isinstance(bb, tuple) and len(bb) == 4 and bb[1] >= 0:
                        return float(doc.segments[w[3]]["words"][w[4]]["start"]), int(bb[1])
        except Exception:
            return None
        return None

    def _cd_place_word(self, when: float, y: int) -> Optional[int]:
        """Scroll Code mode's text so that the word at time `when` is (to within a line) y pixels from the top. By
        whole display lines, not pixels: on Linux, pixel scrolling made Tk lay out a long transcript again and again."""
        doc, words, t = self._cd.get("doc"), self._cd.get("words") or [], self.cd_text
        if doc is None or not words:
            return None
        try:
            starts = [float(doc.segments[w[3]]["words"][w[4]]["start"]) for w in words]
            n = min(len(words) - 1, max(0, bisect.bisect_left(starts, when - 1e-6)))
            index = f"{words[n][0]}.{words[n][1]}"
            t.yview(index)
            bb = t.bbox(index)
            for _ in range(3):  # lines differ in height (speaker headers have space around them): correct again
                if not (isinstance(bb, tuple) and len(bb) == 4 and bb[3] > 0):
                    break
                lines = int(round((int(bb[1]) - y) / bb[3]))
                if not lines:
                    break
                t.yview_scroll(lines, "units")
                bb = t.bbox(index)
            return int(bb[1]) if isinstance(bb, tuple) and len(bb) == 4 else None
        except Exception:
            return None

    def _cd_show_word(self, seg: int, word: int):
        """Scroll Code mode's text to a word and remember it as the place you are."""
        words = self._cd.get("words") or []
        n = next((k for k, w in enumerate(words) if w[3] == seg and w[4] >= word), None)
        if n is None:
            n = next((k for k, w in enumerate(words) if w[3] >= seg), None)
        if n is None:
            return None
        self._cd["word"] = n
        line, c0, _c1 = words[n][0], words[n][1], words[n][2]
        try:
            self.cd_text.see(f"{line}.{c0}")
            self.cd_text.mark_set(tk.INSERT, f"{line}.{c0}")
        except Exception:
            pass
        return n

    def _cd_follow_to(self, pos: float):
        doc = self._cd.get("doc")
        words = self._cd.get("words") or []
        if doc is None or not words:
            return None
        starts = [float(doc.segments[w[3]]["words"][w[4]]["start"]) for w in words]
        n = max(0, bisect.bisect_right(starts, pos) - 1)
        return self._cd_show_word(words[n][3], words[n][4])

    def _cd_speaker_segments(self) -> List[int]:
        """Code mode: the segments ⌃1–9 / Alt+1–9 give a speaker — those of the selected words, else the clicked word's."""
        words = self._cd.get("words") or []
        span = self._cd_selection_words()
        if span is not None:
            return sorted({words[k][3] for k in range(span[0], span[1] + 1)})
        n = self._cd.get("word")
        return [words[n][3]] if n is not None and n < len(words) else []

    def _cd_assign_speaker(self, name: str) -> int:
        segs = self._cd_speaker_segments()  # first: bringing the view up to date (below) would clear the selection
        doc = self._cd_current()
        segs = segs if doc is not None else []
        if not segs:
            self.lbl_status.config(text="Click a word (or select a stretch), then press "
                                        f"{'⌃' if IS_MAC else 'Alt+'}1–9 for its speaker.")
            return 0
        changed = [k for k in segs if doc.set_segment_speaker(k, name)]
        if not changed:
            self.lbl_status.config(text=f"Already {name}.")
            return 0
        if self._commit(f"Assigned {name} to {len(changed)} segment(s) ({'⌘' if IS_MAC else 'Ctrl+'}Z undoes).") is not None:
            self._rerender()
            sel = self.cd_text.tag_ranges("sel")
            self._cd_render(self.active_doc)
            if sel:
                self.cd_text.tag_add("sel", sel[0], sel[-1])
            self.lbl_status.config(text=f"{name}: {len(changed)} segment(s).")
        return len(changed)

    def _cd_on_tab(self):
        if self._cd_visible():
            self._cd_refresh()

    def _cd_refresh(self, force: bool = False):
        """(Re)draw everything for the open transcript. Called when the tab is shown and after changes."""
        if not self._cd_show_state():
            return
        self._cd_fill_codebook(recount=self.__dict__.get("_cd_counts") is None)
        doc = self.active_doc
        if doc is None:
            self.lbl_cd_doc.config(text="Open a transcript (Project tab, or Transcript ▸ Open…) to code it.")
            self.cd_text.delete("1.0", tk.END)
            self._cd["shown_lines"] = None
            return
        self._cd_render(doc)

    # ================================================================== codebook panel
    def _cd_selected_code(self) -> Optional[str]:
        sel = self.cd_tree.selection()
        return sel[0] if sel else None

    def _cd_exact_counts(self, project: Path) -> Dict[str, int]:
        """The counts now (not the ones being counted in the background): before merging or deleting a code."""
        try:
            return cod.counts(project, cache=proj.RowCache(self._overview_cache(project).path))
        except Exception:
            return cod.counts(project)

    def _cd_recount(self, project: Path, wait: bool = False):
        """Count the codings of every transcript in the background (from the overview's cache: only changed
        transcripts are read); the codebook shows at once and gets its numbers when they are ready."""
        if self.__dict__.get("_cd_counting") == str(project):
            return None
        self._cd_counting = str(project)
        if self.__dict__.get("_cd_counts") is None:
            self._cd_counts = {}
        own = cod.counts(project, paths=[self.active_doc.path]) if self.active_doc is not None else {}
        result = {}

        def work():
            try:
                result["counts"] = cod.counts(project, cache=proj.RowCache(self._overview_cache(project).path))
            except Exception:
                result["counts"] = None

        def done():
            if "counts" not in result:
                self.after(150, done)
                return
            self._cd_counting = None
            if result["counts"] is not None and self._cd_project() == project:
                self._cd_counts = result["counts"]
                self._cd_fill_codebook()
            return result["counts"]

        if own:  # this transcript's numbers right away, the project's when counted
            for code, n in own.items():
                self._cd_counts[code] = max(self._cd_counts.get(code, 0), n)
        if wait:
            work()
            return done()
        threading.Thread(target=work, daemon=True).start()
        self.after(150, done)
        return None

    def _cd_fill_codebook(self, recount: bool = False):
        cb = self._cd_codebook()
        tree = self.cd_tree
        keep = self._cd_selected_code()
        for iid in tree.get_children():
            tree.delete(iid)
        if cb is None:
            return
        if recount or self.__dict__.get("_cd_counts") is None:
            self._cd_recount(cb.path.parent)
        counts = self.__dict__.get("_cd_counts") or {}
        q = self.var_cd_search.get().strip().lower()
        shown_on_tl = set(self._cdt_shown_codes()) if self.__dict__.get("cdt") is not None else set()
        shown = set()
        if q:  # a match and the codes above it
            for c in cb.codes:
                if q in c["name"].lower():
                    cur = c
                    while cur is not None:
                        shown.add(cur["id"])
                        cur = cb.get(cur["parent"]) if cur.get("parent") else None
        for depth, c in cb.ordered():
            if q and c["id"] not in shown:
                continue
            tag = f"col{c['color']}"
            tree.tag_configure(tag, foreground=c["color"])
            parent = c.get("parent") or ""
            if parent and not tree.exists(parent):
                parent = ""
            n = counts.get(c["id"], 0)
            lane = "  ◉" if c["id"] in shown_on_tl else ""
            tree.insert(parent, tk.END, iid=c["id"], text=f"■ {c['name']}{lane}", values=(n or "",), open=True, tags=(tag,))
        if keep and tree.exists(keep):
            tree.selection_set(keep)
        if not cb.codes:
            self.lbl_cd_info.config(text="No codes yet. Select some words and press N (or + Code) to start the codebook.")

    def _cd_show_code_info(self):
        cb, cid = self._cd_codebook(), self._cd_selected_code()
        c = cb.get(cid) if cb and cid else None
        if c is None:
            self.lbl_cd_info.config(text="")
            return
        parts = [cb.path_name(cid)]
        for k, label in (("definition", "Definition"), ("use_when", "Use when"), ("not_when", "Not when"), ("example", "Example"), ("memo", "Memo")):
            if c.get(k):
                parts.append(f"{label}: {c[k]}")
        self.lbl_cd_info.config(text="\n".join(parts))

    def _cd_code_menu(self, event):
        iid = self.cd_tree.identify_row(event.y)
        if iid:
            self.cd_tree.selection_set(iid)
        m = PopupMenu(self)
        if iid:
            m.add_command(label="Code the selection (or the marked range) with it", command=lambda: self._cd_apply(iid))
            on = iid in self._cdt_shown_codes()
            m.add_command(label="Hide from the timeline" if on else "Show on the timeline", command=lambda: self._cdt_set_shown(iid, not on))
            m.add_command(label="New subcode…", command=lambda: self._cd_new_code(parent=iid))
            m.add_command(label="Edit…", command=lambda: self._cd_edit_code(iid))
            m.add_command(label="Merge into another code…", command=lambda: self._cd_merge_dialog(iid))
            m.add_command(label="Delete…", command=lambda: self._cd_delete_code(iid))
            m.add_separator()
        m.add_command(label="New code…", command=lambda: self._cd_new_code(parent=None))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return m

    def _cd_code_choices(self) -> List[Tuple[str, str]]:
        cb = self._cd_codebook()
        return [(c["id"], ("   " * d) + c["name"]) for d, c in cb.ordered()] if cb else []

    def _cd_new_code(self, parent: Optional[str] = None, apply: bool = False, name: Optional[str] = None):
        cb = self._cd_codebook()
        if cb is None:
            return None
        if apply and not self._cd_selection_words() and self._cdt_mark() is None:
            self.lbl_cd_doc.config(text="Select the words to code first, or mark a range on the timeline.")
            return None
        where = f" under “{cb.get(parent)['name']}”" if parent and cb.get(parent) else ""
        if name is None:
            name = simpledialog.askstring("New code", f"Name of the new code{where}:", parent=self)
        if not name:
            return None
        try:
            cid = cb.add(name, parent=parent)
        except ValueError as exc:
            messagebox.showerror("New code", str(exc), parent=self)
            return None
        cb.save()
        self._cd_fill_codebook()
        self.cd_tree.selection_set(cid)
        if apply:
            self._cd_apply(cid)
        return cid

    def _cd_edit_code(self, cid: Optional[str]):
        cb = self._cd_codebook()
        c = cb.get(cid) if cb and cid else None
        if c is None:
            return None
        T = THEME
        win = tk.Toplevel(self)
        win.title(f"Code — {c['name']}")
        win.configure(bg=T["bg_panel"], padx=16, pady=14)
        v_name = tk.StringVar(value=c["name"])
        others = [(i, n) for i, n in self._cd_code_choices() if i != cid and i not in cb.descendants(cid)]
        TOP = "(top level)"
        v_parent = tk.StringVar(value=next((n.strip() for i, n in others if i == c.get("parent")), TOP))
        v_color = tk.StringVar(value=c["color"])
        r = 0
        for label, widget in (("Name", self._entry(win, v_name, font="small", width=44)),
                              ("Under", ttk.Combobox(win, textvariable=v_parent, values=[TOP] + [n.strip() for _, n in others], state="readonly",
                                                     width=42, font=self.f["small"]))):
            self._label(win, label, font="small", fg=T["fg_secondary"], bg=T["bg_panel"]).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=3)
            widget.grid(row=r, column=1, sticky="we", pady=3)
            r += 1
        crow = tk.Frame(win, bg=T["bg_panel"])
        self._label(win, "Colour", font="small", fg=T["fg_secondary"], bg=T["bg_panel"]).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=3)
        crow.grid(row=r, column=1, sticky="w", pady=3)
        swatches = []
        for col in cod.COLORS:
            sw = tk.Label(crow, text="  ", bg=col, cursor="hand2", relief=tk.FLAT, highlightthickness=2,
                          highlightbackground=T["fg_primary"] if col == v_color.get() else T["bg_panel"])
            sw.pack(side=tk.LEFT, padx=1)
            sw.bind("<Button-1>", lambda e, col=col: (v_color.set(col), [s.config(highlightbackground=T["fg_primary"] if s.cget("bg") == col else T["bg_panel"]) for s in swatches]))
            swatches.append(sw)
        r += 1
        texts = {}
        for key, label in (("definition", "Definition"), ("use_when", "Use when"), ("not_when", "Not when"), ("example", "Example"), ("memo", "Memo")):
            self._label(win, label, font="small", fg=T["fg_secondary"], bg=T["bg_panel"]).grid(row=r, column=0, sticky="nw", padx=(0, 8), pady=3)
            box = tk.Text(win, height=4 if key == "memo" else 2, width=52, wrap=tk.WORD, font=self.f["small"], bg=T["bg_input"],
                          fg=T["fg_primary"], insertbackground=T["fg_primary"], relief=tk.FLAT, highlightthickness=1,
                          highlightbackground=T["border"])
            box.insert("1.0", c.get(key, ""))
            box.grid(row=r, column=1, sticky="we", pady=3)
            texts[key] = box
            r += 1
        lbl_err = self._label(win, "", font="small", fg=T["warn"], bg=T["bg_panel"])
        lbl_err.grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1

        def save():
            parent = next((i for i, n in others if n.strip() == v_parent.get()), None)
            fields = {k: " ".join(t.get("1.0", "end-1c").split()) if k != "memo" else t.get("1.0", "end-1c").strip() for k, t in texts.items()}
            try:
                if parent != c.get("parent"):
                    cb.move(cid, parent)
                cb.update(cid, name=v_name.get(), color=v_color.get(), **fields)
            except ValueError as exc:
                lbl_err.config(text=str(exc))
                return False
            cb.save()
            win.destroy()
            self._cd_fill_codebook()
            self._cd_show_code_info()
            if self.active_doc is not None and self._cd_visible():
                self._cd_render(self.active_doc)
            return True

        bar = tk.Frame(win, bg=T["bg_panel"])
        bar.grid(row=r, column=0, columnspan=2, sticky="e", pady=(10, 0))
        self._tool(bar, "Cancel", win.destroy).pack(side=tk.LEFT, padx=(0, 6))
        self._tool(bar, "Save", save, primary=True).pack(side=tk.LEFT)
        win.bind("<Escape>", lambda e: (win.destroy(), "break")[-1])
        return win, {"name": v_name, "parent": v_parent, "color": v_color, "texts": texts, "save": save, "error": lbl_err}

    def _cd_save_other(self, doc, message: str):
        """Save a transcript changed outside the editor (merging or deleting codes): backup and an undo step."""
        previous = doc.path.read_text(encoding="utf-8") if doc.path.exists() else None
        doc.save(backup=True)
        if previous is not None:
            self._push_undo(doc.path, message, previous)

    def _cd_merge_dialog(self, cid: Optional[str], target: Optional[str] = None):
        cb = self._cd_codebook()
        c = cb.get(cid) if cb and cid else None
        if c is None:
            return None
        choices = [(i, n) for i, n in self._cd_code_choices() if i != cid and i not in cb.descendants(cid)]
        if target is None:
            T = THEME
            win = tk.Toplevel(self)
            win.title("Merge code")
            win.configure(bg=T["bg_panel"], padx=16, pady=14)
            self._label(win, f"All codings of “{c['name']}” (and its subcodes, which move along) go to:", font="small",
                        bg=T["bg_panel"]).pack(anchor="w")
            v = tk.StringVar(value="")
            ttk.Combobox(win, textvariable=v, values=[n.strip() for _, n in choices], state="readonly", width=40, font=self.f["small"]).pack(anchor="w", pady=8)
            bar = tk.Frame(win, bg=T["bg_panel"])
            bar.pack(fill=tk.X)
            go = lambda: (win.destroy(), self._cd_merge_dialog(cid, next((i for i, n in choices if n.strip() == v.get()), None)))
            self._tool(bar, "Cancel", win.destroy).pack(side=tk.RIGHT)
            self._tool(bar, "Merge", go, primary=True).pack(side=tk.RIGHT, padx=(0, 6))
            return win, {"var": v, "go": go}
        if cb.get(target) is None:
            return None
        n = self._cd_exact_counts(cb.path.parent).get(cid, 0)
        if not messagebox.askyesno("Merge code", f"Merge “{c['name']}” into “{cb.get(target)['name']}”?\n\n{n} coding(s) change code. Its "
                                   "subcodes move under the new code. Each changed transcript keeps a backup and can be undone "
                                   "when open; the codebook change is recorded in its log.", parent=self):
            return None
        self._cd_flush_active()
        moved = cod.recode_everywhere(cb.path.parent, {cid: target}, save_doc=self._cd_save_other)
        for child in cb.children(cid):
            cb.move(child["id"], target)
        memo = c.get("memo")
        cb.remove(cid)
        if memo:
            t = cb.get(target)
            cb.update(target, memo=((t.get("memo") or "") + f"\n[merged from {c['name']}] {memo}").strip())
        cb._log("merge", code=cid, into=target, codings=moved)
        cb.save()
        self._cd_after_project_change(f"Merged “{c['name']}” into “{cb.get(target)['name']}” ({moved} coding(s)).")
        return moved

    def _cd_delete_code(self, cid: Optional[str]):
        cb = self._cd_codebook()
        c = cb.get(cid) if cb and cid else None
        if c is None:
            return None
        ids = [cid] + cb.descendants(cid)
        counts = self._cd_exact_counts(cb.path.parent)
        n = sum(counts.get(i, 0) for i in ids)
        sub = f" and its {len(ids) - 1} subcode(s)" if len(ids) > 1 else ""
        if not messagebox.askyesno("Delete code", f"Delete “{c['name']}”{sub}?" + (f"\n\nIts {n} coding(s) are removed from the transcripts "
                                   "(each keeps a backup and can be undone when open)." if n else ""), parent=self):
            return None
        self._cd_flush_active()
        if True:  # every transcript is checked, whatever the (cached) count said
            from condense.core.transcript import TranscriptDocument as TD
            for p in cod.project_transcripts(cb.path.parent):
                try:
                    doc = TD.load(p)
                except Exception:
                    continue
                before = len(cod.codings(doc))
                doc.data["codings"] = [k for k in cod.codings(doc) if k["code"] not in ids]
                if len(cod.codings(doc)) < before:
                    doc.log_edit("uncode_code", codes=ids, codings=before - len(cod.codings(doc)))
                    self._cd_save_other(doc, f"Code “{c['name']}” deleted")
        cb.remove(cid)
        cb.save()
        self._cd_after_project_change(f"Deleted “{c['name']}”{sub}.")
        return ids

    def _cd_flush_active(self):
        """Pending text edits in the editor are saved before codes are changed in the files."""
        if self.active_doc is not None:
            self._autosave_edit(rerender=False)

    def _cd_after_project_change(self, message: str):
        self._cd_counts = None
        if self.active_doc is not None:
            self.active_doc = TranscriptDocument.load(self.active_doc.path)  # the file was changed on disk
            self._rerender()
        self._cd_refresh()
        self._append_log(message, "INFO")

    # ================================================================== the transcript with stripes
    def _cd_render(self, doc):
        t = self.cd_text
        self._cd["doc"] = doc
        same = self._cd.get("rendered_for") == str(doc.path)
        y = t.yview()[0] if same else 0.0
        top_word = self._cd_top_word() if same else None  # (time, y): stays where it is, as in Edit mode
        words: List[Tuple] = []  # (line, c0, c1, seg, wi, wid)
        line_words: Dict[int, List[int]] = {}
        roster = self._roster()
        colors = {n: SPEAKER_COLORS[i % len(SPEAKER_COLORS)] for i, n in enumerate(roster)}
        for n, col in colors.items():
            t.tag_config(f"SPKC{roster.index(n)}", foreground=col)
        cb = self._cd_codebook()
        res = cod.resolve(doc)
        moments = [r for r in res if r.get("kind") == "time"]
        eps = doc.episodes
        next_ep, mi = 0, 0
        last_spk = None

        out = textrender.Lines()  # built in Python, then only what changed goes to Tk
        put = out.put

        for i, seg in enumerate(doc.segments):
            if doc.is_segment_cut(i) or is_blank_text(seg.get("text")):
                continue
            s0 = float(seg.get("start", 0.0))
            while next_ep < len(eps) and eps[next_ep]["start"] <= s0 + 0.05:
                ep = eps[next_ep]
                next_ep += 1
                put(f"\n▶ {ep['type']} {ep.get('label') or ''}   {'≈ ' if ep.get('approx') else ''}{short_ts(ep['start'])[:-2]} – "
                    f"{short_ts(ep['end'])[:-2]}\n", "EP", self._episode_tag(ep["type"]))
                last_spk = None
            while mi < len(moments) and moments[mi]["start"] <= s0:
                self._cd_put_moment(put, moments[mi], cb)
                mi += 1
                last_spk = None
            spk = seg.get("speaker") or ""
            if spk != last_spk:
                put("" if out.empty else "\n")
                put(f"{spk or '—'}", "SPK", f"SPKC{roster.index(spk)}" if spk in roster else "TS")
                put(f"  {short_ts(s0)[:-2]}\n", "TS")
                last_spk = spk
            for k, w in enumerate(seg.get("words") or []):
                token = str(w.get("word", "")).strip()
                if not token:
                    continue
                line, col = out.line, out.col
                put(token)
                words.append((line, col, col + len(token), i, k, w.get("wid")))
                line_words.setdefault(line, []).append(len(words) - 1)
                put(" ")
        for r in moments[mi:]:
            self._cd_put_moment(put, r, cb)
        self._cd["shown_lines"] = textrender.show_lines(t, self._cd.get("shown_lines"), out.lines)
        for tag in ("sel", "KSEL", "PLAYING", "CODED"):  # as after a full redraw; painted again below where needed
            t.tag_remove(tag, "1.0", tk.END)
        self._cd.update(words=words, line_words=line_words, resolved=res, rendered_for=str(doc.path), starts=None)
        self._cd["wid_index"] = {w[5]: n for n, w in enumerate(words) if w[5]}
        self._cd["pos_index"] = {(w[3], w[4]): n for n, w in enumerate(words)}
        self._cd_mark_coded()
        t.yview_moveto(y)
        if top_word is not None:
            self._cd_place_word(*top_word)
        self._cd_header(doc, res)
        self._cd_fill_list()
        self._cd_fill_recent()
        self.after_idle(self._cd_draw_stripes)
        self._cd_draw_timeline()

    def _cd_header(self, doc, res: List[Dict]):
        moments = sum(1 for r in res if r.get("kind") == "time")
        n_orph = sum(1 for r in res if r.get("orphan"))
        self.lbl_cd_doc.config(text=f"{doc.base_name} · {len(res)} coding(s)" + (f" · {moments} coded by time" if moments else "")
                               + (f" · ⚠ {n_orph} coding(s) whose words were deleted" if n_orph else ""))

    def _cd_refresh_codings(self, doc):
        """After a change to codings of words (the text is the same): only what shows codings — highlights, the list,
        the stripes, the timeline. A 5-hour transcript's 40,000 words are not laid out again. Codings by time are in the
        text (◆ lines), so a change to one of them redraws everything."""
        if self._cd.get("doc") is not doc or self._cd.get("rendered_for") != str(doc.path):
            return self._cd_render(doc)
        res = cod.resolve(doc)
        self._cd["resolved"] = res
        for tag in ("sel", "KSEL"):  # as after a full redraw: the selection is coded, so it goes
            self.cd_text.tag_remove(tag, "1.0", tk.END)
        self._cd_mark_coded()
        self._cd_header(doc, res)
        self._cd_fill_list()
        self._cd_fill_recent()
        self.after_idle(self._cd_draw_stripes)
        self._cd_draw_timeline()
        return res

    def _cd_put_moment(self, put, r, cb):
        c = cb.get(r["code"]) if cb else None
        name = c["name"] if c else "?"
        tag = f"MC{r['id']}"
        self.cd_text.tag_config(tag, foreground=c["color"] if c else THEME["fg_dim"])
        self.cd_text.tag_bind(tag, "<Button-1>", lambda e, k=r["id"]: self._cd_select_coding(k))
        put(f"\n◆ {name}  {short_ts(r['start'])[:-2]} – {short_ts(r['end'])[:-2]}", "MOMENT", tag)
        put(f"   {r['memo']}" if r.get("memo") else "   (by time)", "MOMENT", tag)
        put("\n")

    def _cd_current(self):
        """The open transcript. If the Coding tab still shows an older copy of it (after undo or an edit in the
        Transcript tab), it is shown again first, so codings always go into the transcript as it is now."""
        doc = self.active_doc
        if doc is None:
            return None
        if self._cd.get("doc") is not doc:
            self._cd_render(doc)
        return doc

    def _cd_word_index(self, r: Dict) -> Optional[Tuple[int, int]]:
        if not r.get("words"):
            return None
        a, b = r["words"]
        pi = self._cd.get("pos_index") or {}
        ia, ib = pi.get(tuple(a)), pi.get(tuple(b))
        if ia is None or ib is None:  # an end word is cut or empty: the nearest shown words inside
            shown = [n for (seg, wi), n in pi.items() if tuple(a) <= (seg, wi) <= tuple(b)]
            if not shown:
                return None
            ia, ib = min(shown), max(shown)
        return ia, ib

    def _cd_mark_coded(self):
        t = self.cd_text
        t.tag_remove("CODED", "1.0", tk.END)
        words = self._cd["words"]
        for r in self._cd["resolved"]:
            span = self._cd_word_index(r)
            if span:
                a, b = words[span[0]], words[span[1]]
                t.tag_add("CODED", f"{a[0]}.{a[1]}", f"{b[0]}.{b[2]}")

    def _cd_draw_stripes(self):
        cv = self.__dict__.get("cd_stripes")
        if cv is None or self._cd.get("doc") is None:
            return
        cv.delete("all")
        t, words = self.cd_text, self._cd["words"]
        cb = self._cd_codebook()
        try:
            h = int(t.winfo_height())
            top_line = int(str(t.index("@0,0")).split(".")[0])
            bot_line = int(str(t.index(f"@0,{h}")).split(".")[0])
        except Exception:
            return  # not on screen yet
        cols: List[float] = []  # bottom y of the last stripe in each column
        items = []
        for r in self._cd["resolved"]:
            span = self._cd_word_index(r)
            if not span:
                continue
            a, b = words[span[0]], words[span[1]]
            if b[0] < top_line or a[0] > bot_line:
                continue
            ia = t.dlineinfo(f"{a[0]}.{a[1]}")
            ib = t.dlineinfo(f"{b[0]}.{b[1]}")
            ia = ia if isinstance(ia, tuple) else None
            ib = ib if isinstance(ib, tuple) else None
            y0 = ia[1] if ia else 0
            y1 = (ib[1] + ib[3]) if ib else h
            items.append((y0, y1, r))
        items.sort(key=lambda x: (x[0], -x[1]))
        self._cd["stripe_hits"] = []
        for y0, y1, r in items:
            col = next((k for k, bottom in enumerate(cols) if bottom < y0 - 1), None)
            if col is None:
                col = len(cols)
                cols.append(0)
            cols[col] = y1
            col = min(col, MAX_COLS - 1)
            x = 2 + col * (STRIPE_W + STRIPE_GAP)
            c = cb.get(r["code"]) if cb else None
            color = c["color"] if c else THEME["fg_dim"]
            sel = self._cd.get("sel") == r["id"]
            cv.create_rectangle(x, y0 + 1, x + STRIPE_W, y1 - 1, fill=color, outline=THEME["fg_primary"] if sel else color)
            self._cd["stripe_hits"].append((x, y0, x + STRIPE_W, y1, r["id"]))
        width = 4 + max(1, min(len(cols), MAX_COLS)) * (STRIPE_W + STRIPE_GAP)
        if int(cv.cget("width")) != width:
            cv.configure(width=width)

    def _cd_stripe_click(self, event):
        for x0, y0, x1, y1, kid in self._cd.get("stripe_hits") or []:
            if x0 - 2 <= event.x <= x1 + 2 and y0 <= event.y <= y1:
                return self._cd_select_coding(kid)
        return None

    def _cd_draw_timeline(self):
        return self._cdt_draw()

    def _cd_video_size(self):
        """The video column: a third of the tab, or more than half of it (for watching closely)."""
        if not self.__dict__.get("_video_panel_shown"):
            self.var_show_video.set(True)
            self._toggle_video_panel()
        try:
            panes = self.tx_paned.panes()
            width = int(self.tx_paned.winfo_width())
            big = not self.__dict__.get("_cd_video_big")
            x = int(width * (0.42 if big else 0.67))
            self.tx_paned.sash_place(len(panes) - 2, x, 0)
            self._cd_video_big = big
            self.after(120, lambda: self._video_resized(self._video_screen()))
        except Exception:
            return None
        return self._cd_video_big

    # ================================================================== selecting and coding
    def _cd_key(self, event):
        nav = {"Left", "Right", "Up", "Down", "Prior", "Next", "Home", "End", "Shift_L", "Shift_R", "Control_L", "Control_R"}
        mods = is_shortcut(event)
        if event.keysym in nav or (mods and event.keysym.lower() in ("c", "a")):
            return None  # moving and selecting with the keyboard, copy, select all
        if mods:
            return None  # other shortcuts (undo …) go to the app
        k = event.keysym
        if k in ("Return", "KP_Enter"):
            self._cd_apply(self._cd_selected_code())
        elif k in ("n", "N"):
            self._cd_new_code(parent=self._cd_selected_code(), apply=True)
        elif k in ("Delete", "BackSpace"):
            self._cd_remove(self._cd.get("sel"))
        elif k == "space":
            self._toggle_play()
        elif k.isdigit() and k != "0":
            rec = self._cd["recent"]
            if int(k) <= len(rec):
                code = rec[int(k) - 1]
                if self._cd_selection_words() is None and self._cdt_mark() is None and (
                        self.__dict__.get("playing") or code in (self.cdt.get("live") or {})):
                    self._cdt_live_toggle(code)  # while watching: start, and end, a coding at the playhead
                else:
                    self._cd_apply(code)
        else:
            self._cdt_key(k)
        return "break"

    def _cd_selection_words(self) -> Optional[Tuple[int, int]]:
        rng = self.cd_text.tag_ranges("sel")
        if not rng:
            return None
        a, b = str(rng[0]), str(rng[-1])
        la, ca = map(int, a.split("."))
        lb, cb_ = map(int, b.split("."))
        words = self._cd["words"]
        inside = [n for n, (line, c0, c1, *_r) in enumerate(words) if (line, c1) > (la, ca) and (line, c0) < (lb, cb_)]
        return (inside[0], inside[-1]) if inside else None

    def _cd_apply(self, code_id: Optional[str]):
        doc = self._cd_current()
        cb = self._cd_codebook()
        if doc is None or cb is None:
            return None
        if not code_id or cb.get(code_id) is None:
            self.lbl_cd_doc.config(text="Choose a code in the codebook first (or press N for a new one).")
            return None
        span = self._cd_selection_words()
        if span is None and self._cdt_mark() is not None:
            return self._cdt_code_mark(code_id)  # the range marked on the timeline: by time
        if span is None:
            self.lbl_cd_doc.config(text="Select the words to code first (drag over them), or mark a range on the timeline.")
            return None
        words = self._cd["words"]
        a, b = words[span[0]], words[span[1]]
        wa = doc.segments[a[3]]["words"][a[4]]
        wb = doc.segments[b[3]]["words"][b[4]]
        kid = cod.add_coding(doc, code_id, float(wa["start"]), float(wb["end"]), wa["wid"], wb["wid"])
        self._cd_commit(f"Coded “{cb.get(code_id)['name']}”: {short_ts(float(wa['start']))[:-2]}")
        self._cd_count(code_id, +1)
        self._cd_use_recent(code_id)
        self._cd_refresh_codings(doc)
        self._cd_fill_codebook()
        self._cd_select_coding(kid)
        return kid

    def _cd_time_dialog(self, start: Optional[float] = None, end: Optional[float] = None, coding_id: Optional[str] = None):
        """A moment without speech (interaction with the materials, a gesture …): code, time and what happens."""
        doc = self._cd_current()
        cb = self._cd_codebook()
        if doc is None or cb is None:
            return None
        T = THEME
        existing = cod.get_coding(doc, coding_id) if coding_id else None
        if start is None:
            pos = self._current_pos()
            start, end = (existing["start"], existing["end"]) if existing else (pos, pos + 10)
        choices = self._cd_code_choices()
        win = tk.Toplevel(self)
        win.title("Code by time")
        win.configure(bg=T["bg_panel"], padx=16, pady=14)
        self._label(win, "Code a stretch of the recording by time — what happens without words (materials, devices, gestures), "
                         "or before the transcript is checked. It shows in the transcript at its time, with your description.", font="small", fg=T["fg_secondary"],
                    bg=T["bg_panel"], wraplength=460, justify=tk.LEFT).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        v_start, v_end = tk.StringVar(value=short_ts(start)), tk.StringVar(value=short_ts(end))
        sel_name = next((n.strip() for i, n in choices if i == ((existing or {}).get("code") or self._cd_selected_code())), "")
        v_code = tk.StringVar(value=sel_name)
        self._label(win, "From", font="small", fg=T["fg_secondary"], bg=T["bg_panel"]).grid(row=1, column=0, sticky="w")
        self._entry(win, v_start, font="small", width=12).grid(row=1, column=1, sticky="w")
        self._label(win, "To", font="small", fg=T["fg_secondary"], bg=T["bg_panel"]).grid(row=2, column=0, sticky="w")
        self._entry(win, v_end, font="small", width=12).grid(row=2, column=1, sticky="w")
        self._tool(win, "▶ Play", lambda: (eplib.parse_time(v_start.get()) is not None and self._player_start(
            eplib.parse_time(v_start.get()), max(1.0, (eplib.parse_time(v_end.get()) or 0) - eplib.parse_time(v_start.get()))))).grid(row=1, column=2, padx=(8, 0))
        self._label(win, "Code", font="small", fg=T["fg_secondary"], bg=T["bg_panel"]).grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(win, textvariable=v_code, values=[n.strip() for _, n in choices], state="readonly", width=34,
                     font=self.f["small"]).grid(row=3, column=1, columnspan=2, sticky="w", pady=(6, 0))
        self._label(win, "What happens", font="small", fg=T["fg_secondary"], bg=T["bg_panel"]).grid(row=4, column=0, sticky="nw", pady=(6, 0))
        memo = tk.Text(win, height=4, width=48, wrap=tk.WORD, font=self.f["small"], bg=T["bg_input"], fg=T["fg_primary"],
                       insertbackground=T["fg_primary"], relief=tk.FLAT, highlightthickness=1, highlightbackground=T["border"])
        memo.insert("1.0", (existing or {}).get("memo", ""))
        memo.grid(row=4, column=1, columnspan=2, sticky="we", pady=(6, 0))
        lbl = self._label(win, "", font="small", fg=T["warn"], bg=T["bg_panel"])
        lbl.grid(row=5, column=0, columnspan=3, sticky="w")

        def save():
            a, b = eplib.parse_time(v_start.get()), eplib.parse_time(v_end.get())
            code = next((i for i, n in choices if n.strip() == v_code.get()), None)
            if a is None or b is None or b <= a:
                lbl.config(text="From and to as h:mm:ss, the end after the start.")
                return None
            if code is None:
                lbl.config(text="Choose a code (or create one in the codebook first).")
                return None
            text = memo.get("1.0", "end-1c").strip()
            if existing:
                existing["start"], existing["end"] = round(a, 3), round(b, 3)
                cod.update_coding(doc, existing["id"], code=code, memo=text)
                kid = existing["id"]
            else:
                kid = cod.add_coding(doc, code, a, b, memo=text)
                self._cd_count(code, +1)
            self._cd_commit(f"Moment coded “{cb.get(code)['name']}” {short_ts(a)[:-2]}–{short_ts(b)[:-2]}")
            self._cd_use_recent(code)
            win.destroy()
            self._cd_render(doc)
            self._cd_fill_codebook()
            self._cd_select_coding(kid)
            return kid

        bar = tk.Frame(win, bg=T["bg_panel"])
        bar.grid(row=6, column=0, columnspan=3, sticky="e", pady=(10, 0))
        self._tool(bar, "Cancel", win.destroy).pack(side=tk.LEFT, padx=(0, 6))
        self._tool(bar, "Save", save, primary=True).pack(side=tk.LEFT)
        win.bind("<Escape>", lambda e: (win.destroy(), "break")[-1])
        return win, {"start": v_start, "end": v_end, "code": v_code, "memo": memo, "save": save, "error": lbl}

    def _cd_commit(self, message: str):
        """Codings don't change the exports: save the transcript with a backup and an undo step, nothing else."""
        doc = self.active_doc
        if doc is None:
            return
        try:
            previous = doc.saved_text() if doc.path.exists() else None
            doc.save(backup=True)
        except Exception as exc:
            messagebox.showerror("Could not save transcript", str(exc), parent=self)
            return
        if previous is not None:
            self._push_undo(doc.path, message, previous)
        self.lbl_status.config(text=message)
        self._sync_linked_clips(doc)  # codings and comments in a linked interview go into its clip too

    def _cd_count(self, code_id: str, delta: int):
        counts = self.__dict__.get("_cd_counts")
        if counts is None:
            counts = self._cd_counts = {}
        counts[code_id] = max(0, counts.get(code_id, 0) + delta)

    def _cd_use_recent(self, code_id: str):
        rec = [c for c in self._cd["recent"] if c != code_id]
        self._cd["recent"] = ([code_id] + rec)[:9]
        self._cd_fill_recent()

    def _cd_fill_recent(self):
        fr = self.cd_bar
        for w in self._cd_recent_items:
            fr.remove(w)
        self._cd_recent_items = []
        cb = self._cd_codebook()
        rec = [c for c in self._cd["recent"] if cb and cb.get(c)]
        self._cd["recent"] = rec
        if not rec:
            return
        sep = self._separator(fr)
        fr.add(sep)
        self._cd_recent_items.append(sep)
        for k, cid in enumerate(rec):
            c = cb.get(cid)
            # no outline: the code's name in its colour, the key before it
            chip = tk.Label(fr, text=f"{k + 1}  {c['name']}", font=self.f["small_bold"], padx=8, pady=3, cursor="hand2", bg=THEME["bg_panel"],
                            fg=c["color"], highlightthickness=0)
            chip.bind("<Button-1>", lambda e, cid=cid: self._cd_apply(cid))
            chip.condense_invoke = lambda cid=cid: self._cd_apply(cid)
            self._tip(chip, f"Code the selection with “{c['name']}”  {k + 1}")
            fr.add(chip)
            self._cd_recent_items.append(chip)

    # ================================================================== codings: select, list, change
    def _cd_click(self, event):
        """A click (not a drag) on coded words selects the innermost coding there."""
        t = self.cd_text
        if t.tag_ranges("sel"):
            return None  # a selection was made: that's for coding
        idx = t.index(f"@{event.x},{event.y}")
        line, col = map(int, idx.split("."))
        ws = self._cd["line_words"].get(line, [])
        n = next((n for n in ws if self._cd["words"][n][1] <= col <= self._cd["words"][n][2]), None)
        if n is None:
            return None
        self._cd["word"] = n  # where you are: ⌃1–9 / Alt+1–9 give this word's segment a speaker, ⌘E edits it
        hits = []
        for r in self._cd["resolved"]:
            span = self._cd_word_index(r)
            if span and span[0] <= n <= span[1]:
                hits.append((span[1] - span[0], r["id"]))
        if hits:
            return self._cd_select_coding(min(hits)[1])
        self._cd_select_coding(None)
        return None

    def _cd_select_coding(self, kid: Optional[str], from_list: bool = False):
        self._cd["sel"] = kid
        t = self.cd_text
        t.tag_remove("KSEL", "1.0", tk.END)
        r = next((r for r in self._cd["resolved"] if r["id"] == kid), None) if kid else None
        if r is not None:
            span = self._cd_word_index(r)
            if span:
                a, b = self._cd["words"][span[0]], self._cd["words"][span[1]]
                t.tag_add("KSEL", f"{a[0]}.{a[1]}", f"{b[0]}.{b[2]}")
                t.see(f"{a[0]}.{a[1]}")
            elif r.get("kind") == "time":
                rng = t.tag_ranges(f"MC{kid}")
                if rng:
                    t.tag_add("KSEL", rng[0], rng[-1])
                    t.see(rng[0])
            if not from_list and self.cd_list.exists(kid):
                self.cd_list.selection_set(kid)
                self.cd_list.see(kid)
        self._cd_draw_stripes()
        return kid

    def _cd_list_selected(self) -> Optional[str]:
        sel = self.cd_list.selection()
        return sel[0] if sel else self._cd.get("sel")

    def _cd_fill_list(self):
        lst = self.__dict__.get("cd_list")
        doc = self._cd.get("doc") if self.__dict__.get("_cd") else None
        if lst is None:
            return
        for iid in lst.get_children():
            lst.delete(iid)
        if doc is None:
            return
        cb = self._cd_codebook()
        only = self._cd_selected_code() if self.var_cd_only.get() else None
        keep = set([only] + cb.descendants(only)) if only and cb else None
        n = 0
        for r in self._cd["resolved"]:
            if keep is not None and r["code"] not in keep:
                continue
            c = cb.get(r["code"]) if cb else None
            if r["code"] == cod.COMMENT:  # a comment: what you wrote first, then what it is about
                about = "" if r.get("kind") == "time" or r.get("orphan") else f"   — “{cod.coded_text(doc, r)}”"
                text = "✎ " + (r.get("memo") or "").replace("\n", " ⏎ ") + about
            else:
                text = ("◆ " + (r.get("memo") or "(coded by time)")) if r.get("kind") == "time" else (
                    "⚠ (its words were deleted)" if r.get("orphan") else cod.coded_text(doc, r))
                if r.get("memo") and r.get("kind") != "time":
                    text += f"   ✎ {r['memo']}"
            text = text.replace("\n", " ⏎ ")
            tag = f"col{c['color']}" if c else ""
            if c:
                lst.tag_configure(tag, foreground=c["color"])
            lst.insert("", tk.END, iid=r["id"], values=(short_ts(r["start"])[:-2], cb.path_name(r["code"]) if c else "?",
                                                        ", ".join(cod.speakers_of(doc, r)), text[:300]), tags=(tag,) if tag else ())
            n += 1
        self.lbl_cd_list.config(text=f"Codings ({n})")

    def _cd_remove(self, kid: Optional[str]):
        doc = self._cd_current()
        if doc is None or not kid:
            return False
        c = cod.get_coding(doc, kid)
        if c is None or not cod.remove_coding(doc, kid):
            return False
        self._cd_count(c["code"], -1)
        self._cd_commit("Coding removed")
        self._cd["sel"] = None
        self._cd_render(doc) if c.get("kind") == "time" else self._cd_refresh_codings(doc)
        self._cd_fill_codebook()
        return True

    def _cd_change_code(self, kid: Optional[str], code_id: Optional[str] = None):
        """Give a coding another code — also how a code that grew too big is split: make the new code, then move the
        codings that belong to it, one by one from the list."""
        doc, cb = self._cd_current(), self._cd_codebook()
        c = cod.get_coding(doc, kid) if doc is not None and kid else None
        if c is None or cb is None:
            return None
        if c.get("kind") == "time" and code_id is None:
            return self._cd_time_dialog(coding_id=kid)
        if code_id is None:
            choices = self._cd_code_choices()
            T = THEME
            win = tk.Toplevel(self)
            win.title("Change code")
            win.configure(bg=T["bg_panel"], padx=16, pady=14)
            v = tk.StringVar(value=next((n.strip() for i, n in choices if i == c["code"]), ""))
            ttk.Combobox(win, textvariable=v, values=[n.strip() for _, n in choices], state="readonly", width=40, font=self.f["small"]).pack(anchor="w")
            go = lambda: (win.destroy(), self._cd_change_code(kid, next((i for i, n in choices if n.strip() == v.get()), None)))
            self._tool(win, "Change", go, primary=True).pack(anchor="e", pady=(10, 0))
            return win, {"var": v, "go": go}
        if cb.get(code_id) is None or not cod.update_coding(doc, kid, code=code_id):
            return None
        self._cd_count(c["code"], -1)
        self._cd_count(code_id, +1)
        self._cd_commit(f"Coding moved to “{cb.get(code_id)['name']}”")
        self._cd_render(doc) if c.get("kind") == "time" else self._cd_refresh_codings(doc)
        self._cd_fill_codebook()
        self._cd_select_coding(kid)
        return kid

    def _cd_memo(self, kid: Optional[str], text: Optional[str] = None):
        doc = self._cd_current()
        c = cod.get_coding(doc, kid) if doc is not None and kid else None
        if c is None:
            return None
        if c.get("code") == cod.COMMENT and text is None:
            return self._comment_dialog(kid)
        if c.get("kind") == "time" and text is None:
            return self._cd_time_dialog(coding_id=kid)
        if text is None:
            text = simpledialog.askstring("Memo", "Memo for this coding:", initialvalue=c.get("memo", ""), parent=self)
            if text is None:
                return None
        if cod.update_coding(doc, kid, memo=text):
            self._cd_commit("Coding memo changed")
            self._cd_render(doc)
            self._cd_select_coding(kid)
        return kid

    def _cd_text_menu(self, event):
        m = PopupMenu(self)
        sel = self._cd_selection_words()
        code = self._cd_selected_code()
        cb = self._cd_codebook()
        if sel and code and cb and cb.get(code):
            m.add_command(label=f"Code with “{cb.get(code)['name']}”", command=lambda: self._cd_apply(code))
        if sel:
            m.add_command(label="New code from selection…", command=lambda: self._cd_new_code(parent=code, apply=True))
            for k, cid in enumerate(self._cd["recent"][:9]):
                if cb and cb.get(cid):
                    m.add_command(label=f"{k + 1}  {cb.get(cid)['name']}", command=lambda cid=cid: self._cd_apply(cid))
        m.add_command(label="✎ Comment on this…  (M)", command=lambda: self._comment_dialog())
        kid = self._cd.get("sel")
        c = cod.get_coding(self.active_doc, kid) if kid and self.active_doc is not None else None
        if c is not None and c.get("code") == cod.COMMENT:
            m.add_separator()
            m.add_command(label="Edit this comment…", command=lambda: self._comment_dialog(kid))
            m.add_command(label="Delete this comment", command=lambda: self._cd_remove(kid))
        elif kid:
            m.add_separator()
            m.add_command(label="Memo for this coding…", command=lambda: self._cd_memo(kid))
            m.add_command(label="Change its code…", command=lambda: self._cd_change_code(kid))
            m.add_command(label="Delete this coding", command=lambda: self._cd_remove(kid))
        m.add_separator()
        m.add_command(label="Code by time…", command=lambda: self._cd_time_dialog(*(self._cdt_mark() or (None, None))))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return m

    # ================================================================== playing
    def _cd_play_word(self, event):
        t = self.cd_text
        line, col = map(int, t.index(f"@{event.x},{event.y}").split("."))
        n = next((n for n in self._cd["line_words"].get(line, []) if self._cd["words"][n][1] <= col <= self._cd["words"][n][2]), None)
        if n is not None:
            w = self._cd["words"][n]
            self._player_start(float(self._cd["doc"].segments[w[3]]["words"][w[4]]["start"]))
        return "break"

    def _cd_play_selection(self):
        span = self._cd_selection_words()
        doc = self._cd_current()
        if not span or doc is None:
            r = next((r for r in self._cd["resolved"] if r["id"] == self._cd.get("sel")), None)
            if r is not None:
                return self._cd_play_coding(r["id"])
            return None
        a, b = self._cd["words"][span[0]], self._cd["words"][span[1]]
        t0 = float(doc.segments[a[3]]["words"][a[4]]["start"])
        t1 = float(doc.segments[b[3]]["words"][b[4]]["end"])
        self._player_start(t0, t1 - t0 + 0.3)
        return t0

    def _cd_play_coding(self, kid: Optional[str]):
        r = next((r for r in self._cd["resolved"] if r["id"] == kid), None)
        if r is None:
            return None
        self._cd_select_coding(kid)
        self._player_start(max(0.0, r["start"] - 0.3), r["end"] - r["start"] + 0.6)
        return r["start"]

    def _cd_follow(self, pos: float):
        """While playing: the word being spoken, in the Coding tab too."""
        if self.__dict__.get("_cd") is None or self._cd.get("doc") is None or not self._cd_visible():
            return
        doc, words = self._cd["doc"], self._cd["words"]
        if not words:
            return
        starts = self._cd.get("starts")
        if starts is None or len(starts) != len(words):
            starts = self._cd["starts"] = [float(doc.segments[w[3]]["words"][w[4]]["start"]) for w in words]
        n = max(0, bisect.bisect_right(starts, pos) - 1)
        w = words[n]
        t = self.cd_text
        t.tag_remove("PLAYING", "1.0", tk.END)
        t.tag_add("PLAYING", f"{w[0]}.{w[1]}", f"{w[0]}.{w[2]}")
        if self.var_follow.get():
            t.see(f"{w[0]}.{w[1]}")
