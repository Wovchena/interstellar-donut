#!/usr/bin/env python3
"""
Interstellar Donut - A rotating ASCII donut with gravitational lensing

Renders a rotating torus (donut) in the terminal using ASCII characters,
with an accretion disk and gravitational lensing effects inspired by the
movie Interstellar (Gargantua black hole).

GOAL: The visual should look like Gargantua - a donut/black-hole with:
  - A bright accretion disk in the torus equatorial plane
  - A perpendicular lensed ring (gravitationally bent image of the far
    side of the disk, arcing over the top and under the bottom)
  - Together these form a characteristic "cross" pattern around the donut

ARCHITECTURE:
  - InterstellarDonut class holds all parameters and rendering logic
  - render_frame() draws one frame in 3 passes:
      Pass 1: Accretion disk via SCREEN-SPACE RAY CASTING into the torus
              equatorial plane (rotated by A,B). For each pixel, cast a ray
              and test intersection with the disk plane's annular region.
              This guarantees complete pixel coverage — no gaps or stray dots.
      Pass 2: Lensed ring via PARAMETRIC 3D RING in the plane perpendicular
              to the disk and containing the view direction. Uses basis
              vectors n (disk normal) and e2 (perpendicular within that plane).
      Pass 3: Solid donut torus with z-buffered Lambertian surface normals.
  - All passes share a z-buffer so nearer surfaces properly occlude farther ones.
  - run() loops render_frame() with rotation increments A+=0.04, B+=0.02
  - Projection: perspective with K2=5.0 distance, K1 auto-scaled to fit
  - Light direction: (0, 1/√2, -1/√2) — from upper-left

KEY MATH:
  - Disk plane normal (torus equatorial, rotated): n = (-sinB*cosA, cosB*cosA, sinA)
    Derived from rotating (0,1,0) by Rx(A) then Rz(B).
  - Lensed ring plane basis: n and e2 = (-sinA*sinB, sinA*cosB, -cosA)
    e2 = n × (n × view_dir), normalized. Perpendicular to n, in the n-view plane.
  - Ray for pixel (xp,yp): direction d = ((xp-half_w)/K1, 2*(half_h-yp)/K1, 1)
    Intersection with disk plane at parameter t = (sinA*K2) / (n·d)

HISTORY OF CHANGES:
  v1: Sparse concentric circle outlines for disk — too sparse.
  v2: Filled annular regions — solid but disk rendered as parametric 3D points
      in a fixed horizontal plane (y=0). Problem: a plane containing the camera
      projects to a 1-pixel-high line. Adding y-slab thickness just scattered dots.
  v3: Disk rotating with torus — looked like it passed through the torus body
      (disk_inner was smaller than torus body extent).
  v4: Screen-space ray casting for disk in the torus equatorial plane. Each pixel
      is tested via ray-plane intersection. The disk rotates with the torus so it
      naturally tilts and becomes visible as an elliptical annulus. Lensed ring
      uses properly oriented perpendicular-plane parametric approach.
  v5: Accretion disk and lensed ring now use FIXED orientation angles (disk_A,
      disk_B) instead of the animated A,B. Only the torus rotates. This matches
      the Interstellar visual: the disk is stationary in space while the black
      hole (torus) spins inside it.

REPO: Wovchena/interstellar-donut
BRANCH: copilot/add-rotating-donut-visualization
PR: #1
"""

import math
import time
import sys
import os
import argparse


