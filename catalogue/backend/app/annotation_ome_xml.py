import html
import re
from defusedxml import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

try:
    import tifffile
except Exception:
    tifffile = None

_FILENAME_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_SCN_IMAGE_BLOCK_RE = re.compile(r"<image .*?</image>", re.S)
_SCN_PIXELS_RE = re.compile(r'<pixels[^>]*sizeX="(\d+)"[^>]*sizeY="(\d+)"')
_SCN_VIEW_RE = re.compile(r'<view sizeX="(\d+)" sizeY="(\d+)" offsetX="(\d+)" offsetY="(\d+)"')
_SCN_MACRO_SIZE_THRESHOLD = 3000  # px - Leica SCN's low-res label/macro image is always far smaller than any real tissue scan region, confirmed against real multi-region .scn files.


def _load_scn_regions(physical_path):
    """Leica .scn files can hold more than one independently-positioned
    tissue scan region in a single file (confirmed against a real
    multi-region slide - two separate scans, "near the label" and "below", each
    its own separate scan, not a resolution pyramid of one scan). Each
    region's true canvas position/size is only available from the file's
    own embedded <scn> XML (in the first IFD's ImageDescription tag) -
    OpenSlide's own openslide.bounds-x/y/width/height flattens this into
    a single union bounding box across every region, which is NOT the
    same as any one region's own local coordinate frame (confirmed this
    session: for a 2-region file, the union box doesn't match either
    region's own offset+size).

    Returns a list of {offset_x_px, offset_y_px, size_x_px, size_y_px}
    dicts, one per real tissue region (skips the macro/label image), in
    file order - or None if this isn't a parseable .scn file (wrong
    extension, tifffile unavailable, missing/malformed metadata, etc.)
    so callers can fall back to the no-offset behaviour.
    """
    if tifffile is None or not physical_path or not physical_path.lower().endswith(".scn"):
        return None
    try:
        with tifffile.TiffFile(physical_path) as tf:
            desc = tf.pages[0].tags["ImageDescription"].value
        regions = []
        for block in _SCN_IMAGE_BLOCK_RE.findall(desc):
            pixels_m = _SCN_PIXELS_RE.search(block)
            view_m = _SCN_VIEW_RE.search(block)
            if not pixels_m or not view_m:
                continue
            size_x_px, size_y_px = int(pixels_m.group(1)), int(pixels_m.group(2))
            if size_x_px < _SCN_MACRO_SIZE_THRESHOLD:
                continue
            view_size_x_nm = int(view_m.group(1))
            offset_x_nm, offset_y_nm = int(view_m.group(3)), int(view_m.group(4))
            nm_per_px = view_size_x_nm / size_x_px
            regions.append({
                "offset_x_px": offset_x_nm / nm_per_px,
                "offset_y_px": offset_y_nm / nm_per_px,
                "size_x_px": size_x_px,
                "size_y_px": size_y_px,
            })
        return regions or None
    except Exception:
        return None


def _assign_region(x, y, regions):
    """Which region (offset_x_px, offset_y_px, size_x_px, size_y_px) a
    canvas-absolute point belongs to. Falls back to the nearest region's
    centre when the point doesn't fall inside any region's box outright
    (small floating-point slop at a region's own edge, or an annotation
    drawn just outside the scanned area) - better than silently dropping
    a real annotation.
    """
    for region in regions:
        if region["offset_x_px"] <= x <= region["offset_x_px"] + region["size_x_px"] and \
           region["offset_y_px"] <= y <= region["offset_y_px"] + region["size_y_px"]:
            return region

    def _dist(region):
        cx = region["offset_x_px"] + region["size_x_px"] / 2
        cy = region["offset_y_px"] + region["size_y_px"] / 2
        return (x - cx) ** 2 + (y - cy) ** 2

    return min(regions, key=_dist)


def _shift_geometry(geometry, dx, dy):
    g = dict(geometry)
    if "x" in g:
        g["x"] += dx
        g["y"] += dy
    if "x1" in g:
        g["x1"] += dx
        g["y1"] += dy
        g["x2"] += dx
        g["y2"] += dy
    if "points" in g:
        g["points"] = [(px + dx, py + dy) for px, py in g["points"]]
    return g


