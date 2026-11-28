# Changelog

## 0.30.2 — 2026-11-28

- **↑ / ↓ through segments is smooth again:** the speaker chips are no longer built anew for every segment (they
  blinked and, held down, lagged) — only their colours change; the row of buttons above them stays put.
- **The video runs down to the timeline;** the segment editor sits under the transcript, as wide as it.
- **The transcript keeps the keys:** clicking ⟲ / ⟳, ▶, *Step ▾*, the switches or ✓ no longer takes the keyboard
  away from it (↑/↓ and Return stopped working); a choice in *Paragraphs* / *Show*, a typed
  speed and the pop-up menus give it back; tooltips can't take it on the Mac.
- **The note is there when you want it:** **N** (or *⋯ ▸ Note…*) opens the note line; segments with a note show it,
  the others don't take the room.

## 0.30.1 — 2026-11-28

### Calmer still
- **Rounded buttons** everywhere (quiet, red, the play button, the Code | Edit and zoom switches), drawn smooth on any
  background; the switches show the chosen part in a pill. **The speed slider** is a thin line with a small round knob.
- **Shortcuts on hover:** buttons say only what they do ("Merge", "Save & next", "Code selection"); their key shows in a
  tooltip.
- **The segment editor in one row:** the segment, the clicked word, then ✓ (green when checked), Split, Merge, Insert,
  Delete, **⋯** (Save, Revert, Re-transcribe, markers) and Save & next. The speaker box is gone: the chips under it set
  the speaker and show it (filled), without outlines. The timing hint is a tooltip on the text box; only what matters
  about a segment (re-transcribed, Whisper wrote something else) still shows under it.
- **The transcript:** speaker and times above a paragraph are small and quiet; checked segments have a thin green bar
  in the margin instead of a ✓ in the text. One info line above it; messages such as "Resumed where you left off" are
  in the status line.
- **Code mode:** the recent codes are at the end of the code bar (one row); the codebook's buttons on one row with ⋯
  and a "Search codes" hint; the codings list fits its pane, with light headings.
- **Tasks:** the list shows the name with a status dot and how far it is — video, steps and stage on hover. A task that
  ran shows its details as plain text (no greyed-out boxes and buttons); the settings fold to one line (click for
  all), the output folder shows its last parts (all of it on hover).
- **Header:** a dot and "GPU ready" (or what is wrong) instead of the hardware list, which is on hover and in Setup &
  Status (a click opens it).
- **One heading style** (Tasks, Codebook, Codings, Timeline, Settings cards); the speed is no longer repeated after the
  time.

## 0.29.0 — 2026-11-28

### A calmer, sleeker window
- **Player:** ⟲ back · ▶ · forward ⟳ by a step you choose once (*Step ▾*: 5, 10, 15 or 30 s, remembered); ⌘[ ⌘]
  (Ctrl+[ Ctrl+]) jump one step, with ⇧ three. The play button is small and the only red one there.
- **Toolbars on one line:** what doesn't fit in a narrow window goes into a **⋯** menu at the row's end, instead of a
  second row (Transcript, Code mode, timeline, tasks; the tasks' ⋯ also holds the task actions).
- **Quiet buttons:** soft, borderless; red only for the main action of a place (Run Pending Tasks, + Videos,
  Save & next). *Code | Edit* and the timeline's *Whole · Episode · 10 min · 2 min* are switches.
- **Tabs underlined**, panels and lists without outlines, thin scrollbars without arrows, a slim progress bar and
  status line.
- **Timeline bar as one strip:** zoom switch, then ▶ ⟳ ✕ (with tooltips); hints only where they help.
- **Info line:** shorter and calmer; the text size is a small *Aa 100 %* — click it for larger, smaller or default
  (also *View ▸*, ⌘⌥+ / ⌘⌥−).

### Fixed
- **Giving a segment the speaker above could send the transcript to its end.** When a word ended up cut off at the
  bottom edge, the view was moved by that cut-off height (a pixel or two) instead of a text line. It now steps by
  whole lines and takes back a step that goes past the screen.

## 0.28.1 — 2026-11-27

- **Re-transcribing or translating a passage on a Mac uses the GPU (MLX) again** for transcripts made on a Windows or
  Linux computer. The re-run took the backend recorded in the transcript ("PyTorch GPU"), which a Mac doesn't have, so
  it ran on the CPU; now the transcript's backend is used only when this computer has it, else this computer's own.
- On a Mac, the message for that case names MLX instead of ROCm/CUDA.

## 0.28.0 — 2026-11-27

### Checked interview transcripts into the session
- **Use the clips' transcripts here** (*Episodes ▸ Find Interview Clips in Recording…*): interviews cut out of a session
  before and transcribed and checked on their own bring their transcripts into the session, at the place found by
  their sound. Text, speakers, checked marks, notes, codings and comments replace the session's stretch (also checked
  segments); session segments over the edges are cut there at word level. One undo step. Speakers new to the session
  are added to it.
- **Linked from then on:** every change of the session in that stretch — text, speakers, checked, codings, comments,
  and undo — is written into the clip's transcript too. A clip changed on its own is not overwritten (the status line
  and the window say so): take it over again, or *Write the session into the clips*.
- The clip's place is the one found by sound: moving the episode's edges later doesn't shift what is written into it.

## 0.27.0 — 2026-11-27

### Name recordings by a pattern
- **Project ▸ Name Recordings by Pattern…**: names that say what a recording is — `final video.mp4` in
  *Day 3 2026-08-12 / Group 4* becomes `G4_Day3_2026.08.12_Session.mp4` — only when you ask for it. A pattern for
  sessions (`G{group}_Day{day}_{date}_{type}{part}` by default) and one for interviews; `{date}` (yyyy.mm.dd) from the
  folder names, else the video's recording date.
