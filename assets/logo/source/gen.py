"""Mellon logo: SVG variants traced from the approved reference image."""
import sys

GREEN, GOLD = "#1F4D3A", "#C9A24B"
OX, OY = 291.5, 66  # shift logo bbox into a 440x440 canvas


def cr(pts):
    """Catmull-Rom through pts -> cubic bezier path data."""
    p = [pts[0]] + list(pts) + [pts[-1]]
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def cont(pts):
    return cr(pts).replace("M", "L", 1)


def conv(pts, ox, oy):
    return [(x / 3 + ox, y / 3 + oy) for x, y in pts]


# ---- LEFT leaf (Terreno) ----
L_top = conv([(45, 40), (200, 65), (330, 110), (400, 155)], 315, 195)
L_left = conv([(392, 775), (385, 740), (340, 660), (250, 570), (110, 440), (40, 290), (25, 150), (45, 40)], 315, 195)
left_fill = cr(L_top) + f" L{L_left[0][0]:.1f},{L_left[0][1]:.1f} " + cont(L_left) + " Z"
left_edge = cr(L_left) + " " + cont(L_top)
LEFT_VEINS = [
    [(40, 165), (90, 160), (125, 125), (150, 70)],
    [(40, 220), (120, 215), (175, 170), (205, 85)],
    [(45, 280), (130, 285), (200, 260), (230, 190), (262, 100)],
    [(60, 345), (150, 355), (235, 350), (265, 300), (275, 230), (320, 125)],
    [(85, 405), (200, 420), (280, 425), (315, 385), (320, 300), (345, 215), (375, 150)],
    [(132, 470), (240, 495), (335, 510), (368, 440), (378, 340), (398, 255)],
    [(335, 510), (360, 575), (380, 660), (392, 775)],
]
LEFT_SIMPLE = [LEFT_VEINS[1], LEFT_VEINS[3], LEFT_VEINS[5], LEFT_VEINS[6]]

# ---- RIGHT leaf (Rigor) ----
R_top = conv([(390, 42), (250, 62), (110, 115), (35, 152)], 565, 195)
R_right = conv([(390, 42), (408, 140), (402, 235), (362, 360), (300, 460), (200, 550), (110, 625), (60, 690), (40, 775)], 565, 195)
tail = conv([(36, 775)], 565, 195)[0]
right_fill = cr(R_right) + f" L{tail[0]:.1f},{tail[1]:.1f} " + cont(list(reversed(R_top))) + " Z"
right_edge = cr(list(reversed(R_top))) + " " + cont(R_right)
RIGHT_VEINS = [
    [(40, 775), (45, 650), (70, 570), (88, 530), (160, 385), (250, 250), (330, 150), (385, 55)],
    [(95, 520), (200, 478), (336, 412)],
    [(175, 372), (290, 332), (378, 296)],
    [(258, 242), (330, 215), (384, 200)],
    [(78, 148), (79, 340), (82, 538)],
    [(158, 100), (158, 240), (158, 380)],
    [(243, 82), (243, 160), (243, 245)],
]
RIGHT_SIMPLE = [RIGHT_VEINS[0], RIGHT_VEINS[1], RIGHT_VEINS[2], RIGHT_VEINS[4], RIGHT_VEINS[5]]

# ---- CENTRE leaf (Alianza) ----
mx = lambda pts: [(423 - x, y) for x, y in pts]
C_left = [(211.5, 28), (110, 130), (50, 260), (28, 400), (40, 540), (112, 705), (188, 805), (211.5, 888)]
centre_out = cr(conv(C_left, 440, 110)) + " " + cont(conv(list(reversed(mx(C_left)))[1:], 440, 110)) + " Z"
ARC = [(22, 412), (70, 440), (130, 500), (180, 590), (207, 700), (212, 800), (211.5, 885)]
CENTRE_ARCS = [ARC, mx(ARC)]
CENTRE_VEINS = [
    [(211.5, 890), (210, 780), (203, 660), (208, 560), (215, 450), (222, 380), (232, 300), (222, 230), (206, 182)],
    [(218, 448), (190, 400), (160, 350), (143, 290)],
    [(230, 442), (270, 410), (295, 370), (308, 325)],
]


def veins(simple):
    L = LEFT_SIMPLE if simple else LEFT_VEINS
    R = RIGHT_SIMPLE if simple else RIGHT_VEINS
    return ([cr(conv(v, 315, 195)) for v in L] + [cr(conv(v, 565, 195)) for v in R]
            + [cr(conv(v, 440, 110)) for v in CENTRE_VEINS + CENTRE_ARCS])


def svg(variant="color", simple=False):
    ow = 6.5 if simple else 5
    vw = 7 if simple else 3.6
    vd = veins(simple)
    t = f"translate({-OX} {-OY})"
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 440" width="440" height="440" role="img" aria-label="Mellon">\n'
    vpaths = "\n".join(f'<path d="{d}"/>' for d in vd)
    if variant == "color":
        body = f'''<g transform="{t}" stroke-linecap="round" stroke-linejoin="round">
<path d="{left_fill}" fill="{GREEN}"/>
<path d="{right_fill}" fill="{GREEN}"/>
<path d="{left_edge}" fill="none" stroke="{GOLD}" stroke-width="{ow}"/>
<path d="{right_edge}" fill="none" stroke="{GOLD}" stroke-width="{ow}"/>
<path d="{centre_out}" fill="{GREEN}" stroke="{GOLD}" stroke-width="{ow}"/>
<g fill="none" stroke="{GOLD}" stroke-width="{vw}">
{vpaths}
</g></g>
'''
    else:
        ink = {"black": "#111111", "green": GREEN, "white": "#FFFFFF"}[variant]
        body = f'''<defs><mask id="cut" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="572">
<rect width="1024" height="572" fill="#fff"/>
<g fill="none" stroke="#000" stroke-linecap="round" stroke-linejoin="round">
<path d="{centre_out}" stroke-width="{ow + 1.5}"/>
<g stroke-width="{vw + 1.4}">
{vpaths}
</g></g></mask></defs>
<g transform="{t}" fill="{ink}" stroke="{ink}" stroke-width="{ow}" stroke-linejoin="round" mask="url(#cut)">
<path d="{left_fill}"/><path d="{right_fill}"/><path d="{centre_out}"/>
</g>
'''
    return head + body + "</svg>\n"


VARIANTS = [("mellon-logo", "color", False), ("mellon-logo-simple", "color", True),
            ("mellon-logo-black", "black", False), ("mellon-logo-green", "green", False),
            ("mellon-logo-white", "white", False),
            ("mellon-logo-simple-black", "black", True), ("mellon-logo-simple-white", "white", True)]

if __name__ == "__main__":
    for name, v, s in VARIANTS:
        open(f"{sys.argv[1]}/{name}.svg", "w").write(svg(v, s))
