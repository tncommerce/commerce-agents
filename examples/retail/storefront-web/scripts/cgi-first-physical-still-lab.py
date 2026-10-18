"""DUFYND CGI-first LAB 02: original layered glass/liquid ray transport.

On-demand research only; never invoked in public build or browser runtime.
No external models, stock photographs, paid APIs or generated credits.
"""

import argparse
import hashlib
import json
import math
import os
import time

import numpy as np
from numba import njit, prange
from PIL import Image, ImageDraw, ImageFont

# materials: 0 air, 1 optical glass, 2 perfumed fluid
# object surface: 1 outer shell, 2 inner shell, 3 liquid-air, 4 cap, 5 neck, 6 label, 7 cap gold, 8 atomizer
TINY = 1.0e-4


@njit
def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


@njit
def vlen(a):
    return np.sqrt(vdot(a, a))


@njit
def vnorm(a):
    return a / max(1.0e-12, vlen(a))


@njit
def vref(d, n):
    return d - 2.0 * vdot(d, n) * n


@njit
def vrefract(d, n, eta):
    c = -vdot(d, n)
    k = 1.0 - eta * eta * (1.0 - c * c)
    if k < 0.0:
        return vref(d, n), False
    return vnorm(eta * d + (eta * c - np.sqrt(k)) * n), True


@njit
def sdf_round3(x, y, z, ax, lo, hi, az, r):
    # Exact distance to a filleted 3D glass ingot: real curved shoulders/foot.
    qx = abs(x) - (ax - r)
    qy = abs(y - (lo + hi) * 0.5) - ((hi - lo) * 0.5 - r)
    qz = abs(z) - (az - r)
    return (
        np.sqrt(max(qx, 0.0) ** 2 + max(qy, 0.0) ** 2 + max(qz, 0.0) ** 2)
        + min(max(qx, qy, qz), 0.0)
        - r
    )


@njit
def fluid_surface(x, z):
    # Physical meniscus rises only near the inner cavity wall.
    p = 3.3333333333333
    radius = (abs(x / 0.985) ** p + abs(z / 0.476) ** p) ** (1.0 / p)
    gap = max(0.0, 1.0 - radius) * 0.476
    return 1.971 + 0.019 * math.exp(-gap / 0.032)


@njit
def cap_sdf(pos, shift_x, shift_y):
    # Actual chamfered cap cylinder rather than a painted edge.
    x = pos[0] - shift_x
    z = pos[2]
    y = pos[1] - (3.13 + shift_y)
    bevel = 0.044
    radial = math.sqrt(x * x + z * z) - (0.489 - bevel)
    vertical = abs(y) - (0.345 - bevel)
    return (
        math.sqrt(max(radial, 0.0) ** 2 + max(vertical, 0.0) ** 2)
        + min(max(radial, vertical), 0.0)
        - bevel
    )


@njit
def opening_cap_rise(viewport_width):
    # Same 320/390/desktop opening travel as the public WebGL controller.
    if viewport_width < 360:
        return 0.74
    if viewport_width < 601:
        return 0.78
    return 1.04


@njit
def opening_atomizer_rise(viewport_width):
    if viewport_width < 360:
        return 0.24
    if viewport_width < 601:
        return 0.33
    return 0.46


