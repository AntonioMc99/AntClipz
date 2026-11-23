# AntClipz

Finds the best moments from big Twitch streamers, turns them into short vertical clips,
and (after manual review) posts them to X and TikTok. Original streamers are always credited.

## Progress checklist
- [x] Language: Python
- [x] OS: Windows (ASUS PC)
- [x] Twitch developer app created
- [x] Twitch Client Secret reset
- [x] Whisper choice: free, runs on your PC (faster-whisper)
- [x] Phase 1: clip finder (`find_clips.py`) - tested on Windows, works
- [x] Phase 2: download (`download_clip.py`) - tested on Windows, works
- [x] Phase 3: edit (`edit_clip.py`) - split layout + captions, tested on Windows, works
- [ ] Phase 4: review in Google Drive (`send_to_review.py`) - code written, needs a test on your PC
- [ ] Phase 5a: post to X
- [ ] Phase 5b: TikTok (manual uploads until the API app passes audit)

## First-time setup (Windows)
1. On GitHub, switch to branch `claude/relaxed-curie-z57h2j`, click **Code -> Download ZIP**, and unzip it into Documents.
2. Open the unzipped folder, click the address bar, type `powershell`, and press Enter.
3. Run: `powershell -ExecutionPolicy Bypass -File setup.ps1`
   (If it installs Python, open a new PowerShell window in the folder and run it again.)
4. Paste your Twitch keys into Notepad when it opens, then save.

## Run Phase 1
Double-click `find-clips.bat`.

## Run Phase 2
Double-click `download-clip.bat` to download the #1 clip, or in PowerShell: `.\download-clip.bat 3` for clip #3.
Videos are saved in `data\downloads\`.

## Run Phase 3
Double-click `edit-clip.bat` to edit the #1 clip (or `.\edit-clip.bat 3`). The clip must be downloaded first.
Finished vertical videos are saved in `data\edited\`.

## Run Phase 4 (review on your phone)
One-time: install Google Drive for desktop (https://www.google.com/drive/download/) and sign in.
Then `.\send-to-review.bat` copies the edited clip to `My Drive\antclipz\1 - to review`.
On your phone (Google Drive app): watch it, then **Move** it to `2 - approved` or `3 - rejected`.
Only clips in `2 - approved` will ever be posted.

## All-in-one
`.\make-clip.bat 3` = download + edit + send to review for clip #3 (run `find-clips.bat` first).
