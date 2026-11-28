import os
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.environ["CONDENSE_TESTS"])
import stub_tk2
HOME = Path(tempfile.mkdtemp(prefix="home_")); (HOME / "Desktop").mkdir(); os.environ["HOME"] = str(HOME)
from _compat import pipe
from condense.gui.find import build_regex, find_in_document, replace_in_document, segment_text
ok = lambda m: print("  ✓", m)
TD = pipe.TranscriptDocument
media = Path(os.environ["CONDENSE_TEST_MEDIA"])

def seg(t, text, spk, prob=0.95):
    ws = text.split()
    return {"start": t, "end": t + len(ws) * 0.5, "text": " " + text, "speaker": spk,
            "words": [{"word": " " + w, "start": t + i * 0.5, "end": t + i * 0.5 + 0.4, "probability": prob} for i, w in enumerate(ws)]}

study = Path(tempfile.mkdtemp(prefix="study_"))
def make(name, segs):
    d = study / name; d.mkdir()
    doc = TD.create(d, name, {"segments": segs}, "small", {}, {}, {"playback": str(media / "P02.mp4")}, {"inputs": []})
    doc.save(); doc.export_all(); return doc

d1 = make("Session 1", [seg(0, "We meet at the Riverside club today.", "Robin"), seg(4, "The riverside club is near the park.", "Sam"),
                        seg(8, "I like riversides.", "Sam", prob=0.3), seg(10, "Let us start drawing.", "Robin")])
d2 = make("Session 2", [seg(0, "Back at the Riverside club again.", "Robin"), seg(4, "Nothing else to say.", "Kim")])

print("[1] find / replace helpers")
rx = build_regex("riverside club", match_case=False, whole_words=True)
assert [i for i, _ in find_in_document(d1, rx)] == [0, 1]
assert not build_regex("riverside", False, True).search("I like riversides.")       # whole words
assert build_regex("Riverside", True, False).search("the riverside") is None         # match case
assert build_regex("  ", False, False) is None
ok("phrases, whole words, match case")

holder = {}
stub_tk2.tk.Tk.mainloop = lambda self: holder.setdefault("app", self)
pipe.launch_gui(); app = holder["app"]
app._render_doc(TD.load(d1.path))
pipe.messagebox.askyesno = lambda *a, **k: True

print("[2] notes on segments: editor, view, exports, undo")
app._goto_segment(0)
chips_before = list(app.spk_chips._items)
app._goto_segment(1)
assert app.spk_chips._items == chips_before, "the speaker chips were built again for the next segment"  # (only recoloured)
assert not app._note_shown  # no note: no note line
app._open_note()
assert app._note_shown
app.var_seg_note.set("check spelling of the club's name with the school")
assert app._editor_dirty()
app._save_segment_edit()
doc = TD.load(d1.path)
assert doc.segments[1]["note"] == "check spelling of the club's name with the school"
assert "NOTE" in app.preview_text.used_tags and "✎ check spelling" in app.preview_text.content
txt = (study / "Session 1" / "Session 1.txt").read_text()
assert "near the park. [Note: check spelling of the club's name with the school]" in txt
assert "[Note: check spelling" in (study / "Session 1" / "Session 1_paragraphs.rtf").read_text()
app._goto_segment(0)
assert not app._note_shown
app._goto_segment(1)
assert app.var_seg_note.get().startswith("check spelling") and app._note_shown  # a segment with a note shows it
app.var_seg_note.set(""); app._save_segment_edit()
assert "note" not in TD.load(d1.path).segments[1]
app._undo()
assert TD.load(d1.path).segments[1]["note"].startswith("check spelling")
ok("note saved with the segment, shown with ✎, exported as [Note: …] (TXT, paragraphs), cleared, undone")

print("[3] show filter")
app.var_show_filter.set("Uncertain"); app._rerender()
assert sorted(app.seg_ranges) == [2] and "showing 1 uncertain" in app.lbl_ci_summary.cget("text")
app.var_show_filter.set("With notes"); app._rerender()
assert sorted(app.seg_ranges) == [1]
d = TD.load(d1.path); d.set_checked(0, True); d.save(); app._render_doc(TD.load(d1.path))
app.var_show_filter.set("Not checked"); app._rerender()
assert sorted(app.seg_ranges) == [1, 2, 3]
app._goto_segment(1); app._move_segment(+1)
assert app.edit_seg_idx == 2                                    # ↓ moves within the filtered list
app.var_show_filter.set("All segments"); app._rerender()
assert sorted(app.seg_ranges) == [0, 1, 2, 3]
ok("Uncertain / With notes / Not checked show only those segments; ↓ stays inside the filter")

print("[4] find & replace in the open transcript")
app._toggle_find()
app.var_find.set("riverside club"); app.var_find_words.set(True); app._paint_found()  # real Tk runs this from the variable trace
assert app.lbl_find_count.cget("text") == "2 in 2 segment(s)" and "FOUND" in app.preview_text.tags
app._goto_segment(3)
app._find_step(+1); assert app.edit_seg_idx == 0              # wraps around
app._find_step(+1); assert app.edit_seg_idx == 1
app.var_replace.set("Riverside Club")
app._replace_current()
assert segment_text(TD.load(d1.path).segments[1]) == "The Riverside Club is near the park."
app._replace_all()
doc = TD.load(d1.path)
assert segment_text(doc.segments[0]) == "We meet at the Riverside Club today." and segment_text(doc.segments[2]) == "I like riversides."
words = {x["word"].strip(): x for x in doc.segments[0]["words"]}
assert words["Club"].get("edited") and not words["Riverside"].get("edited")             # only the changed word
assert [x["start"] for x in doc.segments[0]["words"]] == [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]  # timings kept
app._undo()
assert segment_text(TD.load(d1.path).segments[0]) == "We meet at the Riverside club today."
app._undo()
assert segment_text(TD.load(d1.path).segments[1]) == "The riverside club is near the park."
app._hide_find()
ok("count, ◀/▶ with wrap-around, Replace, Replace all (one undo step each), word timings kept")

print("[5] search and replace across all transcripts in a folder")
win, st = app._search_all_dialog()
st["v_dir"].set(str(study)); st["v_q"].set("riverside club"); st["v_r"].set("Riverside Club")
res = st["search"]()
assert len(res) == 3 and {r["path"].name for r in res} == {"Session 1.transcript.json", "Session 2.transcript.json"}
st["lst"].sel = (2,)
st["open"]()
assert Path(app.active_doc.path).name == "Session 2.transcript.json" and app.edit_seg_idx == 0
st["replace"]()
d2n = TD.load(d2.path)
assert segment_text(d2n.segments[0]) == "Back at the Riverside Club again." and "Riverside Club" in (study / "Session 2" / "Session 2.txt").read_text()
assert d2n.data["edit_history"][-1]["action"] == "replace_in_all_transcripts"
assert segment_text(TD.load(d1.path).segments[1]) == "The Riverside Club is near the park."
assert segment_text(app.active_doc.segments[0]) == "Back at the Riverside Club again."      # open transcript reloaded
app._undo()
assert segment_text(TD.load(d2.path).segments[0]) == "Back at the Riverside club again."   # undoable in the open one
ok("finds in every transcript, opens a hit at its segment, replaces everywhere with logs + exports, undo in the open one")