@njit
def hit_cap(o, d, opened, viewport_width):
    shift_y = opening_cap_rise(viewport_width) if opened else 0.0
    shift_x = 0.34 if opened else 0.0
    # Cheap analytic bound limits the raymarch.
    bound, _ = hit_cylinder(o, d, shift_x, 0.0, 0.0, 0.52, 2.765 + shift_y, 3.50 + shift_y)
    if bound > 1.0e12:
        return 1.0e15, np.zeros(3)
    t = max(0.0001, bound - 0.08)
    for _ in range(72):
        pt = o + d * t
        dist = cap_sdf(pt, shift_x, shift_y)
        if abs(dist) < 0.0003:
            e = 0.0005
            n = np.array(
                (
                    cap_sdf(pt + np.array((e, 0.0, 0.0)), shift_x, shift_y)
                    - cap_sdf(pt - np.array((e, 0.0, 0.0)), shift_x, shift_y),
                    cap_sdf(pt + np.array((0.0, e, 0.0)), shift_x, shift_y)
                    - cap_sdf(pt - np.array((0.0, e, 0.0)), shift_x, shift_y),
                    cap_sdf(pt + np.array((0.0, 0.0, e)), shift_x, shift_y)
                    - cap_sdf(pt - np.array((0.0, 0.0, e)), shift_x, shift_y),
                )
            )
            return t, vnorm(n)
        t += max(0.0002, abs(dist) * 0.72)
        if t > bound + 0.90:
            break
    return 1.0e15, np.zeros(3)


@njit
def medium(x, y, z):
    if sdf_round3(x, y, z, 1.08, 0.31, 2.62, 0.57, 0.16) < 0.0:
        if sdf_round3(x, y, z, 0.985, 0.48, 2.46, 0.476, 0.102) < 0.0:
            if y <= fluid_surface(x, z):
                return 2
            return 0
        return 1
    return 0


@njit
def roundbox(x, z, ax, az, r):
    dx = abs(x) - (ax - r)
    dz = abs(z) - (az - r)
    return np.sqrt(max(dx, 0.0) ** 2 + max(dz, 0.0) ** 2) + min(max(dx, dz), 0.0) - r


@njit
def hit_round3(o, d, ax, lo, hi, az, r):
    # A true 3D signed distance field provides a continuous optical normal.
    # Sphere tracing steps are conservative; no screen-space bottle tint.
    t = 0.0
    for _step in range(68):
        x = o[0] + d[0] * t
        y = o[1] + d[1] * t
        z = o[2] + d[2] * t
        dist = sdf_round3(x, y, z, ax, lo, hi, az, r)
        if abs(dist) < 0.0004 and t > 0.0002:
            eps = 0.0006
            dx = sdf_round3(x + eps, y, z, ax, lo, hi, az, r) - sdf_round3(
                x - eps, y, z, ax, lo, hi, az, r
            )
            dy = sdf_round3(x, y + eps, z, ax, lo, hi, az, r) - sdf_round3(
                x, y - eps, z, ax, lo, hi, az, r
            )
            dz = sdf_round3(x, y, z + eps, ax, lo, hi, az, r) - sdf_round3(
                x, y, z - eps, ax, lo, hi, az, r
            )
            return t, vnorm(np.array((dx, dy, dz)))
        t += max(0.00035, abs(dist) * 0.83)
        if t > 25.0:
            break
    return 1.0e15, np.zeros(3)


@njit
def hit_cylinder(o, d, x, y, z, r, lo, hi):
    dx = o[0] - x
    dz = o[2] - z
    a = d[0] * d[0] + d[2] * d[2]
    b = dx * d[0] + dz * d[2]
    c = dx * dx + dz * dz - r * r
    best = 1.0e15
    N = np.zeros(3)
    if a > 1.0e-9:
        discr = b * b - a * c
        if discr >= 0:
            sq = np.sqrt(discr)
            for t in ((-b - sq) / a, (-b + sq) / a):
                if t > 1.0e-4 and t < best and lo <= o[1] + d[1] * t <= hi:
                    best = t
                    N[0] = (dx + d[0] * t) / r
                    N[1] = 0
                    N[2] = (dz + d[2] * t) / r
    if abs(d[1]) > 1.0e-9:
        for yy, s in ((lo, -1.0), (hi, 1.0)):
            t = (yy - o[1]) / d[1]
            if t > 1.0e-4 and t < best and (dx + d[0] * t) ** 2 + (dz + d[2] * t) ** 2 <= r * r:
                best = t
                N[0] = 0.0
                N[1] = s
                N[2] = 0.0
    return best, N


