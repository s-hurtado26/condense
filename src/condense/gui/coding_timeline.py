"""The timeline under the Transcript tab (Code and Edit mode): the recording in time, for coding video and reviewing.

Rows, top to bottom: a time ruler, frames of the video, who speaks (and the episodes behind everything), then one lane
per code — the codes shown on the timeline (codebook: right-click ▸ Show on timeline), or, while none are chosen, the
codes used in view. Time codings are outlined bars, codings of words solid ones.

Zoom: the buttons (whole recording, this episode, 10 or 2 minutes around the playhead), the mouse wheel (at the
mouse), Shift+wheel or dragging the ruler to move along. Click to jump there.

Coding by time: drag across the lanes (or press I and O at the playhead) to mark a range, then code it like words:
Return for the selected code, 1–9 for the recent ones, N for a new code. Drag a bar's edge to change it; right-click
a bar to play or loop it, write a memo, give it another code, attach it to the words said in it, or delete it.
While the video plays, 1–9 with nothing marked starts a coding at the playhead, and the same key ends it.
"""
import bisect

from condense.core import coding as cod
from condense.gui._common import *  # noqa: F401,F403

LABEL_W = 128         # the lane names
RULER_H = 18
FRAMES_H = 40
SPEAKERS_H = 12
LANE_H = 17
MAX_LANES = 14
MIN_SPAN = 4.0        # seconds: the closest zoom
EDGE_PX = 5           # how near a bar's edge grabs it
FRAME_STEP = 0.04     # one frame at 25 fps
TICK_STEPS = (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200)


def tick_step(span: float, plot_w: float, min_px: float = 90.0) -> int:
    """Seconds between ruler ticks, so that they are at least min_px apart."""
    for step in TICK_STEPS:
        if step / max(span, 1e-6) * plot_w >= min_px:
            return step
    return TICK_STEPS[-1]