- Split recordings get `_part1`, `_part2` …; a video merged in Condense keeps the plain name and its parts are numbered
  in the order they were merged.
- A preview first: leave recordings out, write a name yourself; missing dates, clashes and names that are already right
  are shown. The recording's results folder, transcript, backups, copies (compressed, trimmed, MAXQDA) and exports go
  along, and every link in the project's transcripts is updated. **Undo the last renaming** puts it all back.
- Optionally, new interview clips are named by the new pattern too (the old names stay recognised for numbering);
  `{date}` can be part of a clip name.
- Fixed: the project overview could give a merged video's transcript to one of its parts.

### Steady view
- **The transcript no longer shifts when you give a segment a speaker** (or merge, split, cut): the first line on
  screen stays where it is, as in a document editor, and what changed moves below it (a sentence given to the
  speaker above joins that paragraph). Before, the view kept the clicked word in place, so everything above it slid
  down by a speaker header each time, and a small error added up until the selection left the screen. The view only
  follows the open segment when it would otherwise be out of sight. The same in Code mode.

## 0.26.0 — 2026-11-27

### Comments and commentary over time
- **Comments:** a note on a passage or a stretch of the recording, without a code — e.g. a description of what the
  participants do every 5 minutes. On selected words (Code mode), selected segments (Edit mode), a range marked on the
  timeline, or a whole block (right-click the timeline). **M** in Code mode and on the timeline, **⌘K** / **Ctrl+Shift+K**
  anywhere, *✎ Comment* in the Code toolbar, right-click in both modes. Paragraphs are kept.
- They follow their words through edits like codings, have a *✎ Comments* lane on the timeline (in both modes), a
  stripe in Code mode and a row in the codings list; edit, delete, undo, or turn one into a coding later.
- **Commentary over time** (*Transcript ▾*, *Project ▸ Commentary over Time*): comments, coding memos and segment
  notes as a spreadsheet, in blocks of 1–30 minutes (5 by default). Every block is a row, also empty ones, with one
  video frame from its middle; each comment sits in the block where it starts, with its start, end, speakers and
  passage. For one transcript or the whole project (one sheet, with Day, Group, Type and attributes; optionally a sheet
  per transcript). Excel with frames, or CSV.
- New dependencies, installed by the installer: openpyxl (MIT) and Pillow (MIT-CMU), for the spreadsheet and its
  pictures. Without them (an older installation) the export offers CSV.
- Memos of codings keep their line breaks.

## 0.25.0 — 2026-11-26

0.24.0 was not released on its own: everything below up to 0.23.0 is in this release.

### One workspace: Code and Edit mode
- **The Coding tab is now Code mode of the Transcript tab.** *Code | Edit* at the left of the toolbar, or ⌘E / Ctrl+E,
  switches; ⌘3 opens Edit mode, ⌘4 Code mode. One transcript, one player, one video and one timeline for both, so
  a mistake noticed while coding is fixed without changing tabs: click the word, ⌘E, fix it, ⌘E — you are back where
  you were. The mode you used last is kept.
- **Code mode:** the codebook on the left, the transcript with its stripes, the codings under it, the coding toolbar
  and the recent codes (1–9) in place of the review toolbar.
- **Edit mode:** as the Transcript tab was: the segment editor, speakers, checked, cuts, episodes, Find (which opens
  Edit mode).
- **Speakers in both modes:** ⌃1–9 (Mac) / Alt+1–9 give the speaker to what is selected in the mode you see — in Code
  mode the segments of the selected words, or of the word you clicked. Before, these keys in the Coding tab changed the
  segment that was selected in the (hidden) Transcript tab.
- The video has one place in the tab instead of a column in each tab.

### One timeline
- **The Transcript tab and the Coding tab share one timeline**, under both tabs: frames of the video, speakers,
  episodes, the codes' lanes and the zoom — and, from the Transcript tab's old strip, uncertain words (red ticks),
  checked segments (a green bar) and cut parts (hatched). It is built once and drawn for the tab that is open, so
  switching tabs no longer loads a second timeline; Settings and Console don't show it.
- **Scrubbing:** drag the playhead, or the ruler when the whole recording is shown; the playhead follows and Condense
  jumps once, when the mouse rests or is let go. Dragging anywhere else marks a range to code, as in the Coding tab. A click jumps; ⌘J / Ctrl+J still goes to a typed time.
- **Codings stay where they are after editing in the Transcript tab:** the timeline places them by the transcript as
  it is now, not by what the Coding tab showed last.
- Mark a range and code it by time (I / O, then ↩ or 1–9) from the Transcript tab too.

### Smaller videos: AV1
- **A goal instead of encoder settings** (Settings ▸ Video): *Small: AV1, up to 1080p* is the new default. Camera files
  get several times smaller (often a quarter of the size or less) with the picture as before. Before, the
  default quality was close to lossless for the GPU encoders and the resolution was kept, so copies often came out as
  large as the original, or larger.
- **The best AV1 encoder of the computer:** the GPU on AMD RX 7000 / Intel Arc (VA-API) and recent NVIDIA / AMD / Intel
  cards on Windows, otherwise SVT-AV1 on the CPU (Macs have no AV1 encoder, M5 included). If AMD's encoder pads 1080p
  to 1082 lines (a known driver issue), Condense switches to the CPU.
- **Samples first:** a few short samples estimate the size; with VMAF in ffmpeg they also find the smallest setting that
  still looks the same (within a safe range). Without VMAF, the usual setting for "looks the same" is used — SSIM is not
  used to choose, because on grainy camera footage it rates a blurred copy almost as well as a good one.
- **Never larger:** if a copy would not be clearly smaller (or comes out that way), none is kept and the original is
  used. "1080p" limits the short side, so phone videos in portrait stay 1080×1920. Sound: AAC 128 kbit/s.
