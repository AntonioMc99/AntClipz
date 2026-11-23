# AntClipz

Finds the best moments from big Twitch streamers, turns them into short vertical clips,
and (after manual review) posts them to X and TikTok. Original streamers are always credited.

## Progress checklist
- [x] Language: Python
- [x] OS: Windows (ASUS PC)
- [x] Twitch developer app created
- [ ] Twitch Client Secret reset (old one was exposed)
- [ ] Setup plan PDF shared (needed before Phase 3)
- [ ] Phase 1: clip finder (`find_clips.py`) - code written, needs a test on your PC
- [ ] Phase 2: download (yt-dlp)
- [ ] Phase 3: edit (vertical 9:16 crop + Whisper captions)
- [ ] Phase 4: review folder (approve from phone)
- [ ] Phase 5a: post to X
- [ ] Phase 5b: TikTok (manual uploads until the API app passes audit)

## Run Phase 1 (Windows PowerShell)
```powershell
.venv\Scripts\Activate.ps1
python find_clips.py
```
