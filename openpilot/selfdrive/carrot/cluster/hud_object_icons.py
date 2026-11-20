"""Small screen-space pictograms for road objects on the external HUD."""
from functools import lru_cache

import pyray as rl


# Geometry is authored on a 32 px square. The dark backing keeps cutouts and
# wheels legible over both bright camera imagery and the night driving scene.
_BACK = (19, 29, 40, 255)
_LIGHT = (249, 249, 239, 255)
_TINT = {
    "person": (255, 211, 117, 255),
    "motorcycle": (255, 183, 69, 255),
    "bicycle": (114, 229, 180, 255),
    "cone": (255, 137, 68, 255),
    "car": (143, 216, 245, 255),
    "bus": (151, 225, 229, 255),
    "truck": (149, 198, 250, 255),
}


@lru_cache(maxsize=len(_TINT))
def _drawing(kind):
    tint = _TINT[kind]
    commands = []

    def rounded(x, y, w, h, roundness, color):
        commands.append((rl.draw_rectangle_rounded, (rl.Rectangle(x, y, w, h), roundness, 4, color)))

    def disk(x, y, radius, color):
        commands.append((rl.draw_poly, (rl.Vector2(x, y), 16, radius, 0., color)))

    def stroke(*points, width, color):
        vertices = [rl.Vector2(*p) for p in points]
        for start, end in zip(vertices, vertices[1:]):
            commands.append((rl.draw_line_ex, (start, end, width, color)))

    def fill(*points, color):
        # All filled contours below are convex. Raylib culls clockwise faces
        # in its 2D projection (the screen's y axis points down).
        area = sum(x * y2 - y * x2 for (x, y), (x2, y2) in zip(points, points[1:] + points[:1]))
        vertices = [rl.Vector2(*point) for point in (reversed(points) if area > 0 else points)]
        for corner, following in zip(vertices[1:], vertices[2:]):
            commands.append((rl.draw_triangle, (vertices[0], corner, following, color)))

    def wheel(x, y, radius, thick):
        disk(x, y, radius, _LIGHT)
        disk(x, y, radius - thick, _BACK)

    rounded(0, 0, 32, 32, .46, _BACK)
    rounded(.8, .8, 30.4, 30.4, .42, tint)
    rounded(2.2, 2.2, 27.6, 27.6, .37, _BACK)

    if kind == "person":
        # Walking side profile: offset head, bent elbows and a long stride.
        disk(18, 7, 2.6, _LIGHT)
        stroke((16.9, 10.4), (14, 17.7), width=4.0, color=tint)
        stroke((16.3, 10.8), (12.3, 12.4), (9, 16.8), width=2.1, color=tint)
        stroke((16.2, 11.6), (19.4, 15.4), (23, 16.6), width=2.1, color=tint)
        stroke((14.2, 17.1), (12.2, 22.2), (8.6, 26), width=2.7, color=_LIGHT)
        stroke((15.3, 17.2), (19.7, 20.7), (21.8, 26.1), width=2.7, color=_LIGHT)
    elif kind == "motorcycle":
        wheel(8, 21, 4.5, 1.9)
        wheel(24, 21, 4.5, 1.9)
        stroke((8, 21), (13.2, 18.2), (17.5, 21), width=2, color=tint)
        fill((6.1, 13.1), (12.5, 13.5), (17.4, 16.4), (16.1, 19.2),
             (12.2, 18.6), color=tint)
        fill((13.2, 15), (15.7, 11.5), (20.2, 12.1), (20.8, 15),
             (17.9, 17), color=tint)
        stroke((17.3, 9.1), (20.1, 9.6), (24, 21.1), width=1.9, color=_LIGHT)
        rounded(20.1, 11.4, 4.3, 2.6, .4, _LIGHT)
    elif kind == "bicycle":
        for x in (8.2, 23.8):
            wheel(x, 21.2, 4.8, 1.15)
            stroke((x, 17.1), (x, 25.3), width=1.05, color=tint)
        stroke((8.2, 21.2), (12.4, 13.9), (16, 21.2), (8.2, 21.2), width=1.65, color=tint)
        stroke((12.4, 13.9), (20.1, 13.2), (16, 21.2), width=1.65, color=tint)
        stroke((23.8, 21.2), (19.4, 10), (23, 9), width=1.6, color=_LIGHT)
        stroke((12.4, 13.9), (11.7, 11.3), width=1.4, color=_LIGHT)
        stroke((9.1, 11.2), (14.1, 11.2), width=1.8, color=_LIGHT)
    elif kind == "cone":
        fill((15, 5.7), (17, 5.7), (23, 23.8), (9, 23.8), color=tint)
        fill((13.5, 10.2), (18.5, 10.2), (19.5, 13.2), (12.5, 13.2), color=_LIGHT)
        fill((11, 17.8), (21, 17.8), (22.1, 21.1), (9.9, 21.1), color=_LIGHT)
        rounded(5.5, 24.1, 21, 2.7, .5, tint)
    elif kind == "car":
        fill((5, 15.6), (9.2, 8.1), (12, 7.4), (20, 7.4), (22.8, 8.1),
             (27, 15.6), color=tint)
        fill((8.8, 14), (11.1, 9.6), (20.9, 9.6), (23.2, 14), color=_BACK)
        rounded(4.8, 14.5, 22.4, 8.5, .35, tint)
        rounded(6, 21.5, 3.9, 4, .45, _LIGHT)
        rounded(22.1, 21.5, 3.9, 4, .45, _LIGHT)
        rounded(6.4, 16.4, 4.1, 2.2, .65, _LIGHT)
        rounded(21.5, 16.4, 4.1, 2.2, .65, _LIGHT)
        rounded(12.5, 19.1, 7, 1.6, .5, _BACK)
    elif kind == "bus":
        rounded(3.8, 8.1, 24.4, 14.8, .3, tint)
        for x in (6, 11.8, 17.6):
            rounded(x, 10.4, 4.3, 5.2, .15, _BACK)
        rounded(23.2, 10.4, 2.8, 9.3, .2, _BACK)
        wheel(8.9, 23.1, 2.7, 1.4)
        wheel(23.1, 23.1, 2.7, 1.4)
    else:  # truck
        rounded(3.8, 7.7, 15.5, 13, .15, tint)
        fill((20.5, 12), (24.2, 12), (28.3, 16.9), (28.3, 21.4),
             (20.5, 21.4), color=tint)
        fill((21.8, 13.6), (23.6, 13.6), (26.2, 16.8), (21.8, 16.8), color=_BACK)
        stroke((4.7, 22), (27, 22), width=1.5, color=_LIGHT)
        wheel(8.6, 23.3, 2.8, 1.4)
        wheel(23.9, 23.3, 2.8, 1.4)
    return tuple(commands)


def draw_object_icon(kind: str, center_x: float, center_y: float, size: float) -> None:
    """Draw a square screen-space icon centered at the given pixel coordinates."""
    if kind not in _TINT or size <= 0:
        return
    drawing = _drawing(kind)
    scale = size / 32.
    rl.rl_push_matrix()
    try:
        rl.rl_translatef(center_x - size * .5, center_y - size * .5, 0.)
        rl.rl_scalef(scale, scale, 1.)
        for draw, arguments in drawing:
            draw(*arguments)
    finally:
        rl.rl_pop_matrix()