@njit
def hit_metal(o, d, opened, viewport_width):
    # caps/neck/atomizer, immutable studio geometry for self-contained render
    # returns t, material, normal
    tt = 1.0e15
    kind = 0
    N = np.zeros(3)
    # Black cap: exploded in 'open' state but kept as a real 3D solid
    cap_y_shift = opening_cap_rise(viewport_width) if opened else 0.0
    cap_x_shift = 0.34 if opened else 0.0
    atomizer_y_shift = opening_atomizer_rise(viewport_width) if opened else 0.0
    atomizer_x_shift = -0.10 if opened else 0.0
    tcap, ncap = hit_cap(o, d, opened, viewport_width)
    if tcap < tt:
        tt = tcap
        kind = 4
        N = ncap
    for x, z, r, y0, y1, k in (
        (cap_x_shift, 0.0, 0.496, 2.787 + cap_y_shift, 2.805 + cap_y_shift, 7),
        # Collar, rim and sprayer move as one spatial atomizer, never as
        # disconnected decorative rings; the glass neck stays on the vessel.
        (
            atomizer_x_shift,
            0.0,
            0.360,
            2.67 + atomizer_y_shift,
            2.87 + atomizer_y_shift,
            7,
        ),
        (
            atomizer_x_shift,
            0.0,
            0.362,
            2.698 + atomizer_y_shift,
            2.72 + atomizer_y_shift,
            7,
        ),
        (
            atomizer_x_shift,
            0.0,
            0.190,
            2.83 + atomizer_y_shift,
            3.17 + atomizer_y_shift,
            7,
        ),
        (0.0, 0.0, 0.245, 2.62, 2.87, 5),
    ):
        t, n = hit_cylinder(o, d, x, 0.0, z, r, y0, y1)
        if t < tt:
            tt = t
            kind = k
            N = n
    return tt, kind, N


@njit
def hit_scene(o, d, opened, viewport_width):
    tt = 1.0e15
    N = np.zeros(3)
    kind = 0
    t, n = hit_round3(o, d, 1.08, 0.31, 2.62, 0.57, 0.16)
    if t < tt:
        tt = t
        kind = 1
        N = n
    t, n = hit_round3(o, d, 0.985, 0.48, 2.46, 0.476, 0.102)
    if t < tt:
        tt = t
        kind = 2
        N = n
    # Ray-solved curved air/fluid interface, with genuine normal.
    if abs(d[1]) > 1.0e-7:
        t = (1.984 - o[1]) / d[1]
        for _ in range(4):
            x = o[0] + d[0] * t
            z = o[2] + d[2] * t
            t += (fluid_surface(x, z) - (o[1] + d[1] * t)) / d[1]
        if t > 1.0e-4 and t < tt:
            x, y, z = o + d * t
            if sdf_round3(x, y, z, 0.985, 0.48, 2.46, 0.476, 0.102) < -1.0e-6:
                e = 0.002
                dx = (fluid_surface(x + e, z) - fluid_surface(x - e, z)) / (2.0 * e)
                dz = (fluid_surface(x, z + e) - fluid_surface(x, z - e)) / (2.0 * e)
                tt = t
                kind = 3
                N = vnorm(np.array((-dx, 1.0, -dz)))
    # A deeply embossed separate brand-label panel with 3D shadow edges.
    if abs(d[2]) > 1.0e-7:
        t = (0.588 - o[2]) / d[2]
        x = o[0] + d[0] * t
        y = o[1] + d[1] * t
        if t > 1.0e-4 and t < tt and abs(x) < 0.635 and 0.97 < y < 1.925 and d[2] < 0.0:
            tt = t
            kind = 6
            N = np.array((0.0, 0.0, 1.0))
    t, k, n = hit_metal(o, d, opened, viewport_width)
    if t < tt:
        tt = t
        kind = k
        N = n
    return tt, kind, N


