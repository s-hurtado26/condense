"""Transcript editor: the transcript view and the segment editor. Navigation, history and review marks are in
navigation.py, history.py and review_marks.py."""
from condense.core import cuts as cutlib
from condense.core import episodes as eplib
from condense.gui import textrender
from condense.gui._common import *  # noqa: F401,F403


class EditorMixin:
    # ------------------------------------------------------------------ transcript editor
    PLAYER_LATENCY_S = 0.25  # ffplay start-up delay; keeps the follow-along highlight in sync
    SHOW_FILTERS = ["All segments", "Uncertain", "Not checked", "With notes", "Cut"]
    EDIT_HINT = "Unchanged words keep their timing; corrected words are timed within the ones they replace. Every change is logged."

    def _build_preview_tab(self):
        T = THEME
        tab = self.tab_preview

        # ---- the mode (Code / Edit, ⌘E), then the toolbar of that mode ----
        toprow = tk.Frame(tab, bg=T["bg_panel"])
        toprow.pack(fill=tk.X)
        switch = tk.Frame(toprow, bg=T["bg_panel"])
        switch.pack(side=tk.LEFT, anchor="n", padx=(5, 2), pady=5)
        self.btn_mode_code = self._tool(switch, "Code", lambda: self._set_tx_mode("code"))
        self.btn_mode_edit = self._tool(switch, "Edit", lambda: self._set_tx_mode("edit"))
        for b in (self.btn_mode_code, self.btn_mode_edit):
            b.configure(width=6)  # the same width: a switch, whichever is on
        self.btn_mode_code.pack(side=tk.LEFT)
        self.btn_mode_edit.pack(side=tk.LEFT)  # side by side: one switch
        self.mode_holder = tk.Frame(toprow, bg=T["bg_panel"])
        self.mode_holder.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.tx_mode = "edit"
        # ---- the Edit toolbar: what you use while reviewing stays visible; the rest is one click away in a menu ----
        bar = self._flow(self.mode_holder, padx=4, pady=5, bg=T["bg_panel"], one_line=True)  # one row; the rest in ⋯
        bar.pack(fill=tk.X, pady=5)
        self.tx_bar = bar
        bar.add(self._dropdown(bar, "Transcript ▾", [
            ("Open…", self._open_transcript),
            ("-",),
            ("Speakers…", self._show_speakers_dialog),
            ("Who is who? (name the detected speakers)…", self._match_speakers_dialog),
            ("Detect speakers…", self._rediarize_dialog),
            ("-",),
            ("Episodes (interviews, phases)…", self._episodes_dialog),
            ("Find interview clips in this recording…", self._link_clips_dialog),
            ("Find untranscribed stretches…", self._gaps_dialog),
            ("Export trimmed video & transcript…", self._export_trimmed_dialog),
            ("Video with subtitles…", self._subtitles_dialog),
            ("Copy for MAXQDA (H.264 MP4)…", self._maxqda_copy_dialog),
            ("-",),
            ("✎ Comment on the selection…  (⌘K)" if IS_MAC else "✎ Comment on the selection…  (Ctrl+Shift+K)", self._comment_dialog),
            ("Commentary over time (spreadsheet)…", self._commentary_dialog),
            ("-",),
            ("Mark whole transcript checked (100 %)", lambda: self.active_doc is not None and self._mark_transcripts_checked([self.active_doc.path], True)),
            ("Mark whole transcript not checked", lambda: self.active_doc is not None and self._mark_transcripts_checked([self.active_doc.path], False)),
            ("Restore all cuts…", self._restore_all_cuts),
        ]))
        bar.add(self._separator(bar))
        self.var_view_mode = tk.StringVar(value="Paragraphs")
        self._persist["view_mode"] = self.var_view_mode
        self._combo_values["view_mode"] = ["Paragraphs", "Segments"]
        cb = ttk.Combobox(bar, textvariable=self.var_view_mode, values=["Paragraphs", "Segments"], state="readonly", width=10, font=self.f["small"])
        cb.bind("<<ComboboxSelected>>", lambda e: (self._rerender(), self._back_to_transcript()))
        bar.add(cb)
        bar.add(self._label(bar, "Show", font="small", fg=T["fg_secondary"], bg=T["bg_panel"]))
        self.var_show_filter = tk.StringVar(value="All segments")
        cmb_show = ttk.Combobox(bar, textvariable=self.var_show_filter, state="readonly", width=15, font=self.f["small"],
                                values=self.SHOW_FILTERS)
        self.cmb_show = cmb_show
        cmb_show.bind("<<ComboboxSelected>>", lambda e: (self._autosave_edit(rerender=False), self._rerender(), self._back_to_transcript()))
        bar.add(cmb_show)
        bar.add(self._separator(bar))
        bar.add(self._tool(bar, "Find", self._toggle_find, tip="Find and replace  ⌘F"))
        bar.add(self._tool(bar, "◀", lambda: self._jump_low_conf(-1), tip="Previous uncertain word  ←"))
        bar.add(self._label(bar, "Uncertain", font="small", fg=T["fg_secondary"], bg=T["bg_panel"]))
        bar.add(self._tool(bar, "▶", lambda: self._jump_low_conf(+1), tip="Next uncertain word  →"))
        bar.add(self._separator(bar))
        bar.add(self._tool(bar, "✂ Cut", self._toggle_cut, tip="Cut the selection out of the analysis (or restore it)  X"))
        bar.add(self._tool(bar, "Episodes…", self._episodes_dialog))
        self.var_autoplay = tk.BooleanVar(value=True)
        self._persist["autoplay"] = self.var_autoplay
        self._persist["show_pct"] = self.var_show_pct

        # ---- player: the controls; its options in one menu ----
        player = self._flow(tab, padx=5, pady=5, bg=T["bg_card"])
        player.pack(fill=tk.X, pady=(4, 0), ipady=3)
        # back · play · forward, by a step chosen once (5–30 s); ⌘[ ⌘] jump one step, with ⇧ three
        step = self._skip_step()
        transport = tk.Frame(player, bg=T["bg_card"])
        self.btn_back = self._tool(transport, f"⟲ {step} s", lambda: self._skip(-1), tip="Back one step  ⌘[   (three: ⇧⌘[)")
        self.btn_play = ttk.Button(transport, text="▶", style=rounded.style_for(transport, "Play"), command=self._toggle_play)
        self._tip(self.btn_play, "Play / pause  Space")
        self._no_focus(self.btn_play)
        self.btn_fwd = self._tool(transport, f"{step} s ⟳", lambda: self._skip(+1), tip="Forward one step  ⌘]   (three: ⇧⌘])")
        for b in (self.btn_back, self.btn_play, self.btn_fwd):
            b.pack(side=tk.LEFT, padx=(0, 2))
        player.add(transport)
        self.btn_step = self._dropdown(player, f"Step {step} s ▾", [(f"{s} seconds", lambda s=s: self._set_skip_step(s))
                                                                   for s in self.SKIP_STEPS])
        player.add(self.btn_step)
        # speed: a slider, and the value can be typed (1.3, 1.3×, 130%)
        self.var_speed = tk.StringVar(value="1×")
        self._persist["speed"] = self.var_speed
        self.var_speed_num = tk.DoubleVar(value=1.0)
        speed = tk.Frame(player, bg=T["bg_card"])
        self.speed_scale = ttk.Scale(speed, from_=self.SPEED_MIN, to=self.SPEED_SLIDER_MAX, orient=tk.HORIZONTAL, length=110,
                                     variable=self.var_speed_num, command=self._on_speed_slide)
        self.speed_scale.pack(side=tk.LEFT, padx=(2, 4))
        self._no_focus(self.speed_scale)
        self.speed_scale.bind("<ButtonRelease-1>", lambda e: self._speed_apply_now())
        self.speed_entry = self._entry(speed, self.var_speed, width=6, font="small")
        self.speed_entry.configure(justify=tk.CENTER)
        self.speed_entry.pack(side=tk.LEFT)
        for seq in ("<Return>", "<KP_Enter>", "<FocusOut>"):
            self.speed_entry.bind(seq, lambda e: self._speed_typed())
        for seq in ("<Return>", "<KP_Enter>", "<Escape>"):  # done typing: back to the transcript
            self.speed_entry.bind(seq, self._back_to_transcript, add="+")
        self.var_speed.trace_add("write", lambda *a: self._speed_sync_slider())
        player.add(speed)
        self.lbl_time = self._label(player, "0:00:00 / 0:00:00", font="mono_small", fg=T["fg_secondary"])
        player.add(self.lbl_time)
        self.var_follow = tk.BooleanVar(value=True)
        self._persist["follow"] = self.var_follow
        self.var_skip_cuts = tk.BooleanVar(value=True)
        self._persist["skip_cuts"] = self.var_skip_cuts
        self._persist["show_video"] = self.var_show_video
        self.var_preview_original = tk.BooleanVar(value=False)  # the preview decodes the original recording (sharper)
        self._persist["preview_original"] = self.var_preview_original
        self.var_preview_original.trace_add("write", lambda *a: self.after_idle(self._video_refresh))
        self.var_show_video.trace_add("write", lambda *a: self.after_idle(self._toggle_video_panel))
        player.add(self._dropdown(player, "Playback ▾", [
            ("check", "Follow the text while playing", self.var_follow),
            ("check", "Play a snippet when jumping to a segment", self.var_autoplay),
            ("check", "Skip cut parts", self.var_skip_cuts),
            ("check", "Show the video", self.var_show_video),
            ("Video in its own window (⤢)", self._video_pop_out),
            ("check", "Sharper preview: from the original recording", self.var_preview_original),
            ("Go to time…", self._goto_time_dialog),
            ("Link a video…", self._link_video_dialog),
            ("Unlink the video", self._unlink_video),
            ("-",),
            ("Open in QuickTime ↗" if IS_MAC_PLATFORM else "Open in a video player ↗", self._open_in_quicktime),
            ("Keyboard shortcuts…", self._show_shortcuts),
        ]))
        # the clicked word — “word”  time · p 92 % — at the end of the player's row, where there is room for it
        self.lbl_word = self._label(player, "", font="small", fg=T["fg_dim"], anchor="w")
        player.add(self.lbl_word)

        info = tk.Frame(tab, bg=T["bg_panel"])
        info.pack(fill=tk.X, pady=(6, 4))
        # Fixed heights for the lines that change on every ↑/↓: if they grew or shrank, the transcript would jump.
        top = tk.Frame(info, bg=T["bg_panel"])
        top.pack(fill=tk.X)
        # the transcript's text size: a small "Aa 100%" — click for larger / smaller (also View ▸, ⌘⌥+ / ⌘⌥−)
        size = tk.Frame(top, bg=T["bg_panel"], cursor="hand2")
        size.pack(side=tk.RIGHT)
        aa = self._label(size, "Aa", font="small_bold", fg=T["fg_dim"], bg=T["bg_panel"])
        aa.pack(side=tk.LEFT, padx=(8, 3))
        self.var_text_size = tk.DoubleVar(value=self.transcript_scale * 100)
        self.lbl_text_size = self._label(size, f"{self.transcript_scale * 100:.0f}%", font="small", fg=T["fg_dim"], bg=T["bg_panel"], width=5)
        self.lbl_text_size.pack(side=tk.LEFT)
        size_menu = PopupMenu(self)
        size_menu.add_command(label="Larger transcript text", command=lambda: self._transcript_size_step(+1),
                              accelerator="⌘⌥+" if IS_MAC else "Ctrl+Alt++")
        size_menu.add_command(label="Smaller transcript text", command=lambda: self._transcript_size_step(-1),
                              accelerator="⌘⌥−" if IS_MAC else "Ctrl+Alt+−")
        size_menu.add_command(label="Default size", command=lambda: self._set_transcript_size(1.0))
        for w in (size, aa, self.lbl_text_size):
            w.bind("<Button-1>", lambda e: size_menu.tk_popup(e.x_root, e.y_root))
        self.lbl_ci_summary = self._label(top, kbd("No transcript open. Select a finished job or use Open… (⇧⌘O)."), font="small",
                                          fg=T["fg_secondary"], bg=T["bg_panel"], height=1, anchor="w", justify=tk.LEFT)
        self.lbl_ci_summary.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.tx_paned = tk.PanedWindow(tab, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.FLAT, bd=0, bg=T["bg_panel"], showhandle=False)
        self.tx_paned.pack(fill=tk.BOTH, expand=True)
        self._build_find_bar(tab, before=self.tx_paned)
        frame = tk.Frame(self.tx_paned, bg=T["bg_panel"])
        self.tx_paned.add(frame, minsize=300, stretch="always")
        self.tx_text_frame = frame  # Edit mode; Code mode shows the codebook and the coding view here
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        # --- segment editor: under the transcript, as wide as it (the video beside them runs down to the timeline) ---
        ep = tk.Frame(frame, bg=T["bg_card"], padx=10, pady=8)
        ep.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.tx_edit_panel = ep  # Edit mode only (Code mode takes the whole column away)
        # one calm row: the segment on the left; ✓, the segmentation tools, ⋯ and Save & next on the right. The
        # speaker is chosen with the chips below (they show it too), Save and the rest are in ⋯ (⌘S still saves).
        head = tk.Frame(ep, bg=T["bg_card"])
        head.pack(fill=tk.X)
        # as wide as its text; the buttons are right-aligned, so they stay where they are while ↑/↓ change it
        self.lbl_edit_title = self._label(head, "Click a word to edit it", font="section", anchor="w")
        self.lbl_edit_title.pack(side=tk.LEFT)
        self.var_seg_speaker = tk.StringVar(value="")
        self.cmb_seg_speaker = ttk.Combobox(head, textvariable=self.var_seg_speaker, values=[], width=16, font=self.f["small"])  # (not shown)
        more = PopupMenu(self)
        more.add_command(label="Save", command=self._save_segment_edit, accelerator=kbd("⌘S"))
        more.add_command(label="Note…", command=self._open_note, accelerator="N")
        more.add_command(label="Revert my changes", command=self._revert_segment_edit)
        more.add_separator()
        more.add_command(label="Re-transcribe this passage…", command=self._retranscribe_dialog)
        markers = PopupMenu(self, parent=more)
        for label, text, _k in MARKERS:
            markers.add_command(label=label, command=lambda t=text: self._insert_marker(t))
        more.add_cascade(label="Insert marker", menu=markers)
        self.seg_more_menu = more
        row = self._flow(head, padx=5, pady=4, bg=T["bg_card"], one_line=True, align="right", extra_menu=lambda: self.seg_more_menu,
                         more_before_last=True)
        row.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 0))
        self.edit_row = row
        self.btn_checked = ttk.Button(row, text="✓", style=rounded.style_for(row, "Check"), command=self._toggle_checked)
        self.btn_checked.condense_keep = True
        self._no_focus(self.btn_checked)
        self._tip(self.btn_checked, lambda: ("Checked — click to unmark" if rounded.base_style(str(self.btn_checked.cget("style"))) == "CheckOn.TButton"
                                             else "Mark checked") + "  C")
        row.add(self.btn_checked)
        # the segmentation tools are used all the time while reviewing: one click, and one key in the transcript
        row.add(self._tool(row, "Split", self._split_at_current_word, tip="Split before the selected word  S"))
        row.add(self._tool(row, "Merge", self._merge_with_next, tip="Merge with the next segment  M"))
        row.add(self._tool(row, "Insert", self._insert_segment_dialog, tip="Insert a segment  I"))
        row.add(self._tool(row, "Delete", self._delete_segment, tip="Delete this segment (asks first)  " + ("⌫" if IS_MAC else "Del")))
        save_next = self._tool(row, "✓ Save & next", self._check_and_next, primary=True, tip="Save, mark checked, open the next segment  ⌘↩")
        save_next.condense_keep = True
        row.add(save_next)
        self.btn_save_next = save_next
        self.edit_text = tk.Text(ep, height=3, wrap=tk.WORD, font=self.f["transcript"], bg=T["bg_input"], fg=T["fg_primary"],
                                 insertbackground=T["fg_primary"], relief=tk.FLAT, highlightthickness=1, highlightbackground=T["border"],
                                 highlightcolor=T["accent"], padx=8, pady=6, undo=True)
        self.spk_chips = self._flow(ep, padx=4, pady=4, bg=T["bg_card"])
        self.spk_chips.pack(fill=tk.X, pady=(6, 0))
        self.edit_text.pack(fill=tk.X, pady=(6, 2))
        for seq in (f"<{MOD}-Return>", f"<{MOD}-KP_Enter>"):  # main and number-pad Enter
            self.edit_text.bind(seq, lambda e: (self._check_and_next(), "break")[-1])
        for d in range(1, 10):
            self.bind_all(f"<{EDIT_MOD}-Key-{d}>", lambda e, d=d: (self._assign_speaker_number(d), "break")[-1])
        # the note: only there when the segment has one, or when asked for (N, or ⋯ ▸ Note…)
        extras = tk.Frame(ep, bg=T["bg_card"])
        extras.pack(fill=tk.X)
        note_row = tk.Frame(extras, bg=T["bg_card"])
        self.note_row = note_row
        self._label(note_row, "✎ Note", font="small", fg="#c4b5fd").pack(side=tk.LEFT, padx=(0, 6))
        self.var_seg_note = tk.StringVar(value="")
        self.ent_seg_note = self._entry(note_row, self.var_seg_note, font="small")
        self.ent_seg_note.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ent_seg_note.bind("<Return>", lambda e: (self._save_segment_edit(), "break")[-1])
        for seq in (f"<{MOD}-Return>", f"<{MOD}-KP_Enter>"):
            self.ent_seg_note.bind(seq, lambda e: (self._check_and_next(), "break")[-1])
        self.edit_note_original = ""
        # only what is worth knowing about this segment (re-transcribed, Whisper wrote something else); the usual
        # hint about timing is a tooltip on the text box
        self.lbl_edit_hint = self._label(extras, "", font="small", fg=T["fg_dim"], height=1, anchor="w", justify=tk.LEFT)
        self._tip(self.edit_text, self.EDIT_HINT)
        self.edit_seg_idx: Optional[int] = None
        self.edit_original = ("", "")

        self._build_video_panel()
        # checked segments: a thin green bar in the margin beside their lines (instead of a ✓ in the text)
        self.check_bar = tk.Canvas(frame, width=self.CHECK_BAR_W, bg="#0b0d13", highlightthickness=0, bd=0)
        self.preview_text = tk.Text(frame, bg="#0b0d13", fg=T["fg_primary"], font=self.f["transcript"], relief=tk.FLAT, padx=12, pady=12,
                                    wrap=tk.WORD, highlightthickness=0, cursor="arrow", spacing1=2, spacing3=2, state=tk.DISABLED)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=lambda a, b: (sb.set(a, b), self._schedule_check_bar()))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        self.check_bar.grid(row=0, column=0, sticky="ns")
        self.preview_text.grid(row=0, column=1, sticky="nsew")
        sb.grid(row=0, column=2, sticky="ns")
        self.preview_text.bind("<Configure>", lambda e: self._schedule_check_bar(), add="+")
        pt = self.preview_text
        # the line above a paragraph — speaker and times — is small and quiet: the spoken text leads
        pt.tag_config("SEG_HDR", foreground=T["fg_dim"], font=self.f["small"], spacing1=12)
        for i, color in enumerate(SPEAKER_COLORS):
            pt.tag_config(f"SPK{i}", foreground=color, font=self.f["small_bold"], spacing1=12)
        pt.tag_config("HIGH", foreground=T["fg_primary"])
        pt.tag_config("MED", foreground="#f5c56b")
        pt.tag_config("LOW", foreground="#fb923c")
        pt.tag_config("POOR", foreground="#f87171", underline=True)
        pt.tag_config("PCT", foreground="#f87171", font=self.f["mono_small"])
        pt.tag_config("EDITSEG", background="#1c2a40")
        pt.tag_config("PLAYING", background="#1d3a2e")
        pt.tag_config("CURRENT", background="#3b4a63")
        pt.tag_config("MARKER", foreground="#8fb3ff", font=self.f["marker"])
        pt.tag_config("CUT", overstrike=True, foreground="#5b6475")
        pt.tag_config("NOTE", foreground="#c4b5fd", font=self.f["small"])
        pt.tag_config("FOUND", background="#5c4a12")
        pt.tag_config("CUT_HDR", foreground="#f59e0b", font=self.f["small_bold"])
        for i, color in enumerate(eplib.PALETTE):
            pt.tag_config(f"EPC{i}", foreground=color, font=self.f["small_bold"], spacing1=6, spacing3=2)
        pt.tag_config("MULTISEL", background="#3a2f5c")
        pt.bind("<ButtonRelease-1>", self._on_text_click)
        for seq in ("<Button-3>",) + (("<Button-2>", "<Control-Button-1>") if IS_MAC else ()):
            pt.bind(seq, lambda e: (self._transcript_menu(e), "break")[-1])  # re-transcribe / play what is highlighted
        pt.bind("<Shift-ButtonRelease-1>", self._on_shift_click)
        pt.bind("<Double-Button-1>", lambda e: (self._on_text_click(e), self._play_from_current_word(), "break")[-1])
        # A plain <Key-c> binding also fires for ⌘C / Ctrl+C: step aside when a modifier is held, so copy,
        # ⌘1–3 (tabs), ⌘R (start queue) and ⌃1–9 (Alt+1–9) keep working from the transcript. Shift, Caps Lock and
        # Num Lock are not modifiers here, nor the fn bit a Mac puts on ↑/↓ (see widgets.SHORTCUT_MODS).
        def brk(fn):
            def handler(event=None):
                if event is not None and is_shortcut(event):
                    return None
                fn()
                return "break"
            return handler
        # single keys while the transcript has focus (it is read-only, so they never type anything)
        pt.bind("<Right>", brk(lambda: self._jump_low_conf(+1)))
        pt.bind("<Left>", brk(lambda: self._jump_low_conf(-1)))
        pt.bind("<Down>", brk(lambda: self._move_segment(+1)))
        pt.bind("<Up>", brk(lambda: self._move_segment(-1)))
        pt.bind("<Shift-Down>", brk(lambda: self._move_segment(+1, extend=True)))
        pt.bind("<Shift-Up>", brk(lambda: self._move_segment(-1, extend=True)))
        pt.bind("<space>", brk(self._toggle_play))
        for d in range(1, 10):
            pt.bind(f"<Key-{d}>", brk(lambda d=d: self._assign_speaker_number(d)))
            try:
                pt.bind(f"<KeyPress-KP_{d}>", brk(lambda d=d: self._assign_speaker_number(d)))  # number pad
            except Exception:
                pass
        pt.bind("<Key-0>", brk(self._add_speaker_quick))
        for k in ("c", "C"):
            pt.bind(f"<Key-{k}>", brk(self._toggle_checked))
        for k in ("r", "R"):
            pt.bind(f"<Key-{k}>", brk(self._replay_segment))
        for k in ("x", "X"):
            pt.bind(f"<Key-{k}>", brk(self._toggle_cut))
        for k in ("e", "E"):
            pt.bind(f"<Key-{k}>", brk(self._mark_episode))
        for k in ("Delete",) + (("BackSpace",) if IS_MAC else ()):  # the Mac's delete key is BackSpace; asks first
            pt.bind(f"<{k}>", brk(self._delete_segment))
        for keys, fn in ((("s", "S"), self._split_at_current_word), (("m", "M"), self._merge_with_next),
                         (("i", "I"), self._insert_segment_dialog)):
            for k in keys:
                pt.bind(f"<Key-{k}>", brk(fn))
        pt.bind("<Return>", brk(self._focus_editor))
        # Ctrl/⌘ + mouse wheel over the transcript: its text size (like a browser)
        for widget in (pt, self.edit_text):
            widget.bind(f"<{MOD}-MouseWheel>", lambda e: (self._transcript_size_step(+1 if e.delta > 0 else -1), "break")[-1])
            if not IS_MAC:
                widget.bind("<Control-Button-4>", lambda e: (self._transcript_size_step(+1), "break")[-1])
                widget.bind("<Control-Button-5>", lambda e: (self._transcript_size_step(-1), "break")[-1])
        pt.bind(f"<{MOD}-Key-a>", lambda e: (self._select_all_segments(), "break")[-1])
        self.edit_text.bind("<Tab>", brk(self._focus_transcript))  # a tab character is never wanted in a transcript
        # Esc while typing: save and go back to the transcript (↑/↓ move on, Return edits again). Outside the text
        # boxes Esc still plays and pauses; "break" keeps it from doing both.
        self.edit_text.bind("<Escape>", lambda e: (self._focus_transcript(), "break")[-1])
        self.ent_seg_note.bind("<Escape>", lambda e: (self._close_note(), "break")[-1])
        for k in ("n", "N"):
            pt.bind(f"<Key-{k}>", brk(self._open_note))
        self.cmb_seg_speaker.bind("<<ComboboxSelected>>", lambda e: self._on_speaker_combo())
        self.sel_segs: List[int] = []
        self.sel_anchor: Optional[int] = None
        self._sel_nseg = 0

        # player state
        self.playing = False
        self.play_pos = 0.0
        self._play_from = 0.0
        self._play_t0 = 0.0
        self._play_until: Optional[float] = None
        self._play_speed = 1.0
        self._tick_job = None
        self.span_starts: List[float] = []
        self.span_lookup: Dict[Tuple[int, int], int] = {}
        self.seg_ranges: Dict[int, Tuple[str, str]] = {}

    # ----- rendering -----
    def _rerender(self, keep_view: bool = True):
        if self.active_doc is None:
            return
        keep = None
        if self.current_span is not None and self.current_span < len(self.word_spans):
            sp = self.word_spans[self.current_span]
            keep = (sp["seg"], sp["w"], sp["start"])
        anchor = self._view_anchor() if keep_view else None
        top = self.preview_text.yview()[0] if keep_view else 0.0
        self._render_doc(self.active_doc, reset_editor=False)
        if not (anchor and self._restore_view_anchor(anchor)):
            try:
                self.preview_text.yview_moveto(top)
            except Exception:
                pass
        if keep is not None:
            idx = self.span_lookup.get(keep[:2])
            if idx is None or abs(self.word_spans[idx]["start"] - keep[2]) > 0.01:  # segments merged/split: by time
                idx = self._span_near(keep[2])
            if idx is not None:
                self._select_span(idx, scroll=False, load_editor=False)
        self._highlight_edit_segment()

    # A redraw can regroup paragraphs (a segment joins another speaker's turn, two segments merge, a cut header
    # appears or goes). Keeping the same *fraction* of the text in view then lands somewhere else, so the view is
    # anchored to words, as in a document editor: the first word on screen stays exactly where it was, and what changed
    # below it moves (a segment given to the speaker above joins that paragraph, a line or so higher). Only if the open
    # segment would then be off screen does the view follow it instead (back to the height it had).
    def _span_near(self, t: float) -> Optional[int]:
        import bisect
        if not self.span_starts:
            return None
        i = bisect.bisect_left(self.span_starts, t - 1e-6)
        cands = [j for j in (i - 1, i) if 0 <= j < len(self.span_starts)]
        return min(cands, key=lambda j: abs(self.span_starts[j] - t)) if cands else None

    CHECK_BAR_W = 8

    def _show_note_row(self, show: bool):
        row = self.__dict__.get("note_row")
        if row is None:
            return
        self._note_shown = show
        if show:
            if self.lbl_edit_hint.winfo_manager():  # above a hint that is showing
                row.pack(fill=tk.X, pady=(0, 2), before=self.lbl_edit_hint)
            else:
                row.pack(fill=tk.X, pady=(0, 2))
        else:
            row.pack_forget()

    def _open_note(self):
        """N (or ⋯ ▸ Note…): the note line for the open segment, ready to type in."""
        if self.edit_seg_idx is None:
            self._move_segment(+1)
        if self.edit_seg_idx is None:
            return
        self._show_note_row(True)
        self.ent_seg_note.focus_set()
        self.ent_seg_note.icursor(tk.END)

    def _close_note(self):
        """Esc in the note: save it and back to the transcript; an empty note line goes away again."""
        self._focus_transcript()
        if not self.var_seg_note.get().strip():
            self._show_note_row(False)

    def _schedule_check_bar(self):
        """Redraw the margin bars once, after the scrolling or drawing in progress (not on every scroll event)."""
        if self.__dict__.get("_check_bar_job") is None:
            try:
                self._check_bar_job = self.after_idle(self._draw_check_bar)
            except Exception:
                self._check_bar_job = None

    def _checked_bar_spans(self) -> List[Tuple[int, int]]:
        """(top, bottom) on screen of the checked segments in view, as drawn in the margin."""
        doc, pt = self.active_doc, self.preview_text
        if doc is None or not self.__dict__.get("seg_ranges"):
            return []
        try:
            h = int(pt.winfo_height())
            top_line = int(str(pt.index("@0,0")).split(".")[0])
            bot_line = int(str(pt.index(f"@0,{h}")).split(".")[0])
        except Exception:
            return []
        out = []
        for si, (a, b) in self.seg_ranges.items():
            la, lb = int(a.split(".")[0]), int(b.split(".")[0])
            if lb < top_line or la > bot_line or si >= len(doc.segments) or not doc.segments[si].get("checked"):
                continue
            lb_, cb = b.split(".")
            last = f"{lb_}.{max(0, int(cb) - 1)}"
            ia, ib = pt.dlineinfo(a), pt.dlineinfo(last)
            ia = ia if isinstance(ia, tuple) else None
            ib = ib if isinstance(ib, tuple) else None
            if ia is None and ib is None and not (la < top_line and lb > bot_line):
                continue
            y0 = ia[1] + 2 if ia else 0
            y1 = ib[1] + ib[3] - 2 if ib else h
            out.append((y0, y1))
        return out

    def _draw_check_bar(self):
        self._check_bar_job = None
        cv = self.__dict__.get("check_bar")
        if cv is None:
            return
        cv.delete("all")
        x = self.CHECK_BAR_W // 2
        for y0, y1 in self._checked_bar_spans():
            cv.create_line(x, y0, x, max(y0 + 1, y1), fill=THEME["ok"], width=3, capstyle="round")

    def _word_y(self, i: int) -> Optional[Tuple[int, int]]:
        """(top, height) on screen of word span i, or None when it is not in view."""
        sp = self.word_spans[i]
        try:
            bb = self.preview_text.bbox(f"{sp['line']}.{sp['c0']}")
        except Exception:
            return None
        return (int(bb[1]), int(bb[3])) if isinstance(bb, tuple) and len(bb) == 4 else None

    def _view_anchor(self) -> Optional[Dict]:
        """Where the first word on screen and the open segment's word are now: {"top": (time, y), "cur": (time, y)}."""
        pt = self.preview_text
        out: Dict = {}
        try:
            idx = self.current_span
            if idx is not None and idx < len(self.word_spans):
                y = self._word_y(idx)
                if y is not None:
                    out["cur"] = (self.word_spans[idx]["start"], y[0])
            top_line = int(str(pt.index("@0,0")).split(".")[0])
            for line in range(top_line, top_line + 60):
                for i in self.line_spans.get(line, []):
                    y = self._word_y(i)
                    if y is not None and y[0] >= 0:
                        out["top"] = (self.word_spans[i]["start"], y[0])
                        break
                if "top" in out:
                    break
        except Exception:
            return out or None
        return out or None

    def _place_word(self, t: float, y: int) -> Optional[int]:
        """Scroll so that the word at time t is y pixels from the top, to within a display line (its own line, not its
        paragraph's first). By whole display lines, not pixels: on Linux, pixel scrolling made Tk lay out a long
        transcript again and again. Returns where it ended up."""
        i = self._span_near(t)
        if i is None:
            return None
        sp = self.word_spans[i]
        pt = self.preview_text
        index = f"{sp['line']}.{sp['c0']}"
        try:
            pt.yview(index)  # its paragraph at the top (the word may be some display lines further down) …
            got = self._word_y(i)
            if got is None:  # a paragraph taller than the window: bring the word itself into view
                pt.see(index)
                got = self._word_y(i)
            # A word cut off at the window's edge has a box only a pixel or two high: step by a whole text line, never
            # by that (it once sent the view to the end of the transcript). Lines with paragraph spacing are taller,
            # so a step falls short rather than past, and the next round makes up the rest.
            # A step that takes the word off the screen altogether is taken back and halved.
            line_h = max(1, int(self.f["transcript"].metrics("linespace")))
            cap = None
            for _ in range(8):  # … then by display lines to where it was (again: lines differ in height, can re-wrap)
                if got is None:
                    break
                lines = int(round((got[0] - y) / max(line_h, got[1])))
                if cap is not None:
                    lines = max(-cap, min(cap, lines))
                if not lines:
                    break
                pt.yview_scroll(lines, "units")
                new = self._word_y(i)
                if new is None:
                    pt.yview_scroll(-lines, "units")
                    cap = abs(lines) // 2
                    if not cap:
                        break
                    continue
                got = new
        except Exception:
            return None
        return got[0] if got else None

    def _restore_view_anchor(self, anchor) -> bool:
        if isinstance(anchor, tuple):  # (time, y) of one word
            anchor = {"cur": anchor}
        placed = False
        if anchor.get("top"):
            placed = self._place_word(*anchor["top"]) is not None
        cur = anchor.get("cur")
        if cur:
            i = self._span_near(cur[0])
            got = self._word_y(i) if i is not None else None
            h = max(1, int(self.preview_text.winfo_height()))
            line_h = max(got[1] if got else 0, int(self.f["transcript"].metrics("linespace")))  # a cut-off box is too low
            if got is None or got[0] < 0 or got[0] + 2 * line_h > h:  # the open segment would be out of view: follow it
                placed = self._place_word(cur[0], max(0, min(cur[1], h - 3 * line_h))) is not None or placed
        return placed

    def _render_doc(self, doc: TranscriptDocument, reset_editor: bool = True):
        if reset_editor and self.active_doc is not None and doc is not self.active_doc:
            self._remember_position()
            self._autosave_edit(rerender=False)  # the old document is about to be replaced
            self._player_pause()
        new_doc = doc is not self.active_doc
        self.active_doc = doc
        if new_doc:
            synced = doc.sync_text_with_words()
            removed = doc.remove_empty_segments()
            if synced or removed:
                try:
                    doc.save()
                    doc.export_all()
                    parts = []
                    if synced:
                        parts.append(f"matched the text of {synced} segment(s) to their timed words")
                    if removed:
                        parts.append(f"removed {removed} empty segment(s)")
                    self._append_log(f"{doc.base_name}: {' and '.join(parts)}; exports regenerated, logged in the edit history.", "INFO")
                except Exception as exc:
                    self._append_log(f"Could not save cleanup: {exc}", "WARN")
        report = doc.confidence_report(all_segments=True)
        cut_set = {i for i in range(len(doc.segments)) if doc.is_segment_cut(i)} if doc.cuts else set()
        high_t, med_t, poor_t = report["high_thresh"], report["med_thresh"], report["poor_thresh"]
        show_pct = bool(self.var_show_pct.get())
        speakers = doc.speakers()
        if new_doc:
            self._project_follow_doc(doc)
            self._forget_project_cache()
            if self.__dict__.get("pp_tree") is not None:
                self._pp_mark_open()
        roster = self._roster()
        spk_tag = {spk: f"SPK{i % len(SPEAKER_COLORS)}" for i, spk in enumerate(roster)}
        rsegs = report["segments"]
        show = self.var_show_filter.get() if self.__dict__.get("var_show_filter") is not None else "All segments"
        if show != "All segments":  # a filter shows matching segments one by one
            def wanted(i):
                if show == "Uncertain":
                    return any(float(w.get("probability", w.get("prob", 0.85))) < med_t for w in rsegs[i].get("words") or [])
                if show == "Not checked":
                    return not doc.segments[i].get("checked") and i not in cut_set
                if show == "With notes":
                    return bool(doc.segments[i].get("note"))
                if show.startswith("In "):
                    return i in in_episode
                return i in cut_set
            in_episode = set()
            if show.startswith("In "):
                for ep in doc.episodes:
                    if ep["type"] == show[3:]:
                        in_episode.update(doc.episode_segments(ep))
            groups = [[i] for i in range(len(rsegs)) if not is_blank_text(rsegs[i].get("text")) and wanted(i)]
        elif self.var_view_mode.get() == "Paragraphs":
            groups = [p["segments"] for p in doc.paragraphs(include_cut=True)]
        else:
            groups = [[i] for i in range(len(rsegs)) if not is_blank_text(rsegs[i].get("text"))]

        txt = self.preview_text
        spans: List[Dict] = []
        line_spans: Dict[int, List[int]] = {}
        low: List[int] = []
        seg_ranges: Dict[int, Tuple[str, str]] = {}
        # built in Python first, then only what changed is sent to Tk (gui/textrender.py)
        out = textrender.Lines()
        put = out.put
        eps, next_ep, open_eps = doc.episodes, 0, []
        for group in groups:
            first, last = rsegs[group[0]], rsegs[group[-1]]
            gstart = float(doc.segments[group[0]].get("start", 0.0))
            for ep in list(open_eps):  # episodes that ended before this paragraph
                if gstart >= ep["end"] - 0.05:
                    put(f"■ end of {ep['type']} {ep.get('label') or ''}\n", self._episode_tag(ep["type"]))
                    open_eps.remove(ep)
            while next_ep < len(eps) and eps[next_ep]["start"] <= gstart + 0.05:
                ep = eps[next_ep]
                next_ep += 1
                if ep["end"] <= gstart:
                    continue
                approx = "≈ " if ep.get("approx") else ""
                put(f"▶ {ep['type']} {ep.get('label') or ''}   {approx}{short_ts(ep['start'])[:-2]} – {short_ts(ep['end'])[:-2]}\n",
                    self._episode_tag(ep["type"]))
                open_eps.append(ep)
            spk = first.get("speaker")
            group_cut = group[0] in cut_set
            if group_cut:
                put("✂ cut  ", "CUT_HDR")
            if spk:
                put(f"{spk}  ", spk_tag.get(spk, "SPK0"))
            put(f"{short_ts(first['start'])} – {short_ts(last['end'])}\n", "SEG_HDR")
            for si in group:
                seg = rsegs[si]
                seg_start = f"{out.line}.{out.col}"
                words = seg["words"]
                in_marker = False
                if words:
                    for wi, w in enumerate(words):
                        w_str = str(w.get("word", ""))
                        if wi == 0 and out.col > 0 and not w_str.startswith(" "):
                            put(" ")
                        prob = float(w.get("probability", w.get("prob", 0.85)))
                        tag = "HIGH" if prob >= high_t else ("MED" if prob >= med_t else ("LOW" if prob >= poor_t else "POOR"))
                        token = w_str.strip()
                        if token.startswith("["):
                            in_marker = True
                        if in_marker:
                            tag = "MARKER"
                            if token.endswith("]"):
                                in_marker = False
                        c0 = out.col + (len(w_str) - len(w_str.lstrip()))
                        if si in cut_set:
                            put(w_str, tag, "CUT")
                        else:
                            put(w_str, tag)
                        c1 = out.col
                        if show_pct and prob < poor_t:
                            put(f"{int(round(prob * 100))}%", "PCT")
                        spans.append({"line": out.line, "c0": c0, "c1": c1, "start": float(w.get("start", seg["start"])),
                                      "end": float(w.get("end", seg["end"])), "prob": prob, "word": w_str.strip(),
                                      "speaker": seg.get("speaker"), "seg": si, "w": wi})
                        line_spans.setdefault(out.line, []).append(len(spans) - 1)
                        if prob < med_t:
                            low.append(len(spans) - 1)
                else:
                    put((" " if out.col > 0 else "") + (seg["text"] or "…"), *(("HIGH", "CUT") if si in cut_set else ("HIGH",)))
                seg_ranges[si] = (seg_start, f"{out.line}.{out.col}")
                note = doc.segments[si].get("note")
                if note:
                    put(f"  ✎ {note}", "NOTE")
            put("\n")
        self._shown_lines = textrender.show_lines(txt, self.__dict__.get("_shown_lines"), out.lines)
        txt.configure(state=tk.DISABLED)
        for tag in ("sel", "FOUND", "MULTISEL", "EDITSEG", "PLAYING", "CURRENT"):  # as after a full redraw; repainted below
            txt.tag_remove(tag, "1.0", tk.END)
        for tag in ("CUT", "FOUND", "MULTISEL", "EDITSEG", "PLAYING", "CURRENT"):
            txt.tag_raise(tag)

        self.word_spans, self.line_spans, self.low_conf, self.current_span = spans, line_spans, low, None
        self.span_starts = [sp["start"] for sp in spans]
        self.span_lookup = {(sp["seg"], sp["w"]): i for i, sp in enumerate(spans)}
        self.seg_ranges = seg_ranges
        self._schedule_check_bar()  # checked marks are in the margin: the text itself may not have changed
        if new_doc:
            self.sel_segs, self.sel_anchor = [], None
        self._paint_multi_selection()
        self._paint_found()
        total = max(1, len(spans))
        edited = sum(1 for s in doc.segments if s.get("edited"))
        self.lbl_ci_summary.config(
            # short and calm: one line beside "Aa", the cuts and the filter still fit (p: mean word probability)
            text=f"{doc.base_name}  ·  {doc.checked_fraction() * 100:.0f}% checked  ·  {len(spans)} words  ·  "
                 f"{len(low)} uncertain ({len(low) * 100 / total:.0f}%)  ·  mean p {report['overall_ci'][0] * 100:.0f}%  ·  "
                 f"{len(roster)} speaker{'' if len(roster) == 1 else 's'}" + (f"  ·  {edited} edited" if edited else "")
                 + (f"  ·  ✂ {cutlib.describe(doc.cuts)}" if doc.cuts else "")
                 + (f"  ·  showing {len(groups)} {show.lower()}" if show != "All segments" else "")
        )
        self.cmb_seg_speaker.configure(values=roster)
        if self.__dict__.get("cmb_show") is not None:
            self.cmb_show.configure(values=self.SHOW_FILTERS + [f"In {t}" for t in self._episode_types()])
        self._refresh_speaker_chips()
        if new_doc:
            self.play_pos = 0.0
            self._clear_editor()
            self._update_task_progress(doc)
            media = self._media()
            if media:
                self.lbl_word.config(text="")
                self.lbl_status.config(text=kbd("Click a word to edit its segment · drag or ⇧-click to select several · 1–9 assigns a speaker · "
                                                "↑/↓ segments · ←/→ uncertain words · View ▸ Keyboard Shortcuts"))
            else:
                self.lbl_word.config(text="")
                self.lbl_status.config(text="⚠ Playback media not found (moved or deleted?) — see 'media' in the .transcript.json")
            self._resume_position(doc)
        self._update_time_label()
        self._timeline_redraw()
        if new_doc:
            self._video_stop()
            self._toggle_video_panel()
            self._video_still(self.play_pos)
        if self.__dict__.get("cd_text") is not None and self._cd_visible():
            self._cd_refresh()  # the Coding tab shows the same transcript (also after undo)


    def _select_span(self, idx: int, autoplay: bool = False, scroll: bool = True, load_editor: bool = True):
        if not (0 <= idx < len(self.word_spans)):
            return
        sp = self.word_spans[idx]
        if load_editor and sp["seg"] != self.edit_seg_idx and self._editor_dirty():
            target = (sp["start"], sp["word"])  # by time + text: segment numbers may shift if the edit deleted a segment
            self._save_segment_edit(reload=False)  # never lose an edit by clicking elsewhere
            idx = next((i for i, x in enumerate(self.word_spans) if x["start"] == target[0] and x["word"] == target[1]), None)
            if idx is None:
                return
            sp = self.word_spans[idx]
        self.current_span = idx
        a, b = f"{sp['line']}.{sp['c0']}", f"{sp['line']}.{sp['c1']}"
        self.preview_text.tag_remove("CURRENT", "1.0", tk.END)
        self.preview_text.tag_add("CURRENT", a, b)
        if scroll:
            self.preview_text.see(a)
        pos = f"  ·  uncertain {self.low_conf.index(idx) + 1} of {len(self.low_conf)}" if idx in self.low_conf else ""
        # (the speaker is the filled chip below)
        self.lbl_word.config(text=f"“{sp['word']}”  {short_ts(sp['start'])}  ·  p {sp['prob'] * 100:.0f}%{pos}", fg=THEME["fg_dim"])
        if load_editor and sp["seg"] != self.edit_seg_idx:
            self._load_segment_into_editor(sp["seg"])
        if not self.playing:
            self.play_pos = max(0.0, sp["start"] - 0.5)
            self._update_time_label()
            self._video_still(sp["start"])
        if autoplay:
            self._player_start(max(0.0, sp["start"] - 1.0), duration=max(3.0, sp["end"] - sp["start"] + 2.5))

    def _span_at(self, event) -> Optional[int]:
        index = self.preview_text.index(f"@{event.x},{event.y}")
        line, col = (int(v) for v in index.split("."))
        for i in self.line_spans.get(line, []):
            sp = self.word_spans[i]
            if sp["c0"] <= col < max(sp["c1"], sp["c0"] + 1):
                return i
        return None

    def _on_text_click(self, event):
        self.preview_text.focus_set()
        dragged = self._segments_in_sel()  # read before a save re-renders the text (which drops the selection)
        doc = self.active_doc
        n_before = len(doc.segments) if doc is not None else 0
        i = self._span_at(event)
        if i is not None:
            self._select_span(i)
            if self.playing:
                self._player_start(max(0.0, self.word_spans[self.current_span]["start"] - 0.5))
        if len(dragged) > 1 and doc is not None and len(doc.segments) == n_before:
            anchor = dragged[-1] if self.edit_seg_idx == dragged[0] else dragged[0]
            self._set_multi_selection(dragged, anchor)
        else:
            self._clear_multi_selection()

    def _on_shift_click(self, event):
        """⇧-click: select every segment from the open one (or the selection's start) to the clicked one."""
        self.preview_text.focus_set()
        anchor = self.sel_anchor if self.sel_anchor is not None else self.edit_seg_idx
        i = self._span_at(event)
        if i is None:
            return None
        self._select_span(i)
        if anchor is not None and self.current_span is not None:
            self._extend_selection(anchor, self.word_spans[self.current_span]["seg"])
        return None  # let Tk's own release handling run (it stops drag auto-scrolling)

    # ----- segment editor -----
    def _clear_editor(self):
        self.edit_seg_idx = None
        self.edit_original = ("", "")
        self.edit_text.delete("1.0", tk.END)
        self.var_seg_speaker.set("")
        self.edit_note_original = ""
        self.var_seg_note.set("")
        self._show_note_row(False)
        self.lbl_edit_title.config(text="Click a word to edit it")
        self.preview_text.tag_remove("EDITSEG", "1.0", tk.END)

    def _editor_dirty(self) -> bool:
        if self.edit_seg_idx is None:
            return False
        text = " ".join(self.edit_text.get("1.0", "end-1c").split())
        note = " ".join(self.var_seg_note.get().split())
        return (text != " ".join(self.edit_original[0].split()) or self.var_seg_speaker.get().strip() != self.edit_original[1]
                or note != self.edit_note_original)

    def _load_segment_into_editor(self, seg_idx: int):
        doc = self.active_doc
        if doc is None or not (0 <= seg_idx < len(doc.segments)):
            return
        seg = doc.segments[seg_idx]
        words = seg.get("words") or []
        # exactly what is highlighted in the transcript: the timed words
        text = ("".join(str(w.get("word", "")) for w in words) if words else (seg.get("text") or "")).strip()
        speaker = seg.get("speaker") or ""
        self.edit_seg_idx = seg_idx
        self.edit_original = (text, speaker)
        self.edit_text.delete("1.0", tk.END)
        self.edit_text.insert("1.0", text)
        self.edit_text.edit_reset()
        self.var_seg_speaker.set(speaker)
        self.edit_note_original = seg.get("note") or ""
        self.var_seg_note.set(self.edit_note_original)
        self._show_note_row(bool(self.edit_note_original))
        self._refresh_speaker_chips()
        mark = " ✎" if seg.get("edited") else ""  # (checked: the ✓ button beside it is green)
        self.btn_checked.configure(style=rounded.style_for(self.btn_checked.master, "CheckOn" if seg.get("checked") else "Check"))
        self.lbl_edit_title.config(text=f"{seg_idx + 1}/{len(doc.segments)} · {short_ts(seg.get('start', 0))} – {short_ts(seg.get('end', 0))}{mark}")
        orig = seg.get("text_whisper")
        rt = seg.get("retranscribed") or {}
        if rt and not seg.get("edited"):
            what = "translated to English" if rt.get("task") == "translate" else "re-transcribed"
            self.lbl_edit_hint.config(text=kbd(f"This segment was {what} with Whisper {rt.get('model')} (language: {rt.get('language')}). "
                                               "Undo (⌘Z) brings back the previous version."), fg="#8fb3ff")
            self.lbl_edit_hint.pack(fill=tk.X)
        elif orig and " ".join(str(orig).split()) != " ".join(text.split()) and not seg.get("edited"):
            self.lbl_edit_hint.config(text=f"Whisper's own text for this segment differed: “{str(orig).strip()[:110]}” — listen and correct if needed.",
                                      fg=THEME["warn"])
            self.lbl_edit_hint.pack(fill=tk.X)
        else:
            self.lbl_edit_hint.config(text="", fg=THEME["fg_dim"])  # the usual hint is on the text box, on hover
            self.lbl_edit_hint.pack_forget()
        self._highlight_edit_segment()

    def _highlight_edit_segment(self):
        self.preview_text.tag_remove("EDITSEG", "1.0", tk.END)
        rng = self.seg_ranges.get(self.edit_seg_idx) if self.edit_seg_idx is not None else None
        if rng:
            self.preview_text.tag_add("EDITSEG", *rng)