def tick_label(t: float, step: int) -> str:
    t = int(round(t))
    h, m, s = t // 3600, t // 60 % 60, t % 60
    if step >= 60:
        return f"{h}:{m:02d}" if h else f"0:{m:02d}"
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class CodingTimelineMixin:
    # ================================================================== building
    def _build_cd_timeline(self, parent):
        T = THEME
        self.cdt = {"view": None, "in": None, "out": None, "drag": None, "live": {}, "hits": [], "lanes": [], "loop": None,
                    "thumbs": {}, "thumb_gen": 0, "thumb_q": queue.Queue(), "hover": None, "rows": {}, "lane_mode": "used"}
        bar = self._flow(parent, padx=4, pady=2, bg=T["bg_panel"], one_line=True)
        bar.pack(fill=tk.X, pady=(2, 0))
        self.cdt_bar = bar
        bar.add(self._heading(bar, "Timeline", bg=T["bg_panel"]))
        # the zoom: one switch, the current zoom lighter
        zoom = tk.Frame(bar, bg=T["bg_panel"])
        self.cdt_zoom_btns = {}
        for label, kind in (("Whole", "whole"), ("Episode", "episode"), ("10 min", "600"), ("2 min", "120")):
            b = ttk.Button(zoom, text=label, style=rounded.style_for(zoom, "Seg"), command=lambda k=kind: self._cdt_zoom(k), takefocus=0)
            b.pack(side=tk.LEFT)
            self.cdt_zoom_btns[kind] = b
        bar.add(zoom)
        bar.add(self._separator(bar))
        self.btn_cdt_play = self._tool(bar, "▶", self._cdt_play_mark)
        self.btn_cdt_loop = self._tool(bar, "⟳", self._cdt_toggle_loop)
        self.btn_cdt_clear = self._tool(bar, "✕", self._cdt_clear_mark)
        for b, tip in ((self.btn_cdt_play, "Play the marked range"), (self.btn_cdt_loop, "Loop the marked range (L)"),
                       (self.btn_cdt_clear, "Clear the mark (X)")):
            Tooltip(b, tip, font=self.f["small"])
            bar.add(b)
        self.lbl_cdt_mark = self._label(bar, "", font="small", fg=T["fg_secondary"], bg=T["bg_panel"])
        bar.add(self.lbl_cdt_mark)
        self.lbl_cdt_hint = self._label(bar, "", font="small", fg=T["fg_dim"], bg=T["bg_panel"])
        bar.add(self.lbl_cdt_hint)
        cv = tk.Canvas(parent, height=RULER_H + SPEAKERS_H + LANE_H * 2 + 8, bg=T["bg_input"], highlightthickness=0, bd=0,
                       cursor="crosshair", takefocus=1)
        cv.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.cd_timeline = cv
        cv.bind("<Configure>", lambda e: self._cdt_draw(request_frames=True))
        cv.bind("<Button-1>", self._cdt_press)
        cv.bind("<B1-Motion>", self._cdt_motion)
        cv.bind("<ButtonRelease-1>", self._cdt_release)
        cv.bind("<Double-Button-1>", self._cdt_double)
        cv.bind("<Motion>", self._cdt_hover)
        cv.bind("<Leave>", lambda e: self._cdt_hover(None))
        cv.bind("<Key>", self._cd_key)
        Tooltip(cv, lambda: "Drag (or press I and O) to mark a range: ↩ or 1–9 codes it, M comments on it. Drag the playhead "
                            "to scroll. Right-click a code ▸ Show on timeline to choose the lanes.", font=self.f["small"])
        for seq in ("<Button-3>",) + (("<Button-2>", "<Control-Button-1>") if IS_MAC else ()):
            cv.bind(seq, self._cdt_menu)
        cv.bind("<MouseWheel>", lambda e: self._cdt_wheel(e, -1 if e.delta > 0 else +1))
        cv.bind("<Shift-MouseWheel>", lambda e: self._cdt_pan_steps(-1 if e.delta > 0 else +1))
        cv.bind("<Button-4>", lambda e: self._cdt_wheel(e, -1))
        cv.bind("<Button-5>", lambda e: self._cdt_wheel(e, +1))
        cv.bind("<Shift-Button-4>", lambda e: self._cdt_pan_steps(-1))
        cv.bind("<Shift-Button-5>", lambda e: self._cdt_pan_steps(+1))
        self._cdt_show_mark()

    # ================================================================== the view (what part of the recording)
    def _cdt_duration(self) -> float:
        try:
            dur = float(self._duration())
        except Exception:
            dur = 0.0
        return max(dur, 1.0)

    def _cdt_view(self) -> Tuple[float, float]:
        dur = self._cdt_duration()
        v = self.cdt.get("view")
        if not v:
            return 0.0, dur
        a, b = max(0.0, v[0]), min(dur, v[1])
        if b - a < min(MIN_SPAN, dur):
            return 0.0, dur
        return a, b

    def _cdt_set_view(self, a: float, b: float, zoom: Optional[str] = None):
        dur = self._cdt_duration()
        span = min(dur, max(MIN_SPAN, b - a))
        a = max(0.0, min(a, dur - span))
        self.cdt["view"] = None if span >= dur - 1e-6 else (a, a + span)
        self.cdt["zoom"] = "whole" if self.cdt["view"] is None else zoom  # (zoomed by hand: none of the switch's)
        self._cdt_zoom_shown()
        self._cdt_draw(request_frames=True)
        return self._cdt_view()

    def _cdt_zoom_shown(self):
        current = self.cdt.get("zoom") or ("whole" if self.cdt.get("view") is None else None)
        for kind, b in (self.__dict__.get("cdt_zoom_btns") or {}).items():
            b.configure(style=rounded.style_for(b.master, "SegOn" if kind == current else "Seg"))

    def _cdt_zoom(self, kind: str):
        pos = self._current_pos() if self.active_doc is not None else 0.0
        if kind == "whole":
            return self._cdt_set_view(0.0, self._cdt_duration())
        if kind == "episode":
            doc = self.active_doc
            mark = self._cdt_mark()
            at = mark[0] if mark else pos
            ep = next((e for e in (doc.episodes if doc is not None else []) if e["start"] - 0.5 <= at <= e["end"] + 0.5), None)
            if ep is None:
                self.lbl_status.config(text="The playhead is not in an episode — mark interviews and phases as episodes (E) to zoom to them.")
                return None
            pad = max(2.0, (ep["end"] - ep["start"]) * 0.02)
            return self._cdt_set_view(ep["start"] - pad, ep["end"] + pad, zoom="episode")
        span = float(kind)
        return self._cdt_set_view(pos - span * 0.25, pos + span * 0.75, zoom=kind)

    def _cdt_zoom_at(self, t: float, factor: float):
        """Zoom in (factor < 1) or out around time t, which stays under the mouse."""
        a, b = self._cdt_view()
        f = (t - a) / max(b - a, 1e-6)
        span = (b - a) * factor
        return self._cdt_set_view(t - f * span, t - f * span + span)

    def _cdt_wheel(self, event, direction: int):
        t = self._cdt_t(event.x) if event is not None and event.x >= LABEL_W else sum(self._cdt_view()) / 2
        return self._cdt_zoom_at(t, 1.25 if direction > 0 else 0.8)

    def _cdt_pan_steps(self, direction: int):
        a, b = self._cdt_view()
        step = (b - a) * 0.15 * direction
        return self._cdt_set_view(a + step, b + step)

    # ================================================================== geometry (pure: testable)
    def _cdt_plot(self) -> Tuple[int, int]:
        w = max(LABEL_W + 60, int(self.cd_timeline.winfo_width()))
        return LABEL_W, w - 8

    def _cdt_x(self, t: float) -> float:
        a, b = self._cdt_view()
        x0, x1 = self._cdt_plot()
        return x0 + (t - a) / max(b - a, 1e-6) * (x1 - x0)

    def _cdt_xfun(self):
        """_cdt_x for many shapes at once: the view and the width looked up once."""
        a, b = self._cdt_view()
        x0, x1 = self._cdt_plot()
        k = (x1 - x0) / max(b - a, 1e-6)
        return lambda t: x0 + (t - a) * k

    def _cdt_t(self, x: float) -> float:
        a, b = self._cdt_view()
        x0, x1 = self._cdt_plot()
        return a + max(0.0, min(1.0, (x - x0) / max(x1 - x0, 1))) * (b - a)

    def _cdt_has_video(self) -> bool:
        try:
            return self._video_media() is not None
        except Exception:
            return False

    def _cdt_shown_codes(self) -> List[str]:
        """The codes chosen for the timeline in this project (right-click a code ▸ Show on timeline)."""
        project, cb = self._cd_project(), self._cd_codebook()
        if project is None or cb is None:
            return []
        ids = (self.settings.get("timeline_codes") or {}).get(str(project)) or []
        return [c["id"] for _d, c in cb.ordered() if c["id"] in ids]

    def _cdt_set_shown(self, code_id: str, shown: bool):
        project = self._cd_project()
        if project is None or not code_id:
            return None
        allv = self.settings.setdefault("timeline_codes", {})
        ids = [i for i in allv.get(str(project)) or [] if i != code_id]
        if shown:
            ids.append(code_id)
        allv[str(project)] = ids
        self._save_settings()
        self._cd_fill_codebook()
        self._cdt_draw()
        return ids

    def _cdt_lane_codes(self, resolved: List[Dict]) -> List[str]:
        """One lane per code shown on the timeline; while none are chosen, the codes used in view (codebook order)."""
        cb = self._cd_codebook()
        if cb is None:
            return []
        comments = [cod.COMMENT] if any(r["code"] == cod.COMMENT for r in resolved) else []  # always, while there are any
        shown = [c for c in self._cdt_shown_codes() if c != cod.COMMENT]
        if shown:
            self.cdt["lane_mode"] = "chosen"
            return (comments + shown)[:MAX_LANES]
        self.cdt["lane_mode"] = "used"
        a, b = self._cdt_view()
        used = {r["code"] for r in resolved if r["end"] >= a and r["start"] <= b and not r.get("orphan")}
        used |= set(self.cdt.get("live") or {})
        return (comments + [c["id"] for _d, c in cb.ordered() if c["id"] in used])[:MAX_LANES]

    def _cdt_rows(self, n_lanes: int) -> Dict[str, Tuple[int, int]]:
        y = 0
        rows = {"ruler": (0, RULER_H)}
        y = RULER_H
        if self._cdt_has_video():
            rows["frames"] = (y + 2, y + 2 + FRAMES_H)
            y += FRAMES_H + 4
        rows["speakers"] = (y + 1, y + 1 + SPEAKERS_H)
        rows["checked"] = (y + SPEAKERS_H + 2, y + SPEAKERS_H + 5)
        y += SPEAKERS_H + 8
        rows["lanes"] = (y, y + max(1, n_lanes) * LANE_H)
        rows["bottom"] = (0, y + max(1, n_lanes) * LANE_H + 4)
        return rows

    def _cdt_items(self) -> List[Tuple]:
        """Everything to draw, as plain shapes (the tests check these):
        ('episode', x0, x1, colour) · ('tick', x, label) · ('speaker', x0, x1, colour) · ('lane', y0, y1, code, name, colour)
        · ('bar', x0, x1, y0, y1, colour, kind, coding_id, selected) · ('live', x0, x1, y0, y1, colour) · ('mark', x0, x1)
        · ('in', x) · ('frame', x0, x1, t)."""
        doc = self.active_doc
        if doc is None:
            self.cdt["hits"], self.cdt["lanes"] = [], []
            return []
        if self.cdt.get("path") != str(doc.path):  # another transcript: its whole recording, nothing marked
            self.cdt.update(view=None, live={}, loop=None, thumbs={}, path=str(doc.path))
            self.cdt["in"] = self.cdt["out"] = None
            self._cdt_show_mark()
        a, b = self._cdt_view()
        x0p, x1p = self._cdt_plot()
        X = self._cdt_xfun()
        cb = self._cd_codebook()
        cd = self.__dict__.get("_cd") or {}
        if cd.get("doc") is doc and self._cd_visible() and cd.get("resolved") is not None:
            resolved = cd["resolved"]           # the Coding tab has just worked them out
        else:
            resolved = cod.resolve(doc)         # e.g. after editing in the Transcript tab: where they are now
        lanes = self._cdt_lane_codes(resolved)
        self.cdt["lanes"] = lanes
        rows = self._cdt_rows(len(lanes))
        self.cdt["rows"] = rows
        items: List[Tuple] = []
        for ep in doc.episodes:
            if ep["end"] >= a and ep["start"] <= b:
                items.append(("episode", max(x0p, X(ep["start"])), min(x1p, max(X(ep["start"]) + 2, X(ep["end"]))),
                              self._episode_color(ep["type"]), bool(ep.get("approx"))))
        for s0, s1 in doc.cuts:                 # cut parts: hatched over everything
            if s1 >= a and s0 <= b:
                items.append(("cut", max(x0p, X(s0)), min(x1p, max(X(s0) + 2, X(s1)))))
        step = tick_step(b - a, x1p - x0p)
        t = (int(a) // step) * step
        while t <= b:
            if t >= a:
                items.append(("tick", X(t), tick_label(t, step)))
            t += step
        if "frames" in rows:
            n = max(1, int((x1p - x0p) // 72))
            w = (x1p - x0p) / n
            span = (b - a) / max(x1p - x0p, 1)
            for k in range(n):
                fx0 = x0p + k * w
                items.append(("frame", fx0, fx0 + w, round(a + (k * w + w / 2) * span, 1)))
        roster = self._roster()
        colors = {spk: SPEAKER_COLORS[i % len(SPEAKER_COLORS)] for i, spk in enumerate(roster)}
        merged: List[List] = []
        checks: List[List] = []                 # segments marked as checked: a green bar under the speakers
        for seg in doc.segments:
            s0, s1 = float(seg.get("start", 0.0)), float(seg.get("end", 0.0))
            if s1 < a or s0 > b:
                continue
            sx0, sx1 = max(x0p, X(s0)), min(x1p, max(X(s0) + 1, X(s1)))
            col = colors.get(seg.get("speaker"), "#64748b")
            if merged and merged[-1][3] == col and sx0 <= merged[-1][2] + 1:
                merged[-1][2] = max(merged[-1][2], sx1)
            else:
                merged.append(["speaker", sx0, sx1, col])
            if seg.get("checked"):
                if checks and sx0 <= checks[-1][2] + 1:
                    checks[-1][2] = max(checks[-1][2], sx1)
                else:
                    checks.append(["checked", sx0, sx1])
        items += [tuple(m) for m in merged] + [tuple(c) for c in checks]
        spans = self.__dict__.get("word_spans") or []
        seen_px = set()
        for i in self.__dict__.get("low_conf") or []:   # words Whisper was unsure of: red ticks over the speakers
            if i < len(spans):
                t_w = float(spans[i]["start"])
                if a <= t_w <= b and int(X(t_w)) not in seen_px:
                    seen_px.add(int(X(t_w)))
                    items.append(("lowconf", X(t_w)))
        ly0 = rows["lanes"][0]
        hits = []
        lane_of = {cid: k for k, cid in enumerate(lanes)}
        for k, cid in enumerate(lanes):
            c = cb.get(cid) if cb else None
            items.append(("lane", ly0 + k * LANE_H, ly0 + (k + 1) * LANE_H, cid, c["name"] if c else "?", c["color"] if c else THEME["fg_dim"]))
        sel = self._cd.get("sel")
        for r in resolved:
            k = lane_of.get(r["code"])
            if k is None or r.get("orphan") or r["end"] < a or r["start"] > b:
                continue
            c = cb.get(r["code"]) if cb else None
            col = c["color"] if c else THEME["fg_dim"]
            bx0, bx1 = max(x0p, X(r["start"])), min(x1p, max(X(r["start"]) + 3, X(r["end"])))
            y0, y1 = ly0 + k * LANE_H + 3, ly0 + (k + 1) * LANE_H - 3
            kind = "time" if r.get("kind") == "time" else "words"
            items.append(("bar", bx0, bx1, y0, y1, col, kind, r["id"], r["id"] == sel))
            hits.append((bx0, y0, bx1, y1, r["id"], kind))
        pos = self._current_pos()
        for cid, start in (self.cdt.get("live") or {}).items():
            k = lane_of.get(cid)
            c = cb.get(cid) if cb else None
            if k is None or c is None:
                continue
            items.append(("live", max(x0p, X(start)), min(x1p, max(X(start) + 2, X(max(pos, start)))), ly0 + k * LANE_H + 3,
                          ly0 + (k + 1) * LANE_H - 3, c["color"]))
        mark = self._cdt_mark()
        if mark:
            items.append(("mark", max(x0p, X(mark[0])), min(x1p, X(mark[1]))))
        elif self.cdt.get("in") is not None:
            items.append(("in", X(self.cdt["in"])))
        self.cdt["hits"] = hits
        return items

    # ================================================================== drawing
    def _cdt_draw(self, request_frames: bool = False):
        cv = self.__dict__.get("cd_timeline")
        if cv is None or self.__dict__.get("cdt") is None:
            return None
        T = THEME
        cv.delete("all")
        items = self._cdt_items()
        rows = self.cdt.get("rows") or self._cdt_rows(0)
        height = rows["bottom"][1]
        try:
            if int(cv.cget("height")) != height:
                cv.configure(height=height)
        except Exception:
            pass
        x0p, x1p = self._cdt_plot()
        f = self.f
        for it in items:
            kind = it[0]
            if kind == "episode":
                approx = len(it) > 4 and it[4]
                cv.create_rectangle(it[1], RULER_H, it[2], height, fill=self._dim(it[3], 0.10 if approx else 0.16), outline="")
                cv.create_rectangle(it[1], RULER_H, it[2], RULER_H + 2, fill=self._dim(it[3], 0.6) if approx else it[3], outline="")
            elif kind == "cut":
                cv.create_rectangle(it[1], RULER_H, it[2], height, fill="#000000", stipple="gray50", outline="#f59e0b")
            elif kind == "checked":
                y0, y1 = rows["checked"]
                cv.create_rectangle(it[1], y0, it[2], y1, fill=T["ok"], outline="")
            elif kind == "lowconf":
                y0, _y1 = rows["speakers"]
                cv.create_line(it[1], y0 - 1, it[1], y0 + 5, fill="#f87171")
            elif kind == "tick":
                cv.create_line(it[1], RULER_H - 5, it[1], height, fill=T["border"])
                cv.create_text(it[1] + 3, 2, anchor="nw", text=it[2], fill=T["fg_dim"], font=f["mono_small"])
            elif kind == "frame":
                y0, y1 = rows["frames"]
                img = self.cdt["thumbs"].get(it[3])
                if isinstance(img, tk.PhotoImage):
                    cv.create_image((it[1] + it[2]) / 2, (y0 + y1) / 2, image=img)
                else:
                    cv.create_rectangle(it[1] + 1, y0, it[2] - 1, y1, fill="#0b0d13", outline=T["border"])
            elif kind == "speaker":
                y0, y1 = rows["speakers"]
                cv.create_rectangle(it[1], y0, it[2], y1, fill=self._dim(it[3]), outline="")
            elif kind == "lane":
                cv.create_line(0, it[1], x1p + 8, it[1], fill=T["border"])
                cv.create_text(6, (it[1] + it[2]) / 2, anchor="w", text=it[4][:18], fill=it[5], font=f["small"])
            elif kind == "bar":
                _, bx0, bx1, y0, y1, col, bkind, _kid, sel = it
                if bkind == "time":
                    cv.create_rectangle(bx0, y0, bx1, y1, fill=self._dim(col, 0.45), outline=T["fg_primary"] if sel else col, width=2 if sel else 1)
                else:
                    cv.create_rectangle(bx0, y0 + 2, bx1, y1 - 2, fill=col, outline=T["fg_primary"] if sel else col, width=2 if sel else 1)
            elif kind == "live":
                cv.create_rectangle(it[1], it[3], it[2], it[4], fill=self._dim(it[5], 0.45), outline=it[5], dash=(3, 2))
            elif kind == "mark":
                cv.create_rectangle(it[1], RULER_H, it[2], height - 1, outline=T["fg_primary"], dash=(4, 2), width=1)
            elif kind == "in":
                cv.create_line(it[1], RULER_H, it[1], height, fill=T["fg_primary"], dash=(4, 2))
        lanes_y = rows["lanes"]
        if not self.cdt.get("lanes"):
            cv.create_text(LABEL_W + 6, (lanes_y[0] + lanes_y[1]) / 2, anchor="w", fill=T["fg_dim"], font=f["small"],
                           text="Drag here to mark a range, then press ↩ or 1–9 to code it")
        cv.create_text(6, 2, anchor="nw", text="", fill=T["fg_dim"])
        if "frames" in rows:
            cv.create_text(6, (rows["frames"][0] + rows["frames"][1]) / 2, anchor="w", text="Video", fill=T["fg_dim"], font=f["small"])
        cv.create_text(6, (rows["speakers"][0] + rows["speakers"][1]) / 2, anchor="w", text="Speakers", fill=T["fg_dim"], font=f["small"])
        drag = self.cdt.get("drag") or {}
        if drag.get("mode") == "edge" and drag.get("t") is not None:
            x = self._cdt_x(drag["t"])
            cv.create_line(x, RULER_H, x, height, fill=T["fg_primary"], width=2)
        self.cdt["playhead"] = cv.create_line(0, 0, 0, height, fill="#f87171", width=2)
        self.cdt["hover_item"] = cv.create_text(0, RULER_H + 2, text="", anchor="nw", fill=T["fg_primary"], font=f["mono_small"])
        self._cdt_playhead()
        if height != self.cdt.get("fit_h"):  # more or fewer lanes: the timeline's height follows (a dragged one stays)
            self.cdt["fit_h"] = height
            self.after_idle(lambda h=height: self._cdt_fit_height(h))
        mode = self.cdt.get("lane_mode")
        self.lbl_cdt_hint.config(text="" if mode == "chosen" or not self.cdt.get("lanes") else "Lanes: codes used here")
        if request_frames:
            self._cdt_request_frames()
        return items

    def _tl_keep(self) -> int:
        """Height the Transcript tab keeps above the timeline: toolbars, player and a few lines of text — in Edit mode
        also the segment editor. On a short screen the timeline gets the rest (at least 110 px: ruler, frames, speakers)."""
        return 500 if self.__dict__.get("tx_mode", "edit") == "edit" else 300

    def _cdt_fit_height(self, height: int):
        """Make room for every lane: the line between the tab and the timeline moves up (to half the tab at most, and
        never so far that the tab's text loses its room — Edit mode needs more, for the segment editor)."""
        area, frame = self.__dict__.get("right_area"), self.__dict__.get("tl_frame")
        if area is None or frame is None or not self.__dict__.get("tl_shown"):
            return None
        try:
            area_h = int(area.winfo_height())
            if area_h < 200:
                return None
            bar_h = int(self.cdt_bar.winfo_reqheight())
            # the tab keeps room for its toolbars and the text — in Edit mode also the segment editor
            want = max(110, min(height + bar_h + 16, area_h // 2, area_h - self._tl_keep()))  # 110: ruler, frames, speakers
            have = int(frame.winfo_height())
            if want > have or want < have - 40:
                area.sash_place(0, 0, max(300, area_h - want))
                return want
        except Exception:
            return None
        return None

    def _cdt_playhead(self, pos: Optional[float] = None):
        cv, ph = self.__dict__.get("cd_timeline"), (self.__dict__.get("cdt") or {}).get("playhead")
        if cv is None or ph is None or self.__dict__.get("_scrub_target") is not None:
            return  # (being dragged: the playhead is under the mouse)
        pos = self._current_pos() if pos is None else pos
        a, b = self._cdt_view()
        x = self._cdt_x(pos) if a <= pos <= b else -10
        h = (self.cdt.get("rows") or {}).get("bottom", (0, 60))[1]
        cv.coords(ph, x, 0, x, h)

    def _cdt_tick(self, pos: float):
        """While playing: the playhead, a zoomed view that follows it, running codings, the loop."""
        if self.__dict__.get("cdt") is None or not self._tl_visible():
            return
        if not self.__dict__.get("playing"):
            self._cdt_playhead(pos)
            return
        loop = self.cdt.get("loop")
        if loop and pos >= loop[1] - 0.05:
            self._player_start(loop[0])
            return
        a, b = self._cdt_view()
        if self.cdt.get("view") and not (a <= pos <= b) and not self.cdt.get("drag"):
            span = b - a
            self._cdt_set_view(pos - span * 0.1, pos + span * 0.9)  # page along with the playback
            return
        if self.cdt.get("live"):
            self._cdt_draw()
        else:
            self._cdt_playhead(pos)

    # ================================================================== frames
    def _cdt_request_frames(self):
        """Small frames for the visible part, grabbed one by one in the background (a quick seek each)."""
        if self.__dict__.get("cdt") is None or not self._cdt_has_video():
            return []
        want = [it[3] for it in self._cdt_items() if it[0] == "frame"]
        missing = [t for t in want if t not in self.cdt["thumbs"]]
        self.cdt["thumb_gen"] += 1
        gen = self.cdt["thumb_gen"]
        if not missing or not shutil.which("ffmpeg"):
            return missing
        media = self._video_media()
        mapped = [(t, self._video_map(t)[0]) for t in missing]
        q = self.cdt["thumb_q"]

        def work():
            for t, vt in mapped:
                if self.cdt.get("thumb_gen") != gen:
                    return
                data = None
                if vt is not None:
                    try:
                        res = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{vt:.2f}", "-i",
                                              str(media), "-an", "-sn", "-frames:v", "1", "-vf", f"scale=-2:{FRAMES_H}",
                                              "-f", "image2pipe", "-vcodec", "ppm", "-"], capture_output=True, timeout=20)
                        data = res.stdout or None
                    except Exception:
                        data = None
                q.put((gen, t, data))

        threading.Thread(target=work, daemon=True).start()
        self.after(150, self._cdt_frames_drain)
        return missing

    def _cdt_frames_drain(self):
        got = False
        try:
            while True:
                gen, t, data = self.cdt["thumb_q"].get_nowait()
                if data:
                    try:
                        self.cdt["thumbs"][t] = tk.PhotoImage(data=data, format="ppm")
                        got = True
                    except Exception:
                        self.cdt["thumbs"][t] = None
                else:
                    self.cdt["thumbs"][t] = None
        except queue.Empty:
            pass
        thumbs = self.cdt["thumbs"]
        while len(thumbs) > 240:  # oldest first
            thumbs.pop(next(iter(thumbs)))
        if got:
            self._cdt_draw()
        want = [it[3] for it in self._cdt_items() if it[0] == "frame"]
        if any(t not in thumbs for t in want):
            self.after(200, self._cdt_frames_drain)

    # ================================================================== the marked range
    def _cdt_mark(self) -> Optional[Tuple[float, float]]:
        cdt = self.__dict__.get("cdt") or {}
        a, b = cdt.get("in"), cdt.get("out")
        if a is None or b is None:
            return None
        a, b = sorted((a, b))
        return (a, b) if b - a >= 0.2 else None

    def _cdt_set_mark(self, a: Optional[float], b: Optional[float]):
        self.cdt["in"], self.cdt["out"] = a, b
        self._cdt_show_mark()
        self._cdt_draw()
        return self._cdt_mark()

    def _cdt_show_mark(self):
        mark = self._cdt_mark()
        lbl = self.__dict__.get("lbl_cdt_mark")
        if lbl is None:
            return
        if mark:
            lbl.config(text=f"Marked {short_ts(mark[0])[:-2]} – {short_ts(mark[1])[:-2]} ({mark[1] - mark[0]:.1f} s): ↩ or 1–9 codes it")
        elif self.cdt.get("in") is not None:
            lbl.config(text=f"From {short_ts(self.cdt['in'])[:-2]} — press O at the end")
        else:
            lbl.config(text="")  # (how to mark: the timeline's tooltip)
        loop = self.cdt.get("loop")
        self.btn_cdt_loop.config(text="⟳ Looping" if loop else "⟳", style=rounded.style_for(self.btn_cdt_loop.master, "SegOn" if loop else "Tool"))

    def _cdt_mark_in(self):
        pos = self._current_pos()
        out = self.cdt.get("out")
        self.cdt["out"] = out if out is not None and out > pos else None
        return self._cdt_set_mark(pos, self.cdt["out"])

    def _cdt_mark_out(self):
        pos = self._current_pos()
        a = self.cdt.get("in")
        if a is None:
            a = max(0.0, pos - 5.0)  # O alone: the last 5 seconds
        return self._cdt_set_mark(a, pos)

    def _cdt_clear_mark(self):
        self.cdt["loop"] = None
        return self._cdt_set_mark(None, None)

    def _cdt_play_mark(self):
        mark = self._cdt_mark()
        if mark is None:
            r = next((r for r in self._cd.get("resolved") or [] if r["id"] == self._cd.get("sel")), None)
            mark = (r["start"], r["end"]) if r else None
        if mark is None:
            self.lbl_status.config(text="Mark a range on the timeline first (drag, or I and O).")
            return None
        self._player_start(max(0.0, mark[0]), max(0.5, mark[1] - mark[0]))
        return mark

    def _cdt_toggle_loop(self):
        """Play the marked range (or the selected coding) over and over, until L again."""
        if self.cdt.get("loop"):
            self.cdt["loop"] = None
            self._cdt_show_mark()
            if self.__dict__.get("playing"):
                self._toggle_play()
            return None
        mark = self._cdt_mark()
        if mark is None:
            r = next((r for r in self._cd.get("resolved") or [] if r["id"] == self._cd.get("sel")), None)
            mark = (r["start"], r["end"]) if r else None
        if mark is None:
            self.lbl_status.config(text="Mark a range (or select a coding) to loop it.")
            return None
        self.cdt["loop"] = mark
        self._cdt_show_mark()
        self._player_start(mark[0])
        return mark

    def _cdt_code_mark(self, code_id: str, memo: str = "") -> Optional[str]:
        """Code the marked range with a code: a time coding (it doesn't need the transcript's words)."""
        doc, cb = self._cd_current(), self._cd_codebook()
        mark = self._cdt_mark()
        if doc is None or cb is None or mark is None or cb.get(code_id) is None:
            return None
        kid = cod.add_coding(doc, code_id, mark[0], mark[1], memo=memo)
        self._cd_commit(f"Coded “{cb.get(code_id)['name']}”: {short_ts(mark[0])[:-2]} – {short_ts(mark[1])[:-2]} (by time)")
        self._cd_count(code_id, +1)
        self._cd_use_recent(code_id)
        if self.cdt.get("lane_mode") == "chosen" and code_id not in self._cdt_shown_codes():
            self._cdt_set_shown(code_id, True)  # a code used on the timeline gets its lane
        self.cdt["loop"] = None
        self.cdt["in"] = self.cdt["out"] = None
        self._cdt_show_mark()
        self._cd_render(doc)
        self._cd_fill_codebook()
        self._cd_select_coding(kid)
        return kid

    # ================================================================== coding while watching
    def _cdt_live_toggle(self, code_id: str) -> Optional[str]:
        """While the video plays: the first press starts a coding at the playhead, the second ends it there."""
        cb = self._cd_codebook()
        if cb is None or cb.get(code_id) is None:
            return None
        live = self.cdt.setdefault("live", {})
        pos = self._current_pos()
        name = cb.get(code_id)["name"]
        if code_id not in live:
            live[code_id] = pos
            self.lbl_status.config(text=f"● “{name}” from {short_ts(pos)[:-2]} — press the same key again to end it.")
            self._cdt_draw()
            return "started"
        start = live.pop(code_id)
        if pos - start < 0.3:
            self._cdt_draw()
            return None
        self.cdt["in"], self.cdt["out"] = start, pos
        return self._cdt_code_mark(code_id)

    # ================================================================== mouse
    def _cdt_hit(self, x: float, y: float) -> Optional[Tuple[str, str, Optional[str]]]:
        """(coding id, kind, 'start'/'end' if on an edge else None) under the mouse."""
        best = None
        for x0, y0, x1, y1, kid, kind in self.cdt.get("hits") or []:
            if y0 - 2 <= y <= y1 + 2 and x0 - EDGE_PX <= x <= x1 + EDGE_PX:
                edge = "start" if abs(x - x0) <= EDGE_PX else "end" if abs(x - x1) <= EDGE_PX else None
                if x1 - x0 < 3 * EDGE_PX:
                    edge = None if x0 <= x <= x1 else edge
                cand = (x1 - x0, kid, kind, edge)
                if best is None or cand[0] < best[0]:
                    best = cand
        return (best[1], best[2], best[3]) if best else None

    def _cdt_press(self, event):
        try:
            self.cd_timeline.focus_set()
        except Exception:
            pass
        if self.active_doc is None:
            return None
        whole = self.cdt.get("view") is None
        if event.y < RULER_H and not whole:
            self.cdt["drag"] = {"mode": "pan", "x": event.x, "view": self._cdt_view(), "moved": False}
            return "pan"
        hit = self._cdt_hit(event.x, event.y) if event.x >= LABEL_W else None
        if hit and hit[2]:
            self.cdt["drag"] = {"mode": "edge", "kid": hit[0], "edge": hit[2], "t": None}
            return "edge"
        # scrub: grab the playhead, or the ruler when the whole recording is shown (nothing to pan) — the playhead
        # follows the mouse and Condense jumps once; dragging anywhere else still marks a range to code
        near_playhead = event.x >= LABEL_W and abs(event.x - self._cdt_x(self._current_pos())) <= 6
        if event.y < RULER_H or near_playhead:
            self.cdt["drag"] = {"mode": "scrub", "x": event.x, "moved": False}
            return "scrub"
        self.cdt["drag"] = {"mode": "range", "t0": self._cdt_t(event.x), "x": event.x, "kid": hit[0] if hit else None, "moved": False}
        return "range"

    def _cdt_motion(self, event):
        d = self.cdt.get("drag")
        if not d:
            return None
        if d["mode"] == "pan":
            a, b = d["view"]
            x0, x1 = self._cdt_plot()
            dt = (event.x - d["x"]) / max(x1 - x0, 1) * (b - a)
            d["moved"] = d["moved"] or abs(event.x - d["x"]) > 3
            self.cdt["view"] = None
            self._cdt_set_view(a - dt, b - dt)
            self.cdt["drag"] = d
        elif d["mode"] == "edge":
            d["t"] = self._cdt_t(event.x)
            self._cdt_draw()
        elif d["mode"] == "scrub":
            d["moved"] = d["moved"] or abs(event.x - d["x"]) > 3
            self._cdt_scrub_to(self._cdt_t(event.x))
        else:
            if abs(event.x - d["x"]) > 3:
                d["moved"] = True
                self.cdt["in"], self.cdt["out"] = d["t0"], self._cdt_t(event.x)
                self._cdt_show_mark()
                self._cdt_draw()
        return d["mode"]

    def _cdt_release(self, event):
        d = self.cdt.get("drag")
        self.cdt["drag"] = None
        if not d:
            return None
        if d["mode"] == "pan":
            if not d["moved"]:
                self._cdt_jump(self._cdt_t(event.x))
            self._cdt_draw(request_frames=True)
            return "pan"
        if d["mode"] == "edge":
            t = self._cdt_t(event.x)
            return self._cdt_move_edge(d["kid"], d["edge"], t)
        if d["mode"] == "scrub":
            job = self.__dict__.get("_scrub_job")
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
            self._scrub_job = self._scrub_target = None
            return self._cdt_jump(self._cdt_t(event.x))
        if not d["moved"]:  # a click: select the coding there, or jump
            if d.get("kid"):
                self._cd_select_coding(d["kid"])
                self._cdt_draw()
                return d["kid"]
            self._cdt_jump(self._cdt_t(event.x))
            return "jump"
        self.cdt["in"], self.cdt["out"] = d["t0"], self._cdt_t(event.x)
        self._cdt_show_mark()
        self._cdt_draw()
        return self._cdt_mark()

    def _cdt_scrub_to(self, t: float):
        """While dragging: only the playhead and the time move; the jump (text, video frame, playback) waits until the
        mouse rests or is released — a drag over hours doesn't start dozens of ffmpeg/ffplay processes."""
        self._scrub_target = t
        cv, ph = self.__dict__.get("cd_timeline"), self.cdt.get("playhead")
        if cv is not None and ph is not None:
            x = self._cdt_x(t)
            cv.coords(ph, x, 0, x, (self.cdt.get("rows") or {}).get("bottom", (0, 60))[1])
        try:
            self.lbl_time.configure(text=f"{short_ts(t)[:-2]} / {short_ts(self._duration())[:-2]}")
        except Exception:
            pass
        job = self.__dict__.get("_scrub_job")
        if job is not None:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._scrub_job = self.after(180, self._timeline_settle)
        return t

    def _cdt_double(self, event):
        hit = self._cdt_hit(event.x, event.y)
        if hit:
            return self._cd_play_coding(hit[0])
        return None

    def _cdt_hover(self, event):
        cv, item = self.__dict__.get("cd_timeline"), (self.__dict__.get("cdt") or {}).get("hover_item")
        if cv is None or item is None:
            return
        if event is None or event.x < LABEL_W or self.active_doc is None:
            cv.itemconfigure(item, text="")
            return
        t = self._cdt_t(event.x)
        x0, x1 = self._cdt_plot()
        left = event.x > x1 - 80
        cv.itemconfigure(item, text=short_ts(t)[:-2], anchor="ne" if left else "nw")
        cv.coords(item, event.x - 6 if left else event.x + 6, RULER_H + 1)
        hit = self._cdt_hit(event.x, event.y)
        try:
            cv.configure(cursor="sb_h_double_arrow" if hit and hit[2] else "hand2" if hit else "crosshair")
        except Exception:
            pass

    def _cdt_jump(self, t: float):
        self._timeline_jump(t)
        self._cd_follow(t)
        self._cdt_playhead(t)
        return t

    def _cdt_move_edge(self, kid: str, edge: str, t: float) -> Optional[str]:
        doc = self._cd_current()
        c = cod.get_coding(doc, kid) if doc is not None else None
        r = next((r for r in self._cd.get("resolved") or [] if r["id"] == kid), None)
        if c is None or r is None:
            self._cdt_draw()
            return None
        start, end = (t, r["end"]) if edge == "start" else (r["start"], t)
        if not cod.set_coding_span(doc, kid, start, end):
            self._cdt_draw()
            return None
        self._cd_commit(f"Coding moved: {short_ts(min(start, end))[:-2]} – {short_ts(max(start, end))[:-2]}")
        self._cd_render(doc) if c.get("kind") == "time" else self._cd_refresh_codings(doc)
        self._cd_select_coding(kid)
        return kid

    def _cdt_menu(self, event):
        hit = self._cdt_hit(event.x, event.y) if event.x >= LABEL_W else None
        m = PopupMenu(self)
        cb = self._cd_codebook()
        if hit:
            kid, kind, _edge = hit
            self._cd_select_coding(kid)
            m.add_command(label="▶ Play", command=lambda: self._cd_play_coding(kid))
            m.add_command(label="⟳ Loop", command=lambda: (self._cdt_clear_mark(), self._cdt_toggle_loop()))
            if kid and (cod.get_coding(self.active_doc, kid) or {}).get("code") == cod.COMMENT:
                m.add_command(label="Edit comment…", command=lambda: self._comment_dialog(kid))
                m.add_command(label="Code it (turn the comment into a coding)…", command=lambda: self._cd_change_code(kid))
            else:
                m.add_command(label="Memo…", command=lambda: self._cd_memo(kid))
                m.add_command(label="Change code…", command=lambda: self._cd_change_code(kid))
            if kind == "time":
                m.add_command(label="Attach to the words said in it", command=lambda: self._cdt_attach(kid))
            else:
                m.add_command(label="Keep by time only (not tied to the words)", command=lambda: self._cdt_detach(kid))
            m.add_separator()
            m.add_command(label="Delete coding", command=lambda: self._cd_remove(kid))
        else:
            mark = self._cdt_mark()
            code = self._cd_selected_code()
            if mark:
                if code and cb and cb.get(code):
                    m.add_command(label=f"Code with “{cb.get(code)['name']}”", command=lambda: self._cdt_code_mark(code))
                m.add_command(label="New code for the marked range…", command=lambda: self._cd_new_code(parent=code, apply=True))
                for k, cid in enumerate(self._cd["recent"][:9]):
                    if cb and cb.get(cid):
                        m.add_command(label=f"{k + 1}  {cb.get(cid)['name']}", command=lambda cid=cid: self._cdt_code_mark(cid))
                m.add_command(label="Code with a description…", command=lambda: self._cd_time_dialog(*mark))
                m.add_command(label="✎ Comment on the marked range…  (M)", command=lambda: self._comment_dialog())
                m.add_separator()
                m.add_command(label="▶ Play the marked range", command=self._cdt_play_mark)
                m.add_command(label="Clear the mark", command=self._cdt_clear_mark)
                m.add_separator()
            t = self._cdt_t(event.x)
            bm = self._comment_minutes() * 60
            ba = int(t // bm) * bm
            m.add_command(label=f"✎ Comment on this {bm // 60}-minute block ({short_ts(ba)[:-2]} – "
                                f"{short_ts(min(ba + bm, self._duration()))[:-2]})…", command=lambda: self._comment_on_block(t))
            m.add_command(label=f"Mark from here ({short_ts(t)[:-2]})", command=lambda: self._cdt_set_mark(t, self.cdt.get("out")))
            m.add_command(label="Zoom in here", command=lambda: self._cdt_zoom_at(t, 0.5))
            m.add_command(label="Zoom out", command=lambda: self._cdt_zoom_at(t, 2.0))
            m.add_command(label="Whole recording", command=lambda: self._cdt_zoom("whole"))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return m

    def _cdt_attach(self, kid: str) -> bool:
        doc = self._cd_current()
        if doc is None or not cod.attach_to_words(doc, kid):
            self.lbl_status.config(text="No words in that stretch — it stays a time coding.")
            return False
        self._cd_commit("Time coding attached to its words")
        self._cd_render(doc)
        self._cd_select_coding(kid)
        return True

    def _cdt_detach(self, kid: str) -> bool:
        doc = self._cd_current()
        if doc is None or not cod.detach_from_words(doc, kid):
            return False
        self._cd_commit("Coding kept by time only")
        self._cd_render(doc)
        self._cd_select_coding(kid)
        return True

    # ================================================================== keys (from _cd_key)
    def _cdt_key(self, k: str) -> bool:
        """Timeline keys in the Coding tab. True if handled."""
        if k in ("i", "I"):
            self._cdt_mark_in()
        elif k in ("o", "O"):
            self._cdt_mark_out()
        elif k in ("l", "L"):
            self._cdt_toggle_loop()
        elif k in ("x", "X"):
            self._cdt_clear_mark()
        elif k in ("m", "M"):
            self._comment_dialog()
        elif k in ("comma", "period", "less", "greater"):
            step = {"comma": -FRAME_STEP, "period": FRAME_STEP, "less": -1.0, "greater": 1.0}[k]
            if self.__dict__.get("playing"):
                self._toggle_play()
            self._cdt_jump(max(0.0, min(self._cdt_duration(), self._current_pos() + step)))
        else:
            return False
        return True