@njit
def rect_glow(d, center, spread_x, spread_y, intensity):
    # Smooth angular rectangular softbox, not an arbitrary bottle overlay.
    vec = vnorm(center)
    u = np.array((vec[2], 0.0, -vec[0]))
    u = vnorm(u)
    v = np.cross(u, vec)
    c = vdot(d, vec)
    if c < 0.7:
        return 0.0
    x = vdot(d, u) / c
    y = vdot(d, v) / c
    # feathered area panel highlights
    aa = np.sqrt((x / max(0.001, spread_x)) ** 4 + (y / max(0.001, spread_y)) ** 4)
    edge = max(0.0, min(1.0, (1.21 - aa) * 5.0))
    return intensity * edge * edge * (3.0 - 2.0 * edge)


@njit
def env(d, mask=1.0):
    # matte champaign backdrop in transmission, deep dark flags in reflection,
    # four physically directioned studio panels.
    horizon = min(1.0, max(0.48, 0.86 + 0.12 * d[1]))
    C = np.array((1.03 * horizon, 0.86 * horizon, 0.70 * horizon))
    # softboxes: intentional broad strips, amber bounce and opposing dark flag
    s = rect_glow(d, np.array((-3.5, 2.2, 5.0)), 0.14, 0.9, 3.9)
    C += s * np.array((1.0, 0.88, 0.70))
    s = rect_glow(d, np.array((3.4, 3.0, 5.5)), 0.065, 0.76, 4.8)
    C += s * np.array((0.83, 0.92, 1.0))
    s = rect_glow(d, np.array((-1.4, 7.0, -3.0)), 0.49, 0.28, 2.3)
    C += s * np.array((1.0, 0.94, 0.83))
    s = rect_glow(d, np.array((2.2, 3.0, -5.0)), 0.25, 0.85, 2.5)
    C += s * np.array((1.0, 0.60, 0.32))
    s = rect_glow(d, np.array((4.0, 0.8, 4.0)), 0.12, 0.85, 0.68)
    C -= s * np.array((0.47, 0.42, 0.39))
    return np.maximum(0.0, C)


@njit
def refraction_env(o, d):
    # A physically placed studio diffusion plane behind the vessel.
    # The glass/fluid rays genuinely bend across the backlight spatial field.
    # Gaussian photographic flags avoid rectangular silhouettes in the liquid.
    C = env(d)
    if d[2] < -0.035:
        t = (-3.5 - o[2]) / d[2]
        if t > 0.0 and t < 70.0:
            x = o[0] + d[0] * t
            y = o[1] + d[1] * t
            key = np.exp(-0.5 * ((x + 0.71) / 0.34) ** 2) * np.exp(-0.5 * ((y - 1.65) / 2.7) ** 2)
            broad = np.exp(-0.5 * ((x - 0.25) / 0.84) ** 2) * np.exp(
                -0.5 * ((y - 1.55) / 2.25) ** 2
            )
            rim = np.exp(-0.5 * ((x - 1.39) / 0.19) ** 2) * np.exp(-0.5 * ((y - 1.65) / 2.5) ** 2)
            neg = np.exp(-0.5 * ((x - 0.84) / 0.33) ** 2) * np.exp(-0.5 * ((y - 1.62) / 2.65) ** 2)
            C += key * np.array((1.75, 1.50, 1.15))
            C += broad * np.array((0.34, 0.24, 0.19))
            C += rim * np.array((0.89, 1.03, 1.10))
            C -= neg * np.array((0.67, 0.62, 0.56))
    return np.maximum(C, 0.02)


@njit
def fresnel(n1, n2, cosi):
    r = ((n1 - n2) / (n1 + n2)) ** 2
    return r + (1.0 - r) * (1.0 - cosi) ** 5


@njit
def label_sample(x, y, tex):
    u = (x + 0.635) / 1.27
    v = (1.925 - y) / 0.955
    col = min(tex.shape[1] - 1, max(0, int(u * (tex.shape[1] - 1))))
    row = min(tex.shape[0] - 1, max(0, int(v * (tex.shape[0] - 1))))
    color = np.array((tex[row, col, 0], tex[row, col, 1], tex[row, col, 2])) / 255.0
    # seam lighting and gold foil variation / slight raised stamping
    illum = 0.78 + 0.18 * max(0.0, min(1.0, (x + 0.635) / 1.27))
    return color * illum