- *Compatible: H.264 MP4* for files that play everywhere; *Custom* keeps the encoder settings as before (and tasks saved
  before this version keep theirs).

### Long sessions: coding without waiting
Measured with a 5-hour session (2,300 segments, 600 codings) on a Mac, in the real app:
- **The Coding tab opens in half a second** instead of 19 seconds; coding words, coding by time, changing a code or
  deleting a coding take about half a second instead of 4–6, undo under a second instead of 5, and showing the whole
  recording on the timeline 0.15 instead of 13 seconds. The cause: the timeline worked out the recording's length again
  for every shape it drew — thousands of times, each going through every segment.
- **Coding words doesn't lay out the transcript again** (only highlights, list, stripes and timeline change).
- **The project's code counts are counted in the background**, from the overview's cache (only transcripts that changed
  are read), so the Coding tab no longer waits for every transcript of the study to be read.
- The project's settings and folder are looked up once, not for every episode drawn (slow on network drives); saving no
  longer reads the whole file back first; the video caption doesn't check the disk for every frame.
- **Smaller transcript files:** one segment per line (with its words) instead of one line per word — 40 % smaller,
  quicker to save and back up. They open as before, in Condense and any JSON reader.
- Video playback was measured too: 15 frames/s with the window staying responsive, in the tab and popped out.

### Fixed
- **The video window can go to another screen.** On macOS it disappeared when dragged to a second display: like every
  window, it was tied to the main window, and macOS keeps such windows on their parent's screen.

### MAXQDA
- **Copy for MAXQDA (H.264 MP4)** (Transcript ▾, or right-click transcripts in the Project tab): MAXQDA recommends
  H.264 and may not play AV1. 720p (MAXQDA's advice) or 1080p, timed like the transcript, next to it as
  `<name>_MAXQDA.mp4`; optional, and can be made again any time. Clips exported with *Exact* are H.264 MP4 already.

## 0.23.0 — 2026-11-25

### Platforms
- **Linux with an AMD GPU is now a main platform**, next to macOS on Apple Silicon. NVIDIA, CPU-only Linux and Windows
  stay a preview.

### Coding video on a timeline
- **A real timeline in the Coding tab**, under the transcript and the video: a ruler, frames of the video, who speaks,
  the episodes, and one lane per code (time codings outlined, codings of words solid). Its height can be dragged.
- **Zoom** to the whole recording, the episode at the playhead, or 10 / 2 minutes around it; the mouse wheel zooms where
  the mouse is, Shift+wheel or dragging the ruler moves along, a click jumps there, and it pages along while playing.
- **Code by time without a dialog:** drag a range (or I and O at the playhead), then Return, 1–9 or N — like words.
  Works before the transcript is checked, and for what happens without words.
- **Coding while watching:** with nothing marked, 1–9 starts a coding at the playhead and the same key ends it.
- **Drag a bar's edge** to change a coding (codings of words take the words at the new place). Right-click a bar:
  play, loop, memo, change code, delete, **attach to the words said in it** (or keep by time only).
- **Lanes for the codes you choose** (codebook: right-click ▸ Show on the timeline, marked ◉), like activated codes in
  MAXQDA; until you choose, the codes used in view.
- **Watching closely:** L loops the marked range or a coding, . and , step a frame, > and < a second, X clears the mark;
  *⇔ Video size* gives the video more than half of the tab.

### More room
- **Hide the Tasks / Project panel** (⌘B / Ctrl+B, View menu, or ◂ next to the Tasks tab): it becomes a strip at the
  left, and the Transcript and Coding tabs get the whole width. Click the strip to bring it back; remembered.

### Speakers
- **Detect speakers in a highlighted passage:** right-click ▸ *Detect speakers in this passage…*. Only those segments
  get new speakers, matched to the names already used there.

### Tests
- The playback-speed test counted video stills taken in the background as player restarts, so it failed now and then
  (on macOS); it counts only the player now.

## 0.22.0 — 2026-11-24

### Study overview
- **Project overview is a table:** one row per transcript with Day, Group, Type (session / interview) and Date read
  from the folders and file names, length, % checked, codings and speakers; episodes under their transcript.
- **Filter by typing** (every word has to match: `group 3 interview`, `day 2`), **sort** by any column, and the totals
  of what is shown. *Save as CSV* includes Type, Date, codings and your attributes.
- **Faster with many transcripts:** each row is remembered and only re-read when its transcript changed — also for the
  Project tab.

### Fixed
- **Clicking an episode or interview in the Project tab goes there**, also in a transcript you were already working
  in. It used to jump there and then straight back to where you had left off. The same for episodes in the overview
  and results of Find in all transcripts. Clicking one in the transcript that is already open no longer reloads it, so
  it is instant (also for long sessions) and undo is kept.
- **Lossless clips and cuts stay in sync with their transcript.** For recordings whose internal clock doesn't start at
  0 — common for camera files (.MTS, many MP4/MOV) — lossless episode clips and lossless Cut exports came out
  seconds off: the keyframes were looked up on the file's clock but cut on a clock from 0. MPEG-TS (.MTS) copies also
  keep a little sound from before the keyframe, and a timestamp shift added up to another 0.5 s; both are now measured
  from the written clip. Lossless is now as accurate as the re-encoded export (within a frame or two).

- **Memory no longer piles up while you watch video.** Every pause, jump or click during playback left the video
  preview's ffmpeg running in the background — stuck, but holding its memory (hundreds of MB for a long HD or 4K
  recording with the sharper preview). Over a long session these added up to gigabytes, enough for the system to
  close other programs. Stopped video streams now end for good.

### Memory meter
- **Memory at the bottom right:** what Condense and the programs it started (video preview, playback, transcription)
  use, measured every 10 seconds. Amber ▲ at a quarter of the computer's memory, red ⚠ at 40 %, with one line in the
  status bar and the Console when it gets there (no popups).