def slugify_filename_hint(value, max_length=80):
    """Turns a slide's original filename into a short, cross-platform-safe
    hint for use inside a download filename - not meant to reproduce the
    original name exactly, just to make the file identifiable without having
    to look slide_id up in the catalogue. Strips characters invalid on
    Windows (safe to always strip, even on macOS/Linux where they're legal),
    collapses whitespace/runs of underscores, and caps the length so the
    final filename stays well under any OS path-length limit.
    """
    value = (value or "").strip()
    value = _FILENAME_UNSAFE_RE.sub("", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("._")
    return value[:max_length]

# Confirmed against real data (multiple real multi-region .scn slides):
# rect_x/rect_y/rect_w/rect_h (and the arrow/point coordinates) DO need
# multiplying by the per-annotation "zoom" field to reach real canvas-absolute
# pixel coordinates - verified by generating QuPath-loadable OME-XML at
# multiple candidate transforms and visually checking each against the real
# slide. apply_zoom is kept as a param (rather than hardcoding True) only as
# an escape hatch for a slide where this turns out not to hold.
#
# For multi-region .scn files specifically (a single Leica SCN file can hold
# more than one independently-positioned tissue scan - confirmed against
# Pathology_23.scn, which has two, not a resolution pyramid of one scan),
# canvas-absolute coordinates alone aren't enough: each region has its own
# local coordinate frame when opened as its own image (in QuPath or any
# other per-series viewer), so the canvas-absolute point also needs the
# correct region's own offset (from _load_scn_regions, read from the file's
# own embedded metadata - NOT OpenSlide's openslide.bounds-*, which for a
# multi-region file is the union bounding box of every region combined, not
# any one region's own frame) subtracted back out.


def _parse_drawing_points(drawing_xml):
    """The original recording stores freehand/polygon shapes as HTML-escaped XML in the `drawing`
    column, e.g. <drawing><fhd><styling key="polygon">...</styling>
    <points>0,587|522,592|508,2|10,0</points></fhd></drawing> - the point list
    is relative to the annotation's own bounding box (rect_x/rect_y), not
    absolute. Returns (points, is_closed) or None if it can't be parsed.
    """
    if not drawing_xml:
        return None
    try:
        root = ET.fromstring(html.unescape(drawing_xml))
        points_el = root.find(".//points")
        if points_el is None or not points_el.text:
            return None
        points = []
        for pair in points_el.text.split("|"):
            x_str, y_str = pair.split(",")
            points.append((float(x_str), float(y_str)))
        styling = root.find(".//styling")
        is_closed = styling is not None and styling.get("key") == "polygon"
        return points, is_closed
    except Exception:
        return None


def _rect_geometry(ann, scale):
    x, y, w, h = ann.get("rect_x"), ann.get("rect_y"), ann.get("rect_w"), ann.get("rect_h")
    if x is None or x == -1 or w is None or w <= 0 or h is None or h <= 0:
        return None
    return {"roi_type": "Rectangle", "x": x * scale, "y": y * scale, "w": w * scale, "h": h * scale}


def _ellipse_geometry(ann, scale):
    x, y, w, h = ann.get("rect_x"), ann.get("rect_y"), ann.get("rect_w"), ann.get("rect_h")
    if x is None or x == -1 or w is None or w <= 0 or h is None or h <= 0:
        return None
    return {"roi_type": "Ellipse", "x": x * scale, "y": y * scale, "w": w * scale, "h": h * scale}


def _line_geometry(ann, scale):
    x1, y1 = ann.get("arrow_start_x"), ann.get("arrow_start_y")
    x2, y2 = ann.get("arrow_end_x"), ann.get("arrow_end_y")
    if x1 is None or x1 == -1:
        return None
    return {
        "roi_type": "Line",
        "x1": x1 * scale, "y1": y1 * scale,
        "x2": x2 * scale, "y2": y2 * scale,
    }


def _point_geometry(ann, scale):
    x, y = ann.get("rect_x"), ann.get("rect_y")
    if x is None or x == -1:
        return None
    return {"roi_type": "Point", "x": x * scale, "y": y * scale}


def _freehand_geometry(ann, scale):
    parsed = _parse_drawing_points(ann.get("drawing"))
    if parsed is None:
        return _rect_geometry(ann, scale)

    points, is_closed = parsed
    rect_x, rect_y = ann.get("rect_x"), ann.get("rect_y")
    if rect_x is None or rect_x == -1:
        rect_x, rect_y = 0, 0

    return {
        "roi_type": "Polygon" if is_closed else "Polyline",
        "points": [((rect_x + px) * scale, (rect_y + py) * scale) for px, py in points],
    }


_GEOMETRY_BUILDERS = {
    "rectangle": _rect_geometry,
    "scanned_region": _rect_geometry,
    "ellipse": _ellipse_geometry,
    "arrow": _line_geometry,
    "measure": _line_geometry,
    "pin": _point_geometry,
    "drawing": _freehand_geometry,
    "polygon": _freehand_geometry,
}


DEFAULT_COLOR_RGB = (0, 255, 0)  # bright green

# QuPath's own arrow line tool (right-click the Line tool -> Arrow (start) /
# Arrow (end) / Arrow (double)) stores which end(s) get an arrowhead as a
# PathObject metadata entry - key "arrowhead", value one of these three
# strings - rather than as any distinct ROI type. Confirmed by inspecting
# annotation.getMetadata() on annotations drawn with each of the three real
# QuPath toolbar variants. OME-XML has a native equivalent though:
# MarkerStart/MarkerEnd="Arrow" on a Line shape - so the generated file
# renders the arrowhead directly, no per-object metadata needed.
VALID_ARROW_STYLES = {"<", ">", "<>"}
DEFAULT_ARROW_STYLE = "<"

# "<"/">" are invalid in Windows filenames, so the filename uses these
# words instead when hinting at the chosen arrow style.
_ARROW_STYLE_FILENAME_LABELS = {
    ">": "arrow-end",
    "<": "arrow-start",
    "<>": "arrow-double",
}


def parse_arrow_style(arrow_style):
    """The original recording never recorded which end of an 'arrow' annotation had the actual
    arrowhead - only start/end coordinates - so this is a user-chosen default
    applied to every arrow on a given download, not a value recovered from
    source data. Falls back to DEFAULT_ARROW_STYLE for anything unrecognised.
    """
    return arrow_style if arrow_style in VALID_ARROW_STYLES else DEFAULT_ARROW_STYLE


def arrow_style_filename_label(arrow_style):
    return _ARROW_STYLE_FILENAME_LABELS[parse_arrow_style(arrow_style)]


def parse_color(color_hex):
    """"RRGGBB" (with or without a leading '#') -> (r, g, b) ints, falling back
    to green for anything that doesn't parse - a bad colour param shouldn't
    break generation.
    """
    if not color_hex:
        return DEFAULT_COLOR_RGB
    value = color_hex.lstrip("#")
    if len(value) != 6:
        return DEFAULT_COLOR_RGB
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return DEFAULT_COLOR_RGB


def _to_ome_color(color):
    """Packs (r, g, b) into OME-XML's signed 32-bit RGBA StrokeColor int
    (alpha forced to 0xFF), matching the format QuPath's own OME-XML
    exporter produces - confirmed against a real exported file."""
    r, g, b = color
    rgba = (r << 24) | (g << 16) | (b << 8) | 0xFF
    if rgba >= 2 ** 31:
        rgba -= 2 ** 32
    return rgba


def _shape_attrs(shape_id, name, color, extra):
    parts = [f'ID="{xml_escape(shape_id)}"']
    if name:
        parts.append(f'Text="{xml_escape(name)}"')
    parts.append(f'StrokeColor="{_to_ome_color(color)}"')
    parts.append(extra)
    return " ".join(p for p in parts if p)


def _shape_xml(idx, geometry, name, color, arrow_style):
    shape_id = f"Shape:{idx}"
    roi_type = geometry["roi_type"]

    if roi_type == "Line":
        markers = ""
        if arrow_style in ("<", "<>"):
            markers += 'MarkerStart="Arrow" '
        if arrow_style in (">", "<>"):
            markers += 'MarkerEnd="Arrow" '
        extra = (
            f'X1="{geometry["x1"]}" Y1="{geometry["y1"]}" '
            f'X2="{geometry["x2"]}" Y2="{geometry["y2"]}" {markers}'
        ).strip()
        return f'<Line {_shape_attrs(shape_id, name, color, extra)}/>'

    if roi_type == "Rectangle":
        extra = f'X="{geometry["x"]}" Y="{geometry["y"]}" Width="{geometry["w"]}" Height="{geometry["h"]}"'
        return f'<Rectangle {_shape_attrs(shape_id, name, color, extra)}/>'

    if roi_type == "Ellipse":
        cx, cy = geometry["x"] + geometry["w"] / 2, geometry["y"] + geometry["h"] / 2
        extra = f'X="{cx}" Y="{cy}" RadiusX="{geometry["w"] / 2}" RadiusY="{geometry["h"] / 2}"'
        return f'<Ellipse {_shape_attrs(shape_id, name, color, extra)}/>'

    if roi_type == "Point":
        extra = f'X="{geometry["x"]}" Y="{geometry["y"]}"'
        return f'<Point {_shape_attrs(shape_id, name, color, extra)}/>'

    # Polygon / Polyline
    points_str = " ".join(f"{px},{py}" for px, py in geometry["points"])
    extra = f'Points="{points_str}"'
    return f'<{roi_type} {_shape_attrs(shape_id, name, color, extra)}/>'


def _annotation_anchor(ann):
    """A representative (x, y) for deciding which multi-region .scn region
    an annotation belongs to - rect_x/rect_y for most types, falling back
    to the arrow's start point for 'arrow' rows (which don't populate
    rect_x/rect_y). None if neither is usable."""
    x, y = ann.get("rect_x"), ann.get("rect_y")
    if x is not None and x != -1:
        return x, y
    x, y = ann.get("arrow_start_x"), ann.get("arrow_start_y")
    if x is not None and x != -1:
        return x, y
    return None


def build_ome_xml(slide, annotations, physical_path=None, apply_zoom=True, color=None, arrow_style=None):
    """Builds an OME-XML document (just the <ROI> elements OMERO's
    roi-import tooling needs) recreating this slide's stored annotations
    directly - no QuPath round-trip required. Skips rows with no usable
    geometry the same way the old QuPath-script generator did.

    physical_path is used only to look up multi-region .scn offsets (see
    _load_scn_regions) - harmless to omit (falls back to no offset), but
    needed for annotations to land in the right place on a multi-region
    file such as Pathology_23.scn.
    """
    color = color or DEFAULT_COLOR_RGB
    arrow_style = parse_arrow_style(arrow_style)
    regions = _load_scn_regions(physical_path)

    rois_xml = []
    marked_invisible = 0
    skipped_no_geometry = 0

    for idx, ann in enumerate(annotations):
        is_invisible = (ann.get("invisible") or "").lower() == "true"
        if is_invisible:
            # The "invisible" flag is real per-annotation source data (27%
            # of all annotations in a real dataset checked, and confirmed that
            # some slides have it set on every single one of their
            # annotations) - not something to silently drop, since that
            # could zero out a slide's entire annotation set. Included,
            # just clearly labelled.
            marked_invisible += 1

        ann_type = (ann.get("annotation_type") or "").lower()
        builder = _GEOMETRY_BUILDERS.get(ann_type)
        zoom = ann.get("zoom")
        scale = zoom if (apply_zoom and zoom and zoom > 0) else 1.0

        geometry = builder(ann, scale) if builder else None
        if geometry is None:
            skipped_no_geometry += 1
            continue

        if regions:
            anchor = _annotation_anchor(ann)
            if anchor is not None:
                region = _assign_region(anchor[0] * scale, anchor[1] * scale, regions)
                geometry = _shift_geometry(geometry, -region["offset_x_px"], -region["offset_y_px"])

        name = ann.get("title") or f"Annotation {ann.get('annotation_id')}"
        description = ann.get("description")

        if ann_type == "arrow":
            # QuPath/OME-XML have no distinct "arrow" shape type - a Line
            # with an end marker is the closest match - so without this, an
            # arrow and a measurement are indistinguishable both by shape
            # and by default name.
            name = f"Arrow: {name}"
            x1, y1 = ann.get("arrow_start_x"), ann.get("arrow_start_y")
            x2, y2 = ann.get("arrow_end_x"), ann.get("arrow_end_y")
            direction_note = f"Arrow: start ({x1}, {y1}) -> end ({x2}, {y2})"
            description = f"{direction_note}\n{description}" if description else direction_note

        shape_arrow_style = arrow_style if ann_type == "arrow" else None
        shape_xml = _shape_xml(idx, geometry, name, color, shape_arrow_style)

        desc_xml = f"<Description>{xml_escape(description)}</Description>" if description else ""
        rois_xml.append(f'''  <ROI ID="ROI:{idx}" Name="{xml_escape(name)}">
    {desc_xml}
    <Union>
      {shape_xml}
    </Union>
  </ROI>''')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
{chr(10).join(rois_xml)}
</OME>
''', marked_invisible, skipped_no_geometry
