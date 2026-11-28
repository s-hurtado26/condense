"""Transcript editor: checked marks, markers, speaker chips and number keys."""
from condense.gui._common import *  # noqa: F401,F403


class ReviewMarksMixin:
    # ----- checked marks -----
    def _update_task_progress(self, doc: TranscriptDocument):
        pct = round(doc.checked_fraction() * 100)
        changed = False
        for t in self.jobs:
            if t.get("doc_path") == str(doc.path):
                t["checked_pct"] = pct
                if t["status"] == "Completed":
                    t["stage"] = f"Done ✓ · {pct}% checked"
                self._update_job_row(t)
                changed = True
        if changed:
            self._save_queue()
        if self.__dict__.get("pp_tree") is not None:
            self._pp_update_doc(doc)

    def _toggle_checked(self):
        doc, idx = self.active_doc, self.edit_seg_idx
        if doc is None or not self._selected_segments():
            self.lbl_status.config(text="Click a word to pick a segment first.")
            return
        self._autosave_edit(rerender=False)
        segs = self._selected_segments()
        if len(segs) > 1:  # several selected: mark them all checked (or all unchecked if they already are)
            now = not all(doc.segments[s].get("checked") for s in segs)
            for s in segs:
                doc.set_checked(s, now)
            if self._commit(f"Marked {len(segs)} segments ({segs[0] + 1}–{segs[-1] + 1}) {'checked' if now else 'not checked'}.") is not None:
                self._rerender()
                if self.edit_seg_idx is not None:
                    self._load_segment_into_editor(self.edit_seg_idx)
            return
        now = not bool(doc.segments[idx].get("checked"))
        doc.set_checked(idx, now)
        if self._commit(f"Segment {idx + 1} marked {'checked' if now else 'not checked'}.") is not None:
            self._rerender()
            self._load_segment_into_editor(idx)

    def _mark_transcripts_checked(self, paths: List[Path], checked: bool = True, ask: bool = True) -> int:
        """Whole transcripts marked checked (100 %) or not checked, e.g. after reviewing outside Condense. Each gets a
        backup and an entry in its edit log; ⌘Z / Ctrl+Z undoes it when that transcript is open."""
        paths = [Path(p) for p in paths if p]
        if not paths:
            return 0
        what = "checked (100 %)" if checked else "not checked (0 %)"
        names = "\n".join(f"• {p.name.replace(TranscriptDocument.SUFFIX, '')}" for p in paths[:8]) + ("\n…" if len(paths) > 8 else "")
        if ask and not messagebox.askyesno("Mark transcripts", f"Mark every segment of {len(paths)} transcript(s) as {what}?\n\n{names}\n\n"
                                           "Cut segments don't count. A backup is kept, and "
                                           f"{kbd('⌘Z')} undoes it when the transcript is open.", parent=self):
            return 0
        total = 0
        for path in paths:
            active = self.active_doc is not None and Path(self.active_doc.path).resolve() == path.resolve()
            if active:
                self._autosave_edit(rerender=False)
                doc = self.active_doc
                n = doc.set_all_checked(checked)
                if n and self._commit(f"Marked the whole transcript {what}: {n} segment(s).") is not None:
                    self._rerender()
                    if self.edit_seg_idx is not None:
                        self._load_segment_into_editor(self.edit_seg_idx)
            else:
                try:
                    previous = path.read_text(encoding="utf-8")
                    doc = TranscriptDocument.load(path)
                    n = doc.set_all_checked(checked)
                    if n:
                        doc.save(backup=True)
                        self._push_undo(doc.path, f"Marked the whole transcript {what}", previous)
                except Exception as exc:
                    self._append_log(f"Could not mark {path.name}: {exc}", "ERROR")
                    continue
                self._update_task_progress(doc)
            total += n
            self._append_log(f"{path.name}: {n} segment(s) marked {what}.", "INFO")
        self.lbl_status.config(text=f"{len(paths)} transcript(s) marked {what}.")
        return total

    def _check_and_next_key(self, event=None):
        """Ctrl+Enter anywhere in the main window, but only while the Transcript tab is showing (never from a dialog
        or another tab, where it would check a segment you cannot see)."""
        try:
            if event is not None and event.widget.winfo_toplevel() is not self:
                return None
            if str(self.notebook.select()) != str(self.tab_preview):
                return None
        except Exception:
            return None
        self._check_and_next()
        return "break"

    def _check_and_next(self):
        """Save the segment (text + speaker), mark it checked and move to the next one: the review loop."""
        doc, idx = self.active_doc, self.edit_seg_idx
        if doc is None or idx is None:
            self.lbl_status.config(text="Click a word to pick a segment first.")
            return
        text = self.edit_text.get("1.0", "end-1c")
        if is_blank_text(text) and not is_blank_text(self.edit_original[0]):
            self._delete_segment()
            return
        doc.edit_segment_text(idx, text)
        doc.set_segment_speaker(idx, self.var_seg_speaker.get())
        doc.set_segment_note(idx, self.var_seg_note.get())
        doc.set_checked(idx, True)
        if self._commit(f"Checked segment {idx + 1}.") is None:
            return
        self.edit_original = ("", "")
        self._rerender()
        nxt = next((i for i in range(idx + 1, len(doc.segments)) if not is_blank_text(doc.segments[i].get("text"))), None)
        if nxt is None:
            self._load_segment_into_editor(idx)
            self.lbl_status.config(text=f"Checked segment {idx + 1} — that was the last one. {doc.checked_fraction() * 100:.0f}% checked.")
            return
        first = self.span_lookup.get((nxt, 0))
        if first is not None:
            self._select_span(first)
        else:
            self._load_segment_into_editor(nxt)
        self.edit_text.focus_set()

    # ----- markers -----
    def _show_marker_menu(self):
        self.marker_menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _insert_marker(self, template: str):
        if self.active_doc is None or self.edit_seg_idx is None:
            self.lbl_status.config(text="Click a word to open its segment, then insert the marker where it belongs.")
            return
        text = template.replace("{t}", short_ts(self._current_pos())[:-2])
        box = self.edit_text
        box.focus_set()
        before = box.get("insert-1c", "insert")
        if before and not before.isspace():
            text = " " + text
        box.insert("insert", text + ("" if text.endswith(": ]") else " "))
        if text.endswith(": ]"):  # [unclear: |] — put the cursor where the guess goes
            box.mark_set("insert", "insert-1c")

    # ----- speaker chips in the segment editor -----
    def _refresh_speaker_chips(self):
        """The speaker chips under the segment. Built again only when the speakers (or the kind of selection) change;
        moving to another segment only recolours them — rebuilding on every ↑/↓ made the row blink and lag."""
        chips = self.__dict__.get("spk_chips")
        if chips is None:
            return
        doc = self.active_doc
        if doc is None:
            chips.clear()
            self._chip_sig = None
            return
        T = THEME
        segs = [s for s in (self.__dict__.get("sel_segs") or []) if s < len(doc.segments)]
        if len(segs) > 1:
            names = {doc.segments[s].get("speaker") or "" for s in segs}
            current = names.pop() if len(names) == 1 else ""
            lead = f"Assign to {len(segs)} selected segments ({segs[0] + 1}–{segs[-1] + 1}):"
        else:
            current = self.var_seg_speaker.get().strip()
            lead = "Speaker"
        roster = list(self._roster())
        sig = (lead, tuple(roster), bool(self._generic_speakers()))
        if sig == self.__dict__.get("_chip_sig") and self.__dict__.get("_chip_by_name"):
            self._paint_speaker_chips(current)
            return
        self._chip_sig = sig
        chips.clear()
        if len(segs) > 1:
            chips.add(self._label(chips, lead, font="small_bold", fg="#c4b5fd"))
        else:
            chips.add(self._label(chips, lead, font="small", fg=T["fg_dim"]))
        self._chip_by_name = {}
        for i, name in enumerate(roster):
            # no outlines: the name in its colour; the segment's speaker filled
            chip = tk.Label(chips, text=(f"{i + 1}  " if i < 9 else "") + name, font=self.f["small_bold"], padx=8, pady=2, cursor="hand2",
                            bg=T["bg_card"], fg=SPEAKER_COLORS[i % len(SPEAKER_COLORS)], highlightthickness=0)
            chip.condense_color = SPEAKER_COLORS[i % len(SPEAKER_COLORS)]
            chip.bind("<Button-1>", lambda e, n=name: self._assign_speaker(n))
            for seq in ("<Button-3>",) + (("<Button-2>", "<Control-Button-1>") if IS_MAC else ()):
                chip.bind(seq, lambda e, n=name: self._speaker_chip_menu(e, n))
            chips.add(chip)
            self._chip_by_name[name] = chip
        add = tk.Label(chips, text="0  + Speaker", font=self.f["small"], padx=8, pady=2, cursor="hand2", bg=T["bg_card"], fg=T["fg_dim"],
                       highlightthickness=0)
        add.bind("<Button-1>", lambda e: self._add_speaker_quick())
        chips.add(add)
        if sig[2]:  # labels from speaker detection still waiting for a name
            who = tk.Label(chips, text="Who is who?…", font=self.f["small_bold"], padx=8, pady=2, cursor="hand2", bg=T["bg_card"],
                           fg="#fbbf24", highlightthickness=0)
            who.bind("<Button-1>", lambda e: self._match_speakers_dialog())
            chips.add(who)
        self._paint_speaker_chips(current)

    def _paint_speaker_chips(self, current: str):
        T = THEME
        for name, chip in (self.__dict__.get("_chip_by_name") or {}).items():
            active = name == current
            want = (chip.condense_color if active else T["bg_card"], T["bg_root"] if active else chip.condense_color)
            if (chip.cget("bg"), chip.cget("fg")) != want:  # only what changed: no redraw for the rest
                chip.configure(bg=want[0], fg=want[1])

    # ----- detected speakers (SPEAKER_01 …) → the real names, for the whole transcript -----
    def _generic_speakers(self) -> List[str]:
        doc = self.active_doc
        if doc is None:
            return []
        used = {s.get("speaker") for s in doc.segments}
        return [n for n in doc.roster() if n in used and n.startswith(("SPEAKER_", "Speaker "))]

    def _merge_speaker(self, old: str, new: str) -> int:
        """Every segment of `old` becomes `new` (also when `new` already has segments: the two are merged)."""
        doc = self.active_doc
        new = " ".join((new or "").split())
        if doc is None or not new or new == old:
            return 0
        self._autosave_edit(rerender=False)
        n = doc.rename_speakers({old: new})
        if n and self._commit(f"All {n} segment(s) of {old} are now {new}.") is not None:
            self._rerender()
            if self.edit_seg_idx is not None:
                self._load_segment_into_editor(self.edit_seg_idx)
        return n

    def _speaker_chip_menu(self, event, name: str):
        m = PopupMenu(self)
        others = [n for n in self._roster() if n != name]
        named = [n for n in others if not n.startswith(("SPEAKER_", "Speaker "))]
        generic = [n for n in others if n.startswith(("SPEAKER_", "Speaker "))]
        m.add_command(label=f"All segments of {name} are…", state=tk.DISABLED)
        for n in named + generic:
            m.add_command(label=f"   {n}", command=lambda n=n: self._merge_speaker(name, n))
        m.add_command(label="   another name…", command=lambda: self._merge_speaker(
            name, simpledialog.askstring("Speaker", f"Who is {name}?", parent=self) or ""))
        m.add_separator()
        m.add_command(label="Who is who? (all detected speakers)…", command=self._match_speakers_dialog)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return m

    def _match_speakers_dialog(self):
        """One row per detected speaker: how much they speak, a typical line, ▶ to listen, and whom it is."""
        doc = self.active_doc
        if doc is None:
            return None
        T = THEME
        generic = self._generic_speakers()
        names = [n for n in self._roster() if not n.startswith(("SPEAKER_", "Speaker "))]
        win = tk.Toplevel(self)
        win.title("Who is who?")
        win.configure(bg=T["bg_panel"], padx=16, pady=14)
        win.transient(self)
        self._label(win, "Speaker detection labels voices SPEAKER_00, SPEAKER_01 … Listen to each and choose who it is: all of "
                         "its segments get that name. Two labels can get the same name (the same person split in two). "
                         f"One undo step ({kbd('⌘Z')}).", font="small", fg=T["fg_secondary"], bg=T["bg_panel"], wraplength=620,
                    justify=tk.LEFT).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        rows: Dict[str, tk.StringVar] = {}
        KEEP = "(leave as it is)"
        for r, g in enumerate(generic, start=1):
            idx = [i for i, s in enumerate(doc.segments) if s.get("speaker") == g]
            secs = sum(float(doc.segments[i]["end"]) - float(doc.segments[i]["start"]) for i in idx)
            sample_i = max(idx, key=lambda i: len((doc.segments[i].get("text") or "").split()))
            sample = " ".join((doc.segments[sample_i].get("text") or "").split())
            self._label(win, g, font="small_bold", bg=T["bg_panel"]).grid(row=2 * r - 1, column=0, sticky="w", padx=(0, 10))
            self._label(win, f"{len(idx)} segment(s), {short_ts(secs)[:-2]}", font="small", fg=T["fg_secondary"], bg=T["bg_panel"]
                        ).grid(row=2 * r - 1, column=1, sticky="w")
            self._tool(win, "▶ Listen", lambda i=sample_i: (self._goto_segment(i), self._replay_segment())).grid(row=2 * r - 1, column=2, padx=8)
            v = tk.StringVar(value=KEEP)
            ttk.Combobox(win, textvariable=v, values=[KEEP] + names, width=22, font=self.f["small"]).grid(row=2 * r - 1, column=3, sticky="w")
            rows[g] = v
            self._label(win, f"“{sample[:110]}{'…' if len(sample) > 110 else ''}”", font="small", fg=T["fg_dim"], bg=T["bg_panel"],
                        anchor="w", justify=tk.LEFT).grid(row=2 * r, column=0, columnspan=4, sticky="w", pady=(0, 8))
        if not generic:
            self._label(win, "All speakers have names.", font="small", bg=T["bg_panel"]).grid(row=1, column=0, sticky="w")

        def apply():
            mapping = {g: " ".join(v.get().split()) for g, v in rows.items() if v.get().strip() and v.get() != KEEP}
            mapping = {g: n for g, n in mapping.items() if n and n != g}
            if not mapping:
                win.destroy()
                return 0
            self._autosave_edit(rerender=False)
            n = self.active_doc.rename_speakers(mapping)
            if n and self._commit("Speakers named: " + ", ".join(f"{g} → {v}" for g, v in mapping.items())) is not None:
                self._rerender()
                if self.edit_seg_idx is not None:
                    self._load_segment_into_editor(self.edit_seg_idx)
            win.destroy()
            return n

        bar = tk.Frame(win, bg=T["bg_panel"])
        bar.grid(row=2 * len(generic) + 2, column=0, columnspan=4, sticky="e", pady=(10, 0))
        self._tool(bar, "Cancel", win.destroy).pack(side=tk.LEFT, padx=(0, 6))
        self._tool(bar, "Apply", apply, primary=True).pack(side=tk.LEFT)
        win.bind("<Escape>", lambda e: (win.destroy(), "break")[-1])
        return win, {"rows": rows, "apply": apply, "KEEP": KEEP}

    def _assign_speaker(self, name: str):
        if self.active_doc is None or not self._selected_segments():
            self.lbl_status.config(text="Click a word in the transcript first, then pick the speaker for that segment.")
            return
        segs = self._selected_segments()
        if len(segs) > 1:
            self._assign_speaker_many(name, segs)
            return
        self.var_seg_speaker.set(name)
        self._save_segment_edit()
        self._refresh_speaker_chips()

    def _assign_speaker_many(self, name: str, segs: List[int]):
        """One speaker for many segments: a single save, a single undo step."""
        doc = self.active_doc
        self._autosave_edit(rerender=False)  # keep a text edit that was still being typed
        if len(doc.segments) != self._sel_nseg:  # that save deleted a segment: the selection no longer fits
            self._clear_multi_selection()
            self._rerender()
            return
        changed = [s for s in segs if doc.set_segment_speaker(s, name)]
        if not changed:
            self.lbl_status.config(text=f"All {len(segs)} selected segments are already {name}.")
            return
        if self._commit(f"Assigned {name} to {len(changed)} segment(s) between {segs[0] + 1} and {segs[-1] + 1} ({'⌘' if IS_MAC else 'Ctrl+'}Z undoes).") is not None:
            self._rerender()
            if self.edit_seg_idx is not None:
                self._load_segment_into_editor(self.edit_seg_idx)
            self._refresh_speaker_chips()

    def _on_speaker_combo(self):
        """Picking a speaker in the editor's list applies it to the whole selection when several segments are selected."""
        if len(self._selected_segments()) > 1 and self.var_seg_speaker.get().strip():
            self._assign_speaker(self.var_seg_speaker.get().strip())

    def _assign_speaker_number(self, number: int):
        """⌃1–9 / Alt+1–9: the n-th speaker for what is selected in the mode shown — in Code mode the selected (or
        clicked) words' segments, in Edit mode the selected segments or the one being edited."""
        doc = self.active_doc
        if doc is None:
            return
        roster = self._roster()
        if 1 <= number <= len(roster):
            if self._cd_visible():
                return self._cd_assign_speaker(roster[number - 1])
            self._assign_speaker(roster[number - 1])

    def _add_speaker_quick(self):
        doc = self.active_doc
        if doc is None:
            return
        name = simpledialog.askstring("Add speaker", "Name of the new speaker (e.g. P03, Facilitator):", parent=self)
        if not name or not name.strip():
            return
        if doc.add_speaker(name) and self._commit(f"Added speaker {name.strip()}.") is not None:
            self._rerender()
            if self._selected_segments():
                self._assign_speaker(name.strip())