@njit
def shade_metal(kind, n, d, p):
    # dark metallic PBR with Fresnel reflection of the softboxes
    r = vnorm(vref(d, n))
    rr = env(r)
    nd = max(0.0, -vdot(d, n))
    if kind == 4:
        # dark brushed anodised cap, bright metallic edge and warm highlights
        base = np.array((0.016, 0.014, 0.013))
        color = base * 0.55 + rr * 0.095
        stripe = 0.5 + 0.5 * np.sin(p[1] * 610.0)
        color += np.array((0.013, 0.01, 0.006)) * stripe
    elif kind == 7:
        base = np.array((0.27, 0.16, 0.060))
        color = base * 0.20 + rr * np.array((0.80, 0.61, 0.28)) * 0.46
    else:
        base = np.array((0.055, 0.04, 0.027))
        color = base * 0.25 + rr * np.array((0.62, 0.53, 0.38)) * 0.35
    # bevel appearance through axial location-based Fresnel
    return color * (0.86 + 0.14 * (1.0 - nd) ** 2)


@njit
def trace(o, d, tex, opened, viewport_width):
    # Iterative forward ray transport with Fresnel reflection highlights.
    # Weighted deterministic branch avoids Monte Carlo white noise in stills.
    result = np.zeros(3)
    throughput = np.ones(3)
    hit_any = 0
    fluid_distance = 0.0
    for _bounce in range(11):
        t, kind, n = hit_scene(o, d, opened, viewport_width)
        if t > 1.0e12:
            result += throughput * refraction_env(o, d)
            return result, 0.08 + 0.92 * (
                1.0
                - (
                    math.exp(-0.15 * fluid_distance)
                    + math.exp(-0.92 * fluid_distance)
                    + math.exp(-2.05 * fluid_distance)
                )
                / 3.0
            ) if hit_any else 0.0
        p = o + d * t
        hit_any = 1
        if kind >= 4 and kind != 6:
            result += throughput * shade_metal(kind, n, d, p)
            return result, 1
        if kind == 6:
            texcol = label_sample(p[0], p[1], tex)
            r = vref(d, n)
            result += throughput * (texcol * 0.57 + env(r) * 0.020)
            return result, 1
        before = medium(o[0], o[1], o[2])
        after = medium(p[0] + d[0] * 0.0018, p[1] + d[1] * 0.0018, p[2] + d[2] * 0.0018)
        if before == after:
            o = p + d * 0.002
            continue
        if before == 2:
            absorption = np.array((0.15, 0.92, 2.05))
            throughput *= np.exp(-absorption * t)
            fluid_distance += t
        if before == 1 and after == 2:
            n1 = 1.52
            n2 = 1.339
        elif before == 2 and after == 1:
            n1 = 1.339
            n2 = 1.52
        elif before == 2 and after == 0:
            n1 = 1.339
            n2 = 1.0
        elif before == 0 and after == 2:
            n1 = 1.0
            n2 = 1.339
        elif before == 1 and after == 0:
            n1 = 1.52
            n2 = 1.0
        elif before == 0 and after == 1:
            n1 = 1.0
            n2 = 1.52
        else:
            n1 = 1.0
            n2 = 1.0
        nn = n if vdot(d, n) < 0 else -n
        cosi = max(0.0, min(1.0, -vdot(d, nn)))
        refl = vnorm(vref(d, nn))
        F = fresnel(n1, n2, cosi)
        refr, possible = vrefract(d, nn, n1 / n2)
        if not possible:
            d = refl
            o = p + d * 0.002
            continue
        # reflected studio highlights are real env specular, keep direction
        # behind camera and off-axis sources physically varied across surface
        result += throughput * F * env(refl)
        throughput *= 1.0 - F
        o = p + refr * 0.002
        d = refr
        if max(throughput) < 0.003:
            break
    result += throughput * refraction_env(o, d)
    return result, 0.08 + 0.92 * (
        1.0
        - (
            math.exp(-0.15 * fluid_distance)
            + math.exp(-0.92 * fluid_distance)
            + math.exp(-2.05 * fluid_distance)
        )
        / 3.0
    )