- **Click it for the Memory window:** each program's share, the undo history, how much it grew in the last 30 minutes,
  and two ways out — *Free memory*, or *Restart Condense…*, which saves everything and reopens the transcript where you
  were.

### Episode names
- **A new episode's label starts with its name:** for an interview in Group 4 on Day 3, *G4D3_I14* with the number
  selected, so you only type the number. `14` or `I14` is completed to `G4D3_I14` when saved (with a preview while you
  type), and when exporting. Before, a typed `I14` stayed like that until the clip was exported. Short labels from
  before can be completed with one click in the Episodes dialog, and they count as taken numbers.
- **Names for other episode types** (Project Settings ▸ Episode names, e.g. `Phase: G{group}D{day}_P{n}`), numbered
  per group like interviews — for workshops and studies that mark more than interviews.

### Attributes
- **Describe transcripts with attributes** (activity, site, consent, …): set them for several transcripts at once from
  the overview, or define them in *Project ▸ Attributes…*, optionally with a list of values. Renaming or deleting one
  follows in every transcript. Each becomes a column to filter, sort and export.

### Names and pseudonyms
- **Project ▸ Names & Pseudonyms…:** one list of the people in the study — every transcript's speakers, plus people who
  are only talked about.
- **Rename throughout:** speaker labels, the text, the project's speaker lists and exports, in every transcript, after
  showing what will change. Whole words only; other people whose name contains it (*Robin Meyer* when renaming
  *Robin*) are left alone. Codings stay on their words, transcripts keep a backup, the open one can be undone.
- **Pseudonyms** for each person (or numbered suggestions: P01, P02, …), and **export with pseudonyms**: copies of the
  transcripts with every name replaced, while the originals keep the real names.

## 0.21.0 — 2026-11-24

### Video while you work
- **The Coding tab shows the video** next to the transcript, with its own play/pause and ⤢ — for coding what happens,
  not only what is said.
- **⤢ Video in its own window:** as large as you like, on a second screen, full screen (F or double-click). Closing it
  puts the video back into the tab.
- **The picture fills its column** (fitted to width and height, enlarged when the video is small, never distorted) and
  is fitted again when you resize the column or the window. Sharper scaling, and smoother playback (15 instead of 10
  frames per second). The video column starts wider.
- **Playback ▾ ▸ Sharper preview: from the original recording** — the preview decodes the camera's original instead
  of the compressed copy, when the transcript is on its timeline.

## 0.20.0 — 2026-11-24

### Episode clips get their own transcript folder
- **Export clip…** now lays a clip out like transcribing it: `Semi-structured Interviews/G3D1_I1.mp4` and, next to it,
  the folder `G3D1_I1/` with the clip's transcript, its exports and the `.episode.json` record. Before, the exports of
  every clip landed loose in the interviews folder.
- The folder holds a real **`.transcript.json`** timed to the clip: it keeps the corrections, speakers, checked marks
  and notes made in the session transcript, and opens, edits and codes like any transcript. The project overview shows
  the clip as transcribed.
- Exporting the same episode again asks first and keeps the old transcript in `_backups`.

### Long recordings: fewer stretches Whisper skips
- **Settings ▸ Long recordings — Split at pauses if over 1 hour** (the default; also *Always* or *In one go*): Whisper
  transcribes long recordings in pieces of about 4 minutes, cut in the quietest moment, each started fresh with the
  vocabulary. Over hours Whisper otherwise loses track after one bad window and skips or repeats long stretches; now
  such an error stays inside its piece. Long silences are left out (Whisper invents text there); anything with sound
  is transcribed. The pieces are recorded in the transcript's provenance.
- **Transcript ▾ ▸ Find untranscribed stretches…** lists where the recording has voices as loud as the transcribed
  talk but the transcript has nothing, to listen to and re-transcribe one after another (also for transcripts made
  before).
- **Right-click in the transcript ▸ Re-transcribe this passage…** with the times of what you highlighted (or of the
  segment under the mouse); *Play this passage* too.
- Reading a recording's sound (finding clips, linking a video, untranscribed stretches) no longer holds it all in
  memory: 5 hours took ~600 MB.

### Video with subtitles
- **Transcript ▾ ▸ Video with subtitles…** (and right-click transcripts in the Project tab, several at once): a copy of
  the video with the transcript as subtitles, next to the transcript. As a **subtitle track** (seconds, nothing
  re-encoded; switch it on in the player) or **burned into the picture** (always visible; re-encodes). Subtitles are
  made from the words — two lines at most, a few seconds each, the speaker's name when the speaker changes — and leave
  out cut parts.

### Storage
- **Project ▸ Storage (Backups, Leftovers)…** shows what backups, leftovers of interrupted exports and the audio cache
  take, and clears them after asking: keep the newest 10 / 5 / 3 / 1 backups of each transcript, or none.

### Playback speed
- A **slider**, and the speed can be **typed** (1.3, 1.3×, 130 %; 0.5–3×). Playback restarts once when the slider
  rests, not on every move. ⌘⇧. / ⌘⇧, still step through the usual speeds; a typed speed is remembered.

### Menus
- Right-click menus and the ▾ menus are drawn in Condense's own theme on Linux and Windows, and **close when you click
  elsewhere** (on Linux they stayed open), press Esc or switch to another app. ↑/↓, Return, → and ← work in them. On
  macOS they stay the system's own menus.

## 0.19.0 — 2026-11-24

### Long sessions (3–5 hours) stay responsive
- **Corrections no longer redraw the whole transcript.** After saving a segment, changing a speaker, splitting,
  merging, undo …, only the lines that changed are redrawn; the rest stays as it is (also in the Coding tab when you
  code). On a 5-hour session that is one or two lines instead of ~30 000 words. Opening a transcript sends the text in
  a few large pieces instead of one piece per word.
