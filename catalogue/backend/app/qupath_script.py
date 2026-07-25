import html
import xml.etree.ElementTree as ET

# Whether rect_x/rect_y/rect_w/rect_h (and the arrow/point coordinates) need
# multiplying by the per-annotation "zoom" field to reach true full-resolution
# pixel coordinates is still being verified against real data. Exposed as a
# toggle (apply_zoom) so both hypotheses can be generated and visually
# compared directly in QuPath.


def _groovy_str(value):
    value = "" if value is None else str(value)
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    value = value.replace("\n", " ").replace("\r", " ")
    return f'"{value}"'


def _num(value):
    return "0" if value is None else repr(float(value))


def _parse_drawing_points(drawing_xml):
    """dih stores freehand/polygon shapes as HTML-escaped XML in the `drawing`
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


def _rect_roi(ann, scale, idx):
    x, y, w, h = ann.get("rect_x"), ann.get("rect_y"), ann.get("rect_w"), ann.get("rect_h")
    if x is None or x == -1 or w is None or w <= 0 or h is None or h <= 0:
        return None
    return (
        f"def roi{idx} = ROIs.createRectangleROI({_num(x * scale)}, {_num(y * scale)}, "
        f"{_num(w * scale)}, {_num(h * scale)}, plane)\n"
        f"def annotation{idx} = PathObjects.createAnnotationObject(roi{idx})"
    )


def _ellipse_roi(ann, scale, idx):
    x, y, w, h = ann.get("rect_x"), ann.get("rect_y"), ann.get("rect_w"), ann.get("rect_h")
    if x is None or x == -1 or w is None or w <= 0 or h is None or h <= 0:
        return None
    return (
        f"def roi{idx} = ROIs.createEllipseROI({_num(x * scale)}, {_num(y * scale)}, "
        f"{_num(w * scale)}, {_num(h * scale)}, plane)\n"
        f"def annotation{idx} = PathObjects.createAnnotationObject(roi{idx})"
    )


def _line_roi(ann, scale, idx):
    x1, y1 = ann.get("arrow_start_x"), ann.get("arrow_start_y")
    x2, y2 = ann.get("arrow_end_x"), ann.get("arrow_end_y")
    if x1 is None or x1 == -1:
        return None
    return (
        f"def roi{idx} = ROIs.createLineROI({_num(x1 * scale)}, {_num(y1 * scale)}, "
        f"{_num(x2 * scale)}, {_num(y2 * scale)}, plane)\n"
        f"def annotation{idx} = PathObjects.createAnnotationObject(roi{idx})"
    )


def _point_roi(ann, scale, idx):
    x, y = ann.get("rect_x"), ann.get("rect_y")
    if x is None or x == -1:
        return None
    return (
        f"def roi{idx} = ROIs.createPointsROI({_num(x * scale)}, {_num(y * scale)}, plane)\n"
        f"def annotation{idx} = PathObjects.createAnnotationObject(roi{idx})"
    )


def _freehand_roi(ann, scale, idx):
    parsed = _parse_drawing_points(ann.get("drawing"))
    if parsed is None:
        fallback = _rect_roi(ann, scale, idx)
        if fallback is None:
            return None
        return "// drawing field could not be decoded - showing bounding box only\n" + fallback

    points, is_closed = parsed
    rect_x, rect_y = ann.get("rect_x"), ann.get("rect_y")
    if rect_x is None or rect_x == -1:
        rect_x, rect_y = 0, 0

    coords = ", ".join(
        f"new Point2({_num((rect_x + px) * scale)}, {_num((rect_y + py) * scale)})"
        for px, py in points
    )
    ctor = "createPolygonROI" if is_closed else "createPolylineROI"
    return (
        f"def points{idx} = [{coords}]\n"
        f"def roi{idx} = ROIs.{ctor}(points{idx}, plane)\n"
        f"def annotation{idx} = PathObjects.createAnnotationObject(roi{idx})"
    )


_ROI_BUILDERS = {
    "rectangle": _rect_roi,
    "scanned_region": _rect_roi,
    "ellipse": _ellipse_roi,
    "arrow": _line_roi,
    "measure": _line_roi,
    "pin": _point_roi,
    "drawing": _freehand_roi,
    "polygon": _freehand_roi,
}


DEFAULT_COLOR_RGB = (255, 255, 0)  # yellow


def parse_color(color_hex):
    """"RRGGBB" (with or without a leading '#') -> (r, g, b) ints, falling back
    to yellow for anything that doesn't parse - a bad colour param shouldn't
    break script generation.
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