class InterstellarDonut:
    """A rotating ASCII donut with accretion disk and gravitational lensing."""

    def __init__(self, width=80, height=24):
        """
        Initialize the donut renderer.

        Args:
            width: Terminal width in characters
            height: Terminal height in characters
        """
        self.width = width
        self.height = height

        # Torus geometry: a tube of radius R1 swept around a circle of radius R2.
        # The torus surface spans from R2-R1=1.0 to R2+R1=3.0 in the radial direction.
        self.R1 = 1.0   # Tube radius (cross-section of torus)
        self.R2 = 2.0   # Distance from torus center to tube center
        self.K2 = 5.0   # Distance from viewer to torus (perspective depth)

        # K1: projection scaling factor, auto-sized so the donut fits the screen.
        # Uses min(width, height*2) because terminal chars are ~2x taller than wide.
        # The factor 3/8 was tuned to leave room for disk/ring effects around the donut.
        self.K1 = min(self.width, self.height * 2) * self.K2 * 3 / (8 * (self.R1 + self.R2))

        # Characters for accretion disk and lensed ring glow (darkest to brightest).
        # Index 0 is space (invisible), index 10 is '#' (brightest).
        self.disk_chars = " .,-~:;=!*#"

        # Rotation angles: A = tilt around X-axis, B = spin around Z-axis.
        # A controls how much we see the disk edge-on vs face-on.
        # B rotates the whole scene around the viewing axis.
        # Start tilted so the accretion disk is visible from the first frame.
        self.A = 1.0
        self.B = 0.0

        # Fixed orientation for accretion disk and lensed ring.
        # These do NOT change — the disk is stationary in space.
        # Only the torus (donut body) rotates via self.A, self.B.
        # disk_A near 0 = edge-on view → thin horizontal band (Gargantua look).
        self.disk_A = 0.2
        self.disk_B = 0.0

        # Characters for the donut surface shading (darkest to brightest).
        # These are different from disk_chars; the donut uses luminance-based shading.
        self.luminance_chars = ".,-~:;=!*#$@"

    def clear_screen(self):
        """Clear the terminal screen."""
        sys.stdout.write('\x1b[2J\x1b[H')
        sys.stdout.flush()

    def render_frame(self, display=True):
        """Render a single frame of the rotating donut with accretion disk.

        Args:
            display: If True, print the frame to stdout.

        Returns:
            The 2D character grid (list of lists of chars).
        """
        ambient = '.'
        output = [[ambient for _ in range(self.width)] for _ in range(self.height)]
        zbuffer = [[0.0 for _ in range(self.width)] for _ in range(self.height)]

        half_w = self.width / 2.0
        half_h = self.height / 2.0

        # Precompute rotation for TORUS (animated)
        cosA = math.cos(self.A)
        sinA = math.sin(self.A)
        cosB = math.cos(self.B)
        sinB = math.sin(self.B)

        # Precompute rotation for DISK — base orientation is fixed, but
        # a periodic wobble simulates gravitational frame-dragging from the
        # rotating torus. The torus isn't a sphere: its asymmetric mass
        # distribution warps the disk plane as it rotates.
        drag = 0.08  # Wobble amplitude in radians
        eff_A = self.disk_A + drag * math.sin(self.A)
        eff_B = self.disk_B + drag * math.sin(self.B)
        cosDA = math.cos(eff_A)
        sinDA = math.sin(eff_A)
        cosDB = math.cos(eff_B)
        sinDB = math.sin(eff_B)

        # Disk plane normal: base orientation + frame-dragging distortion.
        # Unrotated normal is (0,1,0). After Rx(eff_A) then Rz(eff_B):
        #   n = (-sinDB*cosDA, cosDB*cosDA, sinDA)
        nx = -sinDB * cosDA
        ny = cosDB * cosDA
        nz = sinDA

        # === Pass 1: Accretion disk (screen-space ray casting) ===
        # The disk lies in a tilted plane whose orientation slowly wobbles
        # due to frame-dragging from the rotating torus. For each screen
        # pixel, cast a ray from the camera through the pixel, intersect
        # with the disk plane, and check if the hit point falls in the
        # annular region [disk_inner, disk_outer] around the torus center.
        # This guarantees complete pixel coverage — no gaps or scattered dots.
        #
        # WHY THIS WORKS:
        #   The disk base tilt (disk_A=0.2) gives a nearly edge-on view
        #   that projects as a thin horizontal band. The frame-dragging
        #   blend makes it wobble as the torus rotates, creating visible
        #   distortion from the non-spherical gravitational field.
        #   accretion disk. The disk does NOT rotate; only the torus body does.

        disk_inner = 0.3   # Light shines through the donut hole
        disk_outer = 5.5   # Well past the torus shadow
        disk_peak = 2.0    # Brightness peaks at the torus center radius

        # Plane equation: n · P = n · center = nz * K2 = sinDA * K2
        n_dot_c = nz * self.K2

        # Only render disk when plane is not perfectly edge-on to camera
        if abs(nz) > 0.01:
            for yp in range(self.height):
                for xp in range(self.width):
                    # Ray direction from camera (origin) through pixel (xp, yp)
                    dx = (xp - half_w) / self.K1
                    dy = 2.0 * (half_h - yp) / self.K1

                    # Ray-plane intersection: t*(n·d) = n·center => t = n_dot_c/(n·d)
                    denom = nx * dx + ny * dy + nz
                    if abs(denom) < 1e-6:
                        continue

                    t = n_dot_c / denom
                    if t <= 0.5:  # Behind camera or too close
                        continue

                    # Intersection point: (t*dx, t*dy, t)
                    # Distance from torus center (0, 0, K2)
                    vx = t * dx
                    vy = t * dy
                    vz = t - self.K2
                    dist = math.sqrt(vx * vx + vy * vy + vz * vz)

                    if disk_inner <= dist <= disk_outer:
                        # Brightness peaks near the shadow edge, fades outward.
                        # σ²=2 gives a disk visible ~3 units from peak.
                        brightness = math.exp(-((dist - disk_peak) ** 2) / 2.0)
                        ooz = 1.0 / t
                        char_idx = int(brightness * (len(self.disk_chars) - 1))
                        if char_idx >= 1 and ooz > zbuffer[yp][xp]:
                            zbuffer[yp][xp] = ooz
                            output[yp][xp] = self.disk_chars[min(char_idx, len(self.disk_chars) - 1)]

        # === Pass 2: Black hole shadow (torus-shaped event horizon) ===
        # The donut is hollow in the middle — light from the accretion disk
        # shines through the hole. The dark body is a torus, not a sphere.
        # Parametric torus sampling renders it as opaque black (space chars).
        # Rendered BEFORE the lensed ring so the ring arcs are visible
        # at the edges of the shadow (simulating gravitational lensing).
        #
        # The shadow overwrites unconditionally: any pixel covered by ANY
        # part of the torus (front or back face) is darkened. This prevents
        # the accretion disk from "shining through" the torus body.

        # Shadow torus is slightly larger than the visible torus to
        # guarantee full pixel coverage at the silhouette edges where
        # parametric sampling can miss pixels due to surface curvature.
        R1_shadow = self.R1 * 1.15  # 15% larger tube radius
        R2_shadow = self.R2         # center radius unchanged

        # Track which pixels are shadow (for Pass 3 edge detection)
        is_shadow_pixel = [[False] * self.width for _ in range(self.height)]
        # Track inner tube surface (facing the hole center) — must stay black
        is_inner_surface = [[False] * self.width for _ in range(self.height)]

        theta_spacing = 0.04
        phi_spacing = 0.01

        theta = 0.0
        while theta < 2 * math.pi:
            costheta = math.cos(theta)
            sintheta = math.sin(theta)

            phi = 0.0
            while phi < 2 * math.pi:
                cosphi = math.cos(phi)
                sinphi = math.sin(phi)

                circlex = R2_shadow + R1_shadow * costheta
                circley = R1_shadow * sintheta

                x = circlex * (cosB * cosphi + sinA * sinB * sinphi) - circley * cosA * sinB
                y = circlex * (sinB * cosphi - sinA * cosB * sinphi) + circley * cosA * cosB
                z = self.K2 + cosA * circlex * sinphi + circley * sinA

                if z > 0.5:
                    ooz = 1.0 / z
                    xp = int(half_w + self.K1 * ooz * x)
                    yp = int(half_h - self.K1 / 2 * ooz * y)

                    if 0 <= xp < self.width and 0 <= yp < self.height:
                        # Always mark silhouette for glow/ring edge detection
                        is_shadow_pixel[yp][xp] = True
                        # Only darken if torus surface is closer than what's
                        # already drawn — the accretion disk in front of the
                        # torus remains visible.
                        if ooz > zbuffer[yp][xp]:
                            zbuffer[yp][xp] = ooz
                            output[yp][xp] = ' '
                            # Inner tube surface (costheta < 0) faces the
                            # hole center — must stay black, no lensed ring.
                            is_inner_surface[yp][xp] = (costheta < 0)

                phi += phi_spacing
            theta += theta_spacing

        # Within the shadow silhouette, blank dim disk characters that
        # leaked through due to the disk plane clipping the torus body.
        # Only the bright center of the accretion disk band (where it
        # genuinely passes in front of the torus) should remain visible.
        min_visible_idx = 4  # dim chars below '~' get blanked in shadow
        for yp in range(self.height):
            for xp in range(self.width):
                if is_shadow_pixel[yp][xp] and output[yp][xp] != ' ':
                    idx = self.disk_chars.find(output[yp][xp])
                    if 0 <= idx < min_visible_idx:
                        output[yp][xp] = ' '

        # === Pass 2b: Photon ring glow (bright halo around shadow edge) ===
        # Light concentrates near the unstable photon orbit, creating a
        # bright ring just outside the torus shadow silhouette.
        # Find shadow edge pixels, then brighten nearby non-shadow pixels.
        glow_radius = 2  # pixels of glow around shadow edge
        glow_chars = self.disk_chars

        # First find shadow-edge pixels (shadow pixel with a non-shadow neighbor)
        edge_pixels = []
        for yp in range(self.height):
            for xp in range(self.width):
                if not is_shadow_pixel[yp][xp]:
                    continue
                is_edge = False
                for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
                    ny2 = yp + dy
                    nx2 = xp + dx
                    if 0 <= ny2 < self.height and 0 <= nx2 < self.width:
                        if not is_shadow_pixel[ny2][nx2]:
                            is_edge = True
                            break
                    else:
                        is_edge = True
                        break
                if is_edge:
                    edge_pixels.append((yp, xp))

        # Apply glow around edge pixels
        for ey, ex in edge_pixels:
            for dy in range(-glow_radius, glow_radius + 1):
                for dx in range(-glow_radius, glow_radius + 1):
                    ny2 = ey + dy
                    nx2 = ex + dx
                    if 0 <= ny2 < self.height and 0 <= nx2 < self.width:
                        if is_shadow_pixel[ny2][nx2]:
                            continue
                        d = math.sqrt(dx * dx + dy * dy)
                        if d <= glow_radius:
                            glow_bright = 1.0 - (d / (glow_radius + 1))
                            glow_idx = int(glow_bright * (len(glow_chars) - 1))
                            if glow_idx >= 1:
                                existing_idx = glow_chars.find(output[ny2][nx2])
                                if existing_idx < 0:
                                    existing_idx = 0
                                if glow_idx > existing_idx:
                                    output[ny2][nx2] = glow_chars[min(glow_idx, len(glow_chars) - 1)]

        # === Pass 3: Lensed ring (shadow-edge based) ===
        # The lensed ring represents the gravitationally bent image of the
        # far side of the accretion disk, appearing to arc over the top and
        # under the bottom of the torus shadow.
        # Instead of a parametric circle (which doesn't align with the tilted
        # torus outline), we trace the ACTUAL shadow edge and apply brightness
        # based on vertical distance from the shadow center — bright at
        # top/bottom (perpendicular to the accretion disk), dim at the sides.
        # This guarantees the ring always hugs the shadow silhouette.

        # Find vertical center of shadow
        shadow_y_sum = 0.0
        shadow_count = 0
        for yp in range(self.height):
            for xp in range(self.width):
                if is_shadow_pixel[yp][xp]:
                    shadow_y_sum += yp
                    shadow_count += 1
        shadow_cy = shadow_y_sum / shadow_count if shadow_count > 0 else half_h

        # Apply ring brightness along edge pixels and their neighbors
        ring_radius = 3  # pixels of ring spread outside shadow edge
        ring_chars = self.disk_chars

        for ey, ex in edge_pixels:
            # Vertical distance from shadow center, normalized to [0..1]
            vert_dist = abs(ey - shadow_cy) / (self.height / 2.0)
            vert_dist = min(vert_dist, 1.0)
            # Brightness peaks at top/bottom (large vert_dist)
            ring_bright = vert_dist * vert_dist * 1.5

            for dy in range(-ring_radius, ring_radius + 1):
                for dx in range(-ring_radius, ring_radius + 1):
                    ny2 = ey + dy
                    nx2 = ex + dx
                    if 0 <= ny2 < self.height and 0 <= nx2 < self.width:
                        if is_shadow_pixel[ny2][nx2]:
                            continue
                        if is_inner_surface[ny2][nx2]:
                            continue
                        d = math.sqrt(dx * dx + dy * dy)
                        if d <= ring_radius:
                            falloff = 1.0 - (d / (ring_radius + 1))
                            brightness = ring_bright * falloff
                            char_idx = int(brightness * (len(ring_chars) - 1))
                            char_idx = min(char_idx, len(ring_chars) - 1)
                            if char_idx >= 1:
                                existing_idx = ring_chars.find(output[ny2][nx2])
                                if existing_idx < 0:
                                    existing_idx = 0
                                if char_idx > existing_idx:
                                    output[ny2][nx2] = ring_chars[char_idx]

        #   Print the frame as a single write for flicker-free output
        if display:
            buf = ['\x1b[H']
            for row in output:
                buf.append(''.join(row))
            sys.stdout.write('\n'.join(buf) + '\x1b[J')
            sys.stdout.flush()

        return output

    # Brightness lookup: map each character to a 0.0-1.0 brightness value.
    # Combines both disk_chars and luminance_chars into a single table.
    _CHAR_BRIGHTNESS = {
        ' ': 0.0, '.': 0.05, ',': 0.1, '-': 0.15, '~': 0.2,
        ':': 0.3, ';': 0.4, '=': 0.5, '!': 0.6, '*': 0.7,
        '#': 0.8, '$': 0.9, '@': 1.0,
    }

    def render_frame_pixels(self):
        """Render one frame as a 2D array of brightness floats [0..1].

        Returns:
            List[List[float]]: height x width brightness values.
        """
        output = self.render_frame(display=False)
        pixels = []
        for row in output:
            prow = []
            for ch in row:
                prow.append(self._CHAR_BRIGHTNESS.get(ch, 0.0))
            pixels.append(prow)
        return pixels

    def save_gif(self, path, n_frames=150, fps=30):
        """Render n_frames and save as an animated GIF.

        Args:
            path: Output file path (should end in .gif).
            n_frames: Number of frames to render.
            fps: Frames per second in the output GIF.
        """
        from PIL import Image

        cell_w = 6   # pixels per character cell width
        cell_h = 12  # pixels per character cell height
        img_w = self.width * cell_w
        img_h = self.height * cell_h

        frames = []
        for i in range(n_frames):
            brightness = self.render_frame_pixels()
            img = Image.new('L', (img_w, img_h), 0)
            pix = img.load()
            for yr, row in enumerate(brightness):
                for xc, b in enumerate(row):
                    v = int(b * 255)
                    for dy in range(cell_h):
                        for dx in range(cell_w):
                            pix[xc * cell_w + dx, yr * cell_h + dy] = v
            frames.append(img)
            self.A += 0.04
            self.B += 0.02
            print(f'\rRendering frame {i + 1}/{n_frames}', end='', flush=True)

        print()
        duration_ms = int(1000 / fps)
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
        )
        print(f'Saved {path} ({n_frames} frames, {img_w}x{img_h})')

    def run(self, duration=9e9):
        """
        Run the animation.

        Args:
            duration: How many seconds to run
        """
        self.clear_screen()
        print('\x1b[2J', end='')    # Clear screen
        print('\x1b[?25l', end='')  # Hide cursor

        start_time = time.time()

        try:
            while True:
                self.render_frame()
                self.A += 0.04
                self.B += 0.02
                time.sleep(0.03)

                if time.time() - start_time > duration:
                    break

        except KeyboardInterrupt:
            pass
        finally:
            print('\x1b[?25h', end='')  # Show cursor
            print()


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Interstellar Donut')
    parser.add_argument(
        '--graphics', action='store_true',
        help='Render as pixel graphics and save to a file instead of ASCII animation',
    )
    parser.add_argument(
        '--output', '-o', default='donut.gif',
        help='Output file path for --graphics mode (default: donut.gif)',
    )
    parser.add_argument(
        '--frames', '-n', type=int, default=150,
        help='Number of frames to render in --graphics mode (default: 150)',
    )
    args = parser.parse_args()

    try:
        terminal_size = os.get_terminal_size()
        width = terminal_size.columns
        height = terminal_size.lines - 1
    except OSError:
        width = 80
        height = 24

    if args.graphics:
        donut = InterstellarDonut(width=width, height=height)
        donut.save_gif(args.output, n_frames=args.frames)
    else:
        donut = InterstellarDonut(width=width, height=height)
        print('Interstellar Donut - Press Ctrl+C to exit')
        time.sleep(2)
        donut.run()


if __name__ == "__main__":
    main()
