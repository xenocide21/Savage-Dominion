# TODO / known issues

- **Splash screen edge glitch:** after a finisher ("fatality") and reset to the splash, a sliver of a
  fighter (Kaze's shoulder on the left, another on the right) can show at the screen edges. Not every
  time. Probably a scroll / camera-orbit value left over from the finisher that the splash does not reset.
- Throw escapes (roadmap).
- CPU dashing (roadmap).
- Model detail: costume pieces, facial expressions, open hands for throws.
- Persistence of records across power cycles is untested on real hardware / other emulators
  (battery RAM header: RAM size $06, type $15).
- **Frame rate on accurate timing:** current snes9x's cycle-accurate Super FX model (2026) renders fights at
  ~12 fps (legacy timing: 30 fps). Most Super FX time is per vertex (point transform ~25%, edge setup ~31%),
  so the next speed-ups are in `fx.gsu` (e.g. running the transform/edge code from the GSU cache instead of
  RAM) and in vertex counts. Measure with `FXDBG=<frame> test/snesrun.py ...` on the patched core.
- **Anatomy rework:** all six fighters use the two-layer builder (`tools/anatomy.py`). The legacy limb/torso
  code in `model.build` now only supplies heads and hair chains; it can be trimmed once nothing else needs it.