- **Exports of long sessions are written in the background** (from about an hour of conversation): the transcript
  itself is saved at once, the `.srt`, `.vtt`, `.txt` and `.rtf` files a moment later. Quitting waits for them.
  Exports are also faster to write.
- **Dragging along the timeline** moves only the playhead; Condense jumps there once you stop or let go, instead of
  starting a video frame and the player for every mouse movement. The timeline shows the **time under the mouse**.
- **Go to time** (⌘J / Ctrl+J, *Playback ▸ Go to Time…*): type `2:15:30`.
- Video frames are taken one at a time; moving quickly through the transcript only asks for the newest one.
- The timeline draws segments that fall on the same pixels as one shape.
- **Undo needs far less memory:** each undo step is kept compressed. On a 5-hour transcript, 100 steps took ~650 MB;
  now ~110 MB.

### Link a video to a transcript
- **Playback ▾ ▸ Link a video…** (also a button in the empty video panel) shows a video with a transcript that has
  none, without compressing anything again: the original recording of a transcript made from a LosslessCut-trimmed
  video without *Compress*, a video that was moved or renamed, or a separate camera's video that started earlier or
  later. Condense lines it up with the transcript by its sound (each kept LosslessCut part separately, to a few
  hundredths of a second) and saves the link in the transcript; the video file is not changed. *Unlink the video*
  removes the link, and undo works.

## 0.18.0 — 2026-11-24

- Published before the changes of 0.19.0 were merged: the same as 0.17.0 (and it still reports itself as 0.17.0).
  Update to 0.19.0.

## 0.17.0 — 2026-11-23

### Fixed
- **↑/↓ in the transcript on a Mac** move between segments again. The Mac sends arrow keys with its *fn* bit set, and
  Condense took that for a shortcut and ignored them (the same happened on Windows with Num Lock on).
- **Bigger windows on an external monitor:** the window can now grow beyond the size of the Mac's built-in screen, and
  full screen fills the whole display without a dark band, also after switching to another app and back. Condense
  reopens at its last size and place on that monitor when it is still connected.

## 0.16.0 — 2026-11-23

### Moved to github.com/s-hurtado26/condense
- The project's GitHub address changed. Update checks and the installers use the new one; installed copies find it
  through GitHub's forwarding until they have updated to this version.

### Coding (first version)
- A **Coding** tab (⌘4 / Ctrl+4): the project's **codebook** on the left, the transcript with a coloured **stripe** for
  every coding, and the transcript's codings below (time, code, speaker, text, memo).
- **Inductive and evolving:** select words and press **N** for a new code that codes them; **1–9** reuse recent codes;
  subcodes; each code has a colour, definition, *use when* / *not when*, example and memo. **Merge** codes (subcodes and
  memos move along), **split** a code by giving some of its codings a new code, delete codes. The codebook
  (`condense-codebook.json` in the study folder) records every change in its log.
- **Moments without speech:** drag on the timeline, choose a code and describe what happens (materials, devices,
  gestures); shown in the transcript at its time.
- Codings are saved in the transcript, with backups and undo, and stay on their words through corrections, splits,
  merges and re-transcribed passages.

### Under the hood: ready for coding
- Every word now has a permanent id. Corrections, splits, merges, deleted or inserted segments and re-transcribed
  passages keep the ids of the words they don't change, so anything attached to words — codes, coming next — stays on
  the right words. Older transcripts get ids when opened. Tested with thousands of random edits.

## 0.15.0 — 2026-11-22

### Who is who?
- Detected speakers (`SPEAKER_01` …) take over a saved name for the **whole transcript**: right-click a speaker chip ▸
  *All segments of SPEAKER_01 are… Robin*, or the yellow **Who is who?…** chip (also in *Transcript ▾*) to name all
  of them at once — with each one's speaking time, a typical line and ▶ *Listen*. Two labels can get the same name
  (merged). One undo step.

### Windows open in front
- Every window Condense opens comes to the front with the keyboard focus, and stays above the window it was opened from.
  Before, e.g. Speakers opened from the Project overview could appear behind it.

### Split, merge, insert, delete: one click, one key
- The segment editor has buttons again for **Split (S)**, **Merge (M)**, **+ Insert (I)** and **Delete (Del / ⌫)**, and
  the letters work as shortcuts in the transcript (Delete asks first). Re-transcribe, revert and the markers are under
  *More ▾*.

## 0.14.0 — 2026-11-22

### A tidier transcript tab
- **Fewer buttons:** *Transcript ▾* holds open, speakers, speaker detection, episodes, finding interview clips, the
  trimmed export, marking a whole transcript checked and restoring cuts. Review tools stay visible: view, *Show*, *Find*,
  ◀ *Uncertain* ▶, *✂ Cut*, *Episodes*.
- **Playback ▾** holds the player's options (follow the text, snippet on jump, skip cuts, video, open in a video player)
  instead of a row of checkboxes and a hint line.
- **Segment ▾** in the editor holds split, merge, insert, delete, re-transcribe, revert and the markers; *Mark checked*,
  *Save* and *Save & next* stay as buttons.
- **Text size is a slider** (Aa) next to the transcript's summary line; double-click it for 100 %.

### Project tab
- Shows each recording's **length** (measured once with ffprobe and remembered) and each episode's length and start.
- Recordings sort naturally: I4 before I10. More space at the edges of the Tasks and Project tabs.

### Speakers per group
- Each group is its own case: *Project ▸ Speakers (Project and Groups)…* keeps a speaker list for the **whole project**
  (people in every group, e.g. facilitators) and one **per group** (its children). A transcript gets the project's
  speakers first, then its group's — on every day, since Group 1 on Day 2 is the same group as on Day 1. So in Group 1,
  Facilitator is 1, Robin 2, Sam 3; Group 3's children don't appear there.