def generate_script(slide, annotations, apply_zoom=True, color=None):
    r, g, b = color or DEFAULT_COLOR_RGB

    lines = [
        "// Auto-generated by the Virtual Microscopy Catalogue - recreates this slide's stored",
        f"// annotations ({slide.get('filename')}, slide_id={slide.get('slide_id')}) as",
        "// QuPath annotation objects. Open the matching slide in QuPath, then",
        "// Automate > Script editor > paste and Run.",
        "//",
        "// Coordinate mode: "
        + (
            "rect/point values multiplied by each annotation's own 'zoom' field."
            if apply_zoom
            else "raw rect/point values, no zoom scaling applied."
        ),
        "// Whether zoom-scaling is correct is still being verified against real",
        "// data - if these annotations look offset, wrongly sized, or land on",
        "// blank space, regenerate with the opposite coordinate mode and compare.",
        "",
        "import qupath.lib.objects.PathObjects",
        "import qupath.lib.roi.ROIs",
        "import qupath.lib.regions.ImagePlane",
        "import qupath.lib.geom.Point2",
        "import qupath.lib.common.ColorTools",
        "",
        "def plane = ImagePlane.getDefaultPlane()",
        f"def annotationColor = ColorTools.packRGB({r}, {g}, {b})",
        "def toAdd = []",
        "",
    ]

    marked_invisible = 0
    skipped_no_geometry = 0

    # Every annotation's Groovy variables are suffixed with its own index
    # (roi0/annotation0, roi1/annotation1, ...) - a flat script body shares one
    # top-level scope in Groovy, so reusing the same "def roi"/"def annotation"
    # name for each annotation fails to compile ("variable already defined")
    # from the second one onward.
    for idx, ann in enumerate(annotations):
        is_invisible = (ann.get("invisible") or "").lower() == "true"
        if is_invisible:
            # dih's "invisible" flag is real per-annotation source data (27% of
            # all dih annotations, and confirmed against real data that some
            # slides have it set on every single one of their annotations) -
            # not something to silently drop, since that could zero out a
            # slide's entire annotation set. Included, just clearly labelled.
            marked_invisible += 1

        ann_type = (ann.get("annotation_type") or "").lower()
        builder = _ROI_BUILDERS.get(ann_type)
        zoom = ann.get("zoom")
        scale = zoom if (apply_zoom and zoom and zoom > 0) else 1.0

        roi_code = builder(ann, scale, idx) if builder else None
        if roi_code is None:
            skipped_no_geometry += 1
            lines.append(
                f"// Skipped annotation {ann.get('annotation_id')} "
                f"({ann_type or 'unknown type'}) - no usable geometry"
            )
            continue

        title = ann.get("title") or f"Annotation {ann.get('annotation_id')}"
        if is_invisible:
            title += " (marked invisible in dih)"
        description = ann.get("description")
        var_name = f"annotation{idx}"

        lines.append(roi_code)
        lines.append(f"{var_name}.setName({_groovy_str(title)})")
        lines.append(f"{var_name}.setColor(annotationColor)")
        if description:
            lines.append(f"{var_name}.setDescription({_groovy_str(description)})")
        lines.append(f"toAdd << {var_name}")
        lines.append("")

    lines.append("addObjects(toAdd)")
    lines.append("fireHierarchyUpdate()")
    lines.append(
        'println "Added ${toAdd.size()} annotation(s) ('
        + f"{marked_invisible} marked invisible in dih (still added), "
        + f"{skipped_no_geometry} unsupported skipped"
        + ') from the catalogue."'
    )

    return "\n".join(lines) + "\n"