@njit
def tonemap(c):
    # ACES-inspired HDR map followed by perceptual transfer
    x = c * 0.82
    v = (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14)
    v = np.maximum(0.0, np.minimum(1.0, v))
    return np.power(v, 1.0 / 2.2)


@njit(parallel=True)
def render(width, height, samples, opened, tex, viewport_width):
    out = np.empty((height, width, 3), dtype=np.uint8)
    mask = np.empty((height, width), dtype=np.uint8)
    aspect = width / height
    # A fixed narrow-frustum desktop opening clips the actual 1.04-unit cap lift.
    # Author the research still separately for mobile vs desktop viewport poses.
    if opened and viewport_width >= 601:
        campos = np.array((3.70, 3.65, 10.05))
    elif opened:
        campos = np.array((3.70, 3.45, 9.30))
    else:
        campos = np.array((3.3, 3.05, 8.2))
    center_y = 2.24 if opened and viewport_width >= 601 else 2.06
    center = np.array((0.0, center_y, 0.0)) if opened else np.array((0.0, 1.82, 0.0))
    fw = vnorm(center - campos)
    right = vnorm(np.cross(fw, np.array((0.0, 1.0, 0.0))))
    up = vnorm(np.cross(right, fw))
    field_of_view = 29.2 if opened and viewport_width >= 601 else 26.8
    size = math.tan(math.radians(field_of_view) / 2.0)
    for py in prange(height):
        for px in range(width):
            col = np.zeros(3)
            hit = 0
            for sy in range(samples):
                ix = px + (sy * 0.61803398875) % 1.0
                iy = py + (sy * 0.75487766625) % 1.0
                u = (ix / width - 0.5) * 2 * size * aspect
                v = (0.5 - iy / height) * 2 * size
                direction = vnorm(fw + u * right + v * up)
                c, h = trace(campos, direction, tex, opened, viewport_width)
                col += c
                hit += h
            col = tonemap(col / samples)
            # Undo transmitted ivory background energy for real straight RGBA.
            backing = np.array((235.0 / 255.0, 225.0 / 255.0, 209.0 / 255.0))
            opacity = min(1.0, max(0.0, hit / samples))
            for ch in range(3):
                if col[ch] > backing[ch]:
                    lo = (col[ch] - backing[ch]) / max(0.00001, 1.0 - backing[ch])
                else:
                    lo = (backing[ch] - col[ch]) / backing[ch]
                if opacity > 0.0:
                    opacity = max(opacity, lo)
            opacity = min(1.0, max(0.0, opacity))
            if opacity > 0.00001:
                col = np.maximum(0.0, np.minimum(1.0, (col - (1.0 - opacity) * backing) / opacity))
            for ch in range(3):
                out[py, px, ch] = int(max(0, min(255, col[ch] * 255)))
            mask[py, px] = round(opacity * 255)
    return out, mask


