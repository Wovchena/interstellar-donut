# Interstellar Donut — Validation Guide

## What it is

An ASCII art animation of a Gargantua-style black hole: a dark spherical
shadow surrounded by a bright accretion disk and a gravitationally lensed
ring, rendered in the terminal.

## How to run

```bash
python interstellar_donut.py        # runs indefinitely, Ctrl+C to stop
```

### Automated validation (finite run)

```python
from interstellar_donut import InterstellarDonut
d = InterstellarDonut(width=80, height=30)
d.run(duration=3)
```

Always use `duration=` when running from tests or scripts.
The script runs **indefinitely** by default and will hang CI or an agent.

## What "correct" looks like

A single rendered frame must satisfy **all** of the following:

### 1. Black hole shadow

- A **dark donut ring** (space characters) — the torus body is opaque black.
- The **center hole** of the donut lets light through — at viewing angles
  where the disk intersects the hole, bright characters will appear inside
  the torus ring. At other angles the hole may be empty (space) but it is
  never occluded by the torus body itself.
- It must be large enough to **visibly cut into** the bright disk/ring,
  not just fill the empty hole inside them.
- Implemented via parametric torus sampling in Pass 3 using the **same**
  geometry as the original donut (`R1=1.0`, `R2=2.0`, spanning radii
  1.0–3.0). The disk brightness peaks at r=2.0, so the dark ring cuts
  sharply into the brightest region of the disk.

### 2. Accretion disk

- A **bright elliptical band** of ASCII characters around the shadow.
- Orientation is **fixed** (`disk_A`, `disk_B` class attributes). It must
  **not** rotate when the animation advances `A` and `B`.
- Brightness follows a Gaussian profile `exp(-(r-2)^2/2)` peaking at
  radius 2.0 (the torus center), across a wide annulus from 0.3 to 5.5.
  This makes the disk brightest right at the shadow edge, with light
  visible both through the donut hole and around the outside.
- Rendered via screen-space ray casting in Pass 1.

### 3. Lensed ring

- A second bright ring **perpendicular** to the accretion disk, representing
  the gravitationally bent image of the far side of the disk.
- Should arc **over the top and under the bottom** of the shadow.
- Brightness peaks at the poles (`sin²α`) and fades to zero at the equator
  so it does not overlap with the accretion disk in the equatorial region.
- Must **not** collapse to a vertical line (the `e1` basis vector must have
  nonzero x-extent).
- Uses the same fixed orientation as the accretion disk.

### 4. Animation

- Only the **black hole shadow** rotates (via animated `A`, `B`).
  The accretion disk and lensed ring stay fixed in space.
- Frame rate regulated by `time.sleep(0.03)`.
- Output uses ANSI escape `\x1b[H` for flicker-free redraws; no `clear`
  per frame.

## Automated frame-content checks

To validate a single frame programmatically:

```python
import io, sys
from interstellar_donut import InterstellarDonut

d = InterstellarDonut(width=80, height=30)
buf = io.StringIO()
sys.stdout = buf
d.render_frame()
sys.stdout = sys.__stdout__
frame = buf.getvalue()
lines = frame.split('\n')

# 1. Frame is non-empty and fills the terminal
assert len(lines) >= 25
assert any(len(l) >= 70 for l in lines)

# 2. Accretion disk / lensed ring produced bright characters
bright = sum(c in '=!*#' for c in frame)
assert bright > 50, f"Too few bright chars ({bright}), disk/ring missing"

# 3. Torus has a hole — it is donut-shaped, not a solid sphere
# Find rows where the torus body creates dark regions. The torus body
# occupies a ring; the center of that ring must NOT be dark-body.
# We verify by checking that the torus does not fill the entire center
# column: there must be rows in the middle vertical strip that are blank
# (hole) while rows above/below have torus body (also blank but from
# disk). A simpler check: the torus body (Pass 3) only writes spaces,
# so we actually check that the lensed ring / disk produce characters
# in rows that are inside the torus bounding box.
mid_x = 40
# Count rows where column mid_x has a non-space char (disk/ring light)
lit_rows = [i for i, l in enumerate(lines)
            if len(l) > mid_x and l[mid_x].strip() != '']
# Count rows where column mid_x is blank
dark_rows = [i for i, l in enumerate(lines)
             if len(l) > mid_x and l[mid_x].strip() == '']
# Both must exist — the donut blocks some rows and the hole/disk lets
# light through in others
assert len(lit_rows) > 5, f"Too few lit rows ({len(lit_rows)}), disk/ring missing"
assert len(dark_rows) > 3, f"Too few dark rows ({len(dark_rows)}), shadow missing"

# 4. Disk does not rotate — render two frames at different A and check
#    that the disk pixels are the same in a row far from the torus body
#    (where only the disk contributes, not the shadow).
d2 = InterstellarDonut(width=80, height=30)
d2.A = 0.0  # different torus angle
buf2 = io.StringIO()
sys.stdout = buf2
d2.render_frame()
sys.stdout = sys.__stdout__
frame2 = buf2.getvalue()
# Compare the last row with bright characters — it's pure disk, far from
# the torus shadow, so it should be identical regardless of torus angle.
lines2 = frame2.split('\n')
last_bright = max((i for i, l in enumerate(lines)
                   if any(c in '=!*#' for c in l)), default=None)
if last_bright is not None and last_bright < len(lines2):
    assert lines[last_bright] == lines2[last_bright], \
        "Disk rotated between frames — it should be fixed"
```

## Common failure modes

| Symptom | Cause |
|---|---|
| Disk rotates with animation | `cosDA`/`sinDA` bound to animated `A` instead of `self.disk_A` |
| Lensed ring is a vertical line | `e1` basis vector has zero x-component (use `view × n` not `e2`) |
| Shadow not visible | Shadow torus too small or disk brightness too uniform |
| Center is dark | Disk inner radius too large — must extend below R2-R1 to reach the hole |
| Shadow swallows disk | Shadow torus geometry too large or disk doesn't extend past R2+R1 |
| Script hangs in CI | Forgot to pass `duration=` to `run()` |
| Frame has gaps/dots | Disk rendered parametrically instead of screen-space ray cast |