- The dialog opens on the open transcript's group; right-click a group (or a recording) in the Project tab for
  *Speakers of Group …*. *Add names from transcripts* collects the names already used in that group.

## 0.13.0 — 2026-11-22

### The project, always in view
- A **Project** tab next to *Tasks* shows every recording of the study by day and group — **transcribed or not** —
  sorted into *Sessions*, *Interviews* and *Other recordings* (like screen recordings), with each transcript's progress
  and episodes. The open transcript is highlighted; progress updates as you check segments.
- **Double-click** opens a transcript (or an episode in it); on a recording without a transcript it offers to add it to
  Tasks. Right-click: transcribe several at once, find interview clips in a session, show in folder.
- New transcripts appear when a run finishes. Condense's own copies (compressed videos in result folders) and macOS `._`
  files are not listed.

### Fixed
- **The transcript no longer jumps** when you give a segment another speaker, merge or split segments, cut, or undo.
  The paragraphs regroup after such a change, and the view used to be restored as a fraction of the whole text, which
  then pointed somewhere else. The segment you are working on now stays at the same place on screen.
- The lines above and below the transcript (summary, word info, the segment editor's hint, its buttons and the speaker
  chips) keep a fixed height, so moving with ↑/↓ no longer shifts the layout.

### Editing
- **Mark a whole transcript checked (100 %)** — or not checked — from the right-click menu of the Project tab (several
  at once) or the task list, or *Edit ▸ Mark Whole Transcript Checked*. Cut segments don't count; a backup is kept,
  the edit log records it, and ⌘Z / Ctrl+Z undoes it when the transcript is open.
- **Esc while typing** in the segment box (or the note field) saves and takes you back to the transcript, where ↑/↓ move
  on and Return edits again. Outside the text boxes Esc still plays and pauses.

### Clip names in more than one pattern
- Interview clips named in different ways (`G1D1_I1`, `D1G4_I1`) are all recognised: the patterns are learned from the
  clips already in the interview folders, and the template accepts alternatives (`G{group}D{day}_I{n} | D{day}G{group}_I{n}`).
  New clips use the first; numbering counts all of them.
- A level with a single folder (only `Day 1 …`) is recognised too.

## 0.12.0 — 2026-11-22

Workshops with groups: episodes for interviews and activity phases, projects that follow your folders, and interviews you
already cut out found again in their session by their sound. Projects stay optional — without one, Condense works file
by file as before.

### Episodes: interviews and activity phases
- An **episode** labels a stretch of a recording: the facilitator's interview with a group, or a phase such as
  *Dioramas*. Nothing is removed. Select segments and press **E**, or use *Episodes…* in the transcript toolbar.
- Episodes show as **coloured bands on the timeline** and as **headers in the transcript** (▶ … / ■ end of …), and start
  new paragraphs. Phases you only know roughly can be marked *approximate*.
- **Show ▸ In Interview / In Phase …** moves through only the segments of one kind of episode.
- **Export an episode as a clip** with a transcript timed to it (SRT, TXT, paragraphs for MAXQDA) and an `.episode.json`
  record. Interviews are saved next to the group's other interviews. Exact export now jumps straight to the episode
  instead of decoding the whole recording before it.

### Interviews you already cut out
- **Find interview clips…** (Episodes dialog or Edit menu) finds each clip from the group's interview folder in the
  session recording **by its sound** — to a few hundredths of a second, whatever tool cut it — and adds it as an
  Interview episode labelled with the clip's name. Uncertain matches are marked for checking; running it again updates
  instead of duplicating. The session's sound is read once and cached.

### Your folder structure, as a template
- *Project ▸ Project Settings* describes the study's structure as templates, read from your folders when the project is
  created: `{Day}/{Group}/Session Recordings` and `{Day}/{Group}/Semi-structured Interviews/G{group}D{day}_I{n}`.
  Presets (*Workshops*, *Interview study*, *One folder*), a live example, and *Read from my folders*.
- `{n}` numbers a group's interviews **across all days**. A new interview marked with **E** or exported as a clip gets the
  next name (e.g. `G1D2_I14`) and goes into the group's interview folder; *Find interview clips* looks exactly there.
- **Tidy Unsorted Folders** (Project menu) is a plan first: for each file in a …Unsorted folder, where it belongs and why.
  Duplicates, unrecognised names and missing folders stay put. Nothing moves until you confirm; moves are recorded in
  `condense-moves.json` and can be undone.

### Projects follow your folders
- Levels are read from folder names: `Day 1 2026-08-10/Group 1/…` gives *Day* and *Group*. Media folders inside a group
  stay part of it.
- **Consent forms** and **…Unsorted** folders are skipped: never opened or listed.
- **Project ▸ Project Settings…**: name, levels, skipped folders and episode types (Interview, Phase, Plenary …).
- The **overview is a tree** — Day ▸ Group ▸ transcript ▸ episodes — with totals per day and group; double-click an
  episode to go to it. The CSV has a column per level.

### Reviewing
- **Transcript text size:** *A−* / *A+* in the transcript toolbar (80–250 %), Ctrl/⌘ + scroll wheel over the transcript,
  or *View ▸ Larger / Smaller Transcript Text*. Sizes the transcript and the segment box only, on top of the window zoom,
  and is remembered.

### Projects are now something you open
- A new **Project** menu: *New Project…*, *Open Project…*, *Open Recent*, *Close Project*, *Project Overview…* and
  *Project Speakers…*. A project is still just the study's folder; nothing is moved.
- The button at the top right shows the open project (click it for the overview), or **No project open** (click it to
  start or open one).
- Opening a transcript of a study opens its project. *Open Transcript* and *Search All Transcripts* start in the project's
  folder.