def make_label():
    w, h = 920, 690
    a = Image.new("RGB", (w, h), (19, 18, 16))
    draw = ImageDraw.Draw(a)
    draw.rectangle((16, 16, w - 17, h - 17), outline=(164, 122, 67), width=7)
    draw.rectangle((26, 26, w - 27, h - 27), outline=(72, 57, 37), width=2)
    serif = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
    sans = "/usr/share/fonts/truetype/lato/Lato-Semibold.ttf"
    light = "/usr/share/fonts/truetype/lato/Lato-Regular.ttf"

    def centered(y, txt, font, color):
        left, _, right, _ = draw.textbbox((0, 0), txt, font=font)
        draw.text(((w - (right - left)) / 2, y), txt, font=font, fill=color)

    centered(110, "D U F Y N D", ImageFont.truetype(sans, 40), (199, 152, 86))
    draw.line((w * 0.34, 206, w * 0.66, 206), fill=(140, 103, 61), width=2)
    centered(230, "n° 01", ImageFont.truetype(serif, 170), (221, 177, 114))
    centered(514, "MAISON DE PARFUM", ImageFont.truetype(light, 27), (157, 116, 71))
    draw.line((w * 0.41, 577, w * 0.59, 577), fill=(113, 87, 53), width=2)
    return np.asarray(a, dtype=np.uint8)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=560)
    parser.add_argument("--height", type=int, default=620)
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--out", default=".cgi-lab/perfume-study-closed.png")
    parser.add_argument("--open", action="store_true")
    parser.add_argument(
        "--viewport-width",
        type=int,
        choices=(320, 390, 1440),
        default=320,
        help="Target WebGL opening pose; independent of output image resolution.",
    )
    args = parser.parse_args()
    if not (240 <= args.width <= 1600 and 240 <= args.height <= 1600 and 1 <= args.samples <= 20):
        parser.error("lab render limits: 240..1600 px, 1..20 samples")
    out = os.path.realpath(os.path.abspath(args.out))
    if not out.lower().endswith(".png") or "/public/" in out.replace("\\", "/"):
        parser.error("internal lab output must be a PNG outside storefront public/")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tex = make_label()
    started = time.monotonic()
    img, mask = render(args.width, args.height, args.samples, args.open, tex, args.viewport_width)
    rgba = np.dstack((img, mask)).astype(np.uint8)
    # Fail closed on missing product or cropped silhouette.
    populated = np.nonzero(mask >= 8)
    if not len(populated[0]) or int(mask.max()) < 254:
        raise RuntimeError("CGI study is empty or has no opaque label/metal pixels")
    top, bottom = int(populated[0].min()), int(populated[0].max())
    left, right = int(populated[1].min()), int(populated[1].max())
    if min(top, left, args.height - 1 - bottom, args.width - 1 - right) < 6:
        raise RuntimeError("CGI study clips a product silhouette at the output edge")
    Image.fromarray(rgba, "RGBA").save(out)
    bg = Image.new("RGB", (args.width, args.height), (235, 225, 209))
    bg.paste(Image.fromarray(rgba, "RGBA"), (0, 0), Image.fromarray(rgba, "RGBA"))
    bg.save(out[:-4] + "-preview.jpg", quality=93)
    with open(__file__, "rb") as source_file:
        renderer_hash = hashlib.sha256(source_file.read()).hexdigest()
    with open(out, "rb") as image_file:
        image_hash = hashlib.sha256(image_file.read()).hexdigest()
    report = {
        "status": "INTERNAL_NOT_APPROVED",
        "scene": "dufynd-cgi-first-lab-02",
        "renderer_sha256": renderer_hash,
        "image_sha256": image_hash,
        "size": [args.width, args.height],
        "samples": args.samples,
        "pose": "open" if args.open else "closed",
        "reference_viewport_width": args.viewport_width,
        "cap_rise": float(opening_cap_rise(args.viewport_width)) if args.open else 0.0,
        "atomizer_rise": float(opening_atomizer_rise(args.viewport_width)) if args.open else 0.0,
        "alpha_bbox_xyxy": [left, top, right, bottom],
        "alpha_max": int(mask.max()),
        "alpha_zero_corners": all(
            mask[y, x] == 0
            for y, x in (
                (0, 0),
                (0, args.width - 1),
                (args.height - 1, 0),
                (args.height - 1, args.width - 1),
            )
        ),
        "runtime_seconds": round(time.monotonic() - started, 2),
        "note": "Internal CGI research only. No public poster replacement or quality approval.",
    }
    with open(out[:-4] + "-evidence.json", "w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)
        file.write("\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
