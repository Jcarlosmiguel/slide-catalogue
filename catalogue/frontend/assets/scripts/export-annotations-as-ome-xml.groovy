// Exports every annotation on the image (except the one currently
// selected - the crop mask) as a standalone OME-XML file (ROIs only, no
// image/pixel data - a valid, minimal OME-XML document, readable by any
// OME-XML-aware tool). Run after repositioning annotations relative to
// the crop mask (see reposition-annotations-for-crop.groovy), with the
// crop mask selected.
//
// This never uses QuPath's own Geometry conversion for line endpoints or
// its built-in GeoJSON export - both were found to sometimes silently
// reorder a line's two endpoints, which breaks which end an arrow's head
// is on. Every shape here is read from its own direct accessors instead
// (getX1/getY1/getX2/getY2 for lines, getBoundsX/Y/Width/Height for
// rectangles/ellipses, getAllPoints() for polygons/polylines/points), and
// an arrow's direction becomes OME-XML's own native MarkerStart/MarkerEnd
// attributes on the Line shape - a real part of the format, not something
// bolted on afterwards.
//
// Import the resulting file with import-annotations-from-ome-xml.groovy,
// or straight into OMERO via omero-roi-importer.
// See "Applying a slide's annotations in QuPath" (the "If you're also
// cropping this slide" section) for the full workflow.

import qupath.fx.dialogs.FileChoosers

def cropAnnotation = getSelectedObject()
if (cropAnnotation == null) {
    print "Select the crop mask first, then run this script again."
    return
}

def escapeXml(value) {
    if (value == null)
        return ""
    return value.toString()
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
}

def toOmeColor(color) {
    if (color == null)
        return null
    int r = (color >> 16) & 0xFF
    int g = (color >> 8) & 0xFF
    int b = color & 0xFF
    long rgba = ((long) r << 24) | ((long) g << 16) | ((long) b << 8) | 0xFF
    return (int) rgba
}

def shapeAttrs = { id, name, color, extra ->
    def sb = new StringBuilder()
    sb << "ID=\"${escapeXml(id)}\" "
    if (name)
        sb << "Text=\"${escapeXml(name)}\" "
    def omeColor = toOmeColor(color)
    if (omeColor != null)
        sb << "StrokeColor=\"${omeColor}\" "
    sb << extra
    return sb.toString().trim()
}

def rois = []
def skipped = []
def shapeIdx = 0
def roiIdx = 0

getAnnotationObjects().each { annotation ->
    if (annotation == cropAnnotation)
        return

    def roi = annotation.getROI()
    def roiName = roi.getRoiName()
    def name = annotation.getName()
    def color = annotation.getColor()
    def arrowStyle = annotation.getMetadata().get("arrowhead")

    def shapeXml
    if (roiName == "Line") {
        double x1 = roi.getX1()
        double y1 = roi.getY1()
        double x2 = roi.getX2()
        double y2 = roi.getY2()
        def markers = ""
        if (arrowStyle == "<" || arrowStyle == "<>")
            markers += 'MarkerStart="Arrow" '
        if (arrowStyle == ">" || arrowStyle == "<>")
            markers += 'MarkerEnd="Arrow" '
        shapeXml = "<Line ${shapeAttrs('Shape:' + shapeIdx, name, color, 'X1="' + x1 + '" Y1="' + y1 + '" X2="' + x2 + '" Y2="' + y2 + '" ' + markers)}/>"
    } else if (roiName == "Rectangle") {
        double x = roi.getBoundsX()
        double y = roi.getBoundsY()
        shapeXml = "<Rectangle ${shapeAttrs('Shape:' + shapeIdx, name, color, 'X="' + x + '" Y="' + y + '" Width="' + roi.getBoundsWidth() + '" Height="' + roi.getBoundsHeight() + '"')}/>"
    } else if (roiName == "Ellipse") {
        double x = roi.getBoundsX()
        double y = roi.getBoundsY()
        double cx = x + roi.getBoundsWidth() / 2
        double cy = y + roi.getBoundsHeight() / 2
        shapeXml = "<Ellipse ${shapeAttrs('Shape:' + shapeIdx, name, color, 'X="' + cx + '" Y="' + cy + '" RadiusX="' + (roi.getBoundsWidth() / 2) + '" RadiusY="' + (roi.getBoundsHeight() / 2) + '"')}/>"
    } else if (roiName == "Points") {
        def points = roi.getAllPoints()
        def shapes = points.withIndex().collect { p, i ->
            "<Point ${shapeAttrs('Shape:' + shapeIdx + '.' + i, name, color, 'X="' + p.getX() + '" Y="' + p.getY() + '"')}/>"
        }
        shapeXml = shapes.join("\n      ")
    } else if (roiName == "Polygon" || roiName == "Polyline") {
        def points = roi.getAllPoints().collect { p -> "${p.getX()},${p.getY()}" }.join(" ")
        def tag = (roiName == "Polygon") ? "Polygon" : "Polyline"
        shapeXml = "<${tag} ${shapeAttrs('Shape:' + shapeIdx, name, color, 'Points="' + points + '"')}/>"
    } else {
        skipped << "${annotation.getName()} (${roiName})"
        return
    }

    def description = annotation.getDescription()
    def descXml = description ? "<Description>${escapeXml(description)}</Description>" : ""

    rois << """  <ROI ID="ROI:${roiIdx}" Name="${escapeXml(name)}">
    ${descXml}
    <Union>
      ${shapeXml}
    </Union>
  </ROI>"""

    shapeIdx++
    roiIdx++
}

if (skipped) {
    print "Skipped ${skipped.size()} annotation(s) with an unrecognised shape type: ${skipped.join(', ')}"
}

def xml = """<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
${rois.join("\n")}
</OME>
"""

def filter = FileChoosers.createExtensionFilter("OME-XML", "ome.xml")
def file = FileChoosers.promptToSaveFile("Save annotations as OME-XML", null, filter)
if (file == null) {
    print "Cancelled - no file saved."
    return
}
file.text = xml
print "Saved ${roiIdx} annotation(s) as OME-XML to ${file}"