- The user guide's project section explains the workflow.

### Fixed
- **Opening the project overview could freeze Condense.** With no transcript open, it searched your whole home folder,
  external drives included, before showing anything. It now never searches without a project, searches in the
  background, skips hidden folders and backups, and stops on very large drives. *Search All Transcripts* uses the same
  safe search.
- **macOS `._` files on external drives** (a Mac writes one next to every file on exFAT drives such as a T7) are no
  longer added as videos by *+ Folder* or listed as broken transcripts.

## 0.11.0 — 2026-11-22

Cut recordings down to what matters, review faster, keep a whole study in view — and Condense now runs on Windows.
New here? The [user guide](https://github.com/s-hurtado26/condense/blob/main/docs/user-guide.md) walks through a
whole study, from recordings to a checked transcript in MAXQDA (also under *Help ▸ User Guide*).

### Highlights
- **Cutting:** press **X** to leave segments out of the transcript, then export a trimmed video with a transcript timed to
  it, ready for MAXQDA.
- **Trim before transcribing:** mark setup time and breaks on a filmstrip; they are skipped before Whisper runs.
- **Find & replace**, in one transcript or across every transcript of a study.
- **Notes on segments** and a **Show filter** (uncertain / not checked / with notes / cut).
- **Project overview** and **project speakers**: progress of every session at a glance, and the same number keys and
  colours for the same people in every session.
- **Clean up for Whisper:** levelling and noise reduction for quiet children and noisy rooms.
- **GPU check:** Condense tests the GPU before you transcribe, and *Help ▸ Test GPU…* shows the details.
- **Windows** (preview), with NVIDIA and AMD GPUs.

### ⚠ Changed shortcuts on Linux and Windows
- Assigning a speaker **while typing** in the segment box is now **Alt+1–9** (was Ctrl+1–9). Ctrl+1–3 switch tabs again.
- **Markers** are **Ctrl+Shift+letter** (as the menu always said). Before, Ctrl+C inserted `[crosstalk]` as well as
  copying, and Ctrl+I inserted `[inaudible]` instead of a segment.
- In the transcript itself nothing changes: **1–9** assign speakers as before. The Mac keeps ⌃1–9 and ⌃letter.

### Cutting and trimming
- **Cut while reviewing:** select segments and press **X** (or *✂ Cut / restore*). Cut segments are struck through, left
  out of every export (TXT, SRT, VTT, RTF, paragraphs), skipped while playing (*Skip cuts*) and don't count towards
  % checked. Nothing is deleted: X again restores them, *Edit ▸ Restore All Cuts…* restores everything, and ⌘Z / Ctrl+Z
  undoes.
- **Export trimmed video & transcript** (File menu or the transcript toolbar): the video without the cut parts, and a
  transcript re-timed to it, so MAXQDA links them correctly.
  - *Exact* re-encodes and cuts exactly where you cut.
  - *Lossless* is fast and keeps full quality but can only start on keyframes. The transcript is timed to what was
    really written, and cuts too short to apply are reported.
  - A `.cuts.json` record documents what was cut; the cuts can also be saved as a LosslessCut project.
- **Trim before transcribing** (*Task Details ▸ Trim…*): mark parts to leave out on a filmstrip and waveform, with a frame
  preview and 5-second playback (I / O mark a cut's start and end). Saved as `<video>-proj.llc`, which Condense applies
  before transcribing and LosslessCut opens too. Condense never deletes a LosslessCut project it did not write.
- When LosslessCut cuts are applied before transcribing, the trimmed video the transcript is timed to is now kept
  (`<name>_trimmed.<ext>`) instead of being discarded.

### Reviewing
- **Find & replace** (⌘F / Ctrl+F, or *Find…*): matches are highlighted; Return / ⇧Return step through them. *Replace* and
  *Replace all* are one undo step each, with options for match case and whole words. Word timings are kept.
- **Search all transcripts** (*Edit ▸ Search All Transcripts…*): searches every transcript in a folder and its subfolders,
  opens a hit at its segment, and can replace everywhere — for a name Whisper always gets wrong, or to swap a name for a
  pseudonym. Each changed transcript gets a backup, new exports and an entry in its edit history.
- **Notes on segments:** a ✎ Note field under the segment text. Notes show in the transcript and appear as `[Note: …]` in
  the TXT and paragraph exports.
- **Show filter:** All segments / Uncertain / Not checked / With notes / Cut. ↑/↓ then move only through those segments.
- **Clean up for Whisper** (*Settings ▸ Audio & Whisper*): *Level quiet voices* or *Reduce noise + level voices*. Only
  the audio Whisper hears is cleaned; your video and audio files are unchanged. The setting is recorded in the
  transcript's provenance.

### Projects
- **Project overview** (*File ▸ Project Overview…*): every transcript in a study folder with its length, % checked,
  % uncertain words, speakers (and how many are still unnamed), cut time, notes and last change. Double-click opens one;
  *Save as CSV* writes `condense-overview.csv`.
- **Project speakers:** the people of a study (facilitators, the children's pseudonyms) in a fixed order, saved as
  `condense-project.json` in the study folder. They come first in every transcript below it, so they have the same
  number key and colour in every session. *Add names from transcripts* collects the names you already used.

### Windows (preview)
- Windows 10/11, 64-bit. Whisper and speaker detection run on the GPU through PyTorch: CUDA on NVIDIA; AMD's ROCm for
  Windows on the Radeon RX 7900 / RX 9000 series (Windows 11, AMD Software 26.2.2 or later); otherwise the CPU.
- Video compression on the GPU: NVENC (NVIDIA), AMF (AMD) or Quick Sync (Intel). The default tests which encoder really
  works on the PC and falls back to the CPU.
- One-line install from PowerShell (see below); winget installs Python 3.12, FFmpeg and HandBrake CLI. In-app updates
  work as on macOS and Linux.
- Hugging Face token in the Windows Credential Manager; Start-menu and Desktop shortcuts; no console windows; sharp text
  on high-resolution screens.

### Linux
- **Native file chooser:** the desktop's own dialog (GNOME/GTK via `zenity`, KDE via `kdialog`) with external drives,
  bookmarks and search, instead of Tk's old dialog. It starts in the last folder used and also finds upper-case
  extensions such as `.MP4`. The installer adds `zenity`.
- **Ctrl+Enter** (save, mark checked, next segment) now also works when the transcript has the focus, and with the
  number-pad Enter.
- The harmless `amdgpu.ids: No such file or directory` message from ROCm builds of PyTorch no longer appears in the
  Console.

### All platforms
- **GPU check:** at start-up Condense runs a short calculation on the GPU instead of only asking whether one is visible
  (with ROCm a card can be visible yet unusable). The header shows the result; *Help ▸ Test GPU…* shows the details. If a
  task would transcribe on the CPU although a GPU backend is chosen, *Run* asks first. The Linux and Windows installers
  run the same test.
- **User guide** with screenshots: *Help ▸ User Guide*.
- Buttons and hints show Ctrl+S, Ctrl+Enter … on Linux and Windows instead of Mac symbols.
- Without HandBrake, the x265/x264 encoders use ffmpeg's own instead of failing.
- Whisper's output is read as UTF-8.
- Faster re-timing for long sessions with many cuts; the project overview table is readable on Linux.

### Under the hood
- Every CI run now tests the real app on macOS, Linux and Windows, including real key presses for the shortcuts, and a
  3-hour session through every core path and both trim modes.
- The largest modules (editor, pipeline worker) are split into smaller ones.

## 0.10.0 — 2026-11-20

### Installing and updating
- One-line installer for macOS and Linux: `curl -fsSL https://raw.githubusercontent.com/s-hurtado26/condense/main/install.sh | bash`. It downloads the latest release, installs Homebrew on a Mac if needed, runs the platform installer and remembers its options.
- Updates from inside the app: a daily check (Help ▸ Check for Updates Automatically, can be turned off) shows what is new; **Update now** installs it without a password and offers a restart. "Skip this version" is remembered. Also Help ▸ Check for Updates… and `~/.condense/install.sh --update`.
- Help menu: installation guide, release notes, report a problem, About.

### Linux (preview)
- New Linux platform layer. Whisper (openai-whisper) and speaker detection run on the GPU through PyTorch — ROCm on AMD, CUDA on NVIDIA — or on the CPU. The GPU and API used are recorded in each transcript's provenance.
- Video compression with VA-API on AMD and Intel GPUs (`vaapi_h265`, `vaapi_av1`, `vaapi_h264`); without a VA-API encoder Condense falls back to HandBrake on the CPU and says so.
- Hugging Face token in the desktop keyring (GNOME Keyring / KWallet via `secret-tool`), app-menu entry (`condense --install-app`), XDG locations (`~/.config/condense`, `~/.local/state/condense`), `xdg-open` for folders and the video player, X11 mouse-wheel scrolling, Linux fonts.
- `scripts/install-linux.sh`: apt packages, the matching PyTorch build (`--gpu rocm|cuda|cpu`, `--torch-index`), or reuse of an environment whose PyTorch already works (`--venv`); PyTorch is pinned so later packages cannot replace it.
- `CONDENSE_WHISPER_PYTHON` runs Whisper from another Python environment; `CONDENSE_VAAPI_DEVICE` picks the render node.

### Editor
- Speakers by number key: in the transcript, 1–9 assign speaker 1–9 and 0 adds a new one (⌃1–9 still work while typing). The speaker chips show their number.
- Select several segments — drag across them, ⇧-click, ⇧↑/⇧↓ or ⌘A — and assign a speaker (key, chip or the editor's speaker list) or mark them checked in one go. One undo step reverts the whole change.
- More transcript keys: ↑/↓ previous/next segment, R replays the open segment, C toggles checked, Return edits the segment, Tab in the segment box saves and returns to the transcript.
- View ▸ Keyboard Shortcuts (⌘/) lists every shortcut.
- Single-key shortcuts ignore ⌘/Ctrl/Alt, so ⌘C copies, ⌘1–3 switch tabs and ⌘R starts the queue from the transcript as before.

### Project
- Install guides for macOS and Linux (`docs/`), release workflow, install-script checks in CI.
- The Mac installer checks MLX and Metal at the end and has `--no-app`; Condense.app requires macOS 14 (as MLX does).
- Public-release housekeeping: third-party notices, citation file, security policy, contributing guide, issue/PR templates with privacy reminders, Dependabot for GitHub Actions.

## 0.9.0 — 2026-11-20

First version in this repository, restructured from the single-file Apple Silicon app into the `condense` package. Behaviour is unchanged; the previous settings, task queue and Keychain token (stored under "SiliconVideoPipeline") are picked up automatically.

- Task queue: one task per video or merge tasks, per-task steps and settings, remembered between launches.
- Hardware: MLX Whisper on the Apple GPU, PyTorch/Metal speaker detection, VideoToolbox encoding.
- Editor: paragraphs/segments views, play/pause/seek/speed, follow-along highlight, video preview, segment editing with timing kept, split/merge/insert/delete, speaker list with ⌃1–⌃9, markers, checked marks and progress, timeline, undo/redo, automatic backups, resume position.
- Accuracy: vocabulary per task, re-transcribe passage (incl. translate to English), re-run speaker detection keeping hand-assigned speakers.
- Exports: paragraph RTF/TXT, SRT, VTT, TXT, confidence RTF; master `.transcript.json` with provenance and edit history.
- Tests: end-to-end scenarios runnable with pytest (no GPU, display or real recordings needed).
