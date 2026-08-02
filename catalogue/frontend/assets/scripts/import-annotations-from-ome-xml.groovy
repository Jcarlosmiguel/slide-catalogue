// Import annotations from an OME-XML file created by
// export-annotations-as-ome-xml.groovy, onto the currently open image.
//
// Run this on the image opened through its OMERO connection (not a local
// file), after importing the cropped OME-TIFF into OMERO - see "Applying a
// slide's annotations in QuPath" (the "If you're also cropping this slide"
// section) for the full workflow. This never uses QuPath's drag-and-drop
// GeoJSON import, which was found to sometimes silently reorder a line's
// two endpoints - every shape here is rebuilt directly from the file's own
// explicit coordinates instead.

import qupath.lib.objects.PathObjects
import qupath.lib.roi.ROIs
import qupath.lib.regions.ImagePlane
import qupath.fx.dialogs.FileChoosers
import groovy.xml.XmlSlurper

def filter = FileChoosers.createExtensionFilter("OME-XML", "ome.xml")
def file = FileChoosers.promptForFile("Select the OME-XML annotations file", filter)
if (file == null) {
    print "Cancelled - no file selected."
    return
}

def xml = new XmlSlurper(false, false).parse(file)
def plane = ImagePlane.getDefaultPlane()

def fromOmeColor(text) {
    if (text == null || text.toString().isEmpty())
        return null
    long rgba = text.toString() as long
    int r = (int) ((rgba >> 24) & 0xFF)
    int g = (int) ((rgba >> 16) & 0xFF)
    int b = (int) ((rgba >> 8) & 0xFF)
    return (r << 16) | (g << 8) | b
}

def parsePoints = { pointsText ->
    pointsText.toString().trim().split(/\s+/).collect { pair ->
        def (x, y) = pair.split(",")
        new qupath.lib.geom.Point2(x as double, y as double)
    }
}

def toAdd = []
def skipped = []

xml.ROI.each { roiNode ->
    def name = roiNode.@Name.text()
    def description = roiNode.Description.text()
    def union = roiNode.Union

    def roi = null
    def arrowStyle = null
    def strokeColorText = null

    if (!union.Line.isEmpty()) {
        def shape = union.Line[0]
        double x1 = shape.@X1.text() as double
        double y1 = shape.@Y1.text() as double
        double x2 = shape.@X2.text() as double
        double y2 = shape.@Y2.text() as double
        roi = ROIs.createLineROI(x1, y1, x2, y2, plane)
        def hasStart = shape.@MarkerStart.text() == "Arrow"
        def hasEnd = shape.@MarkerEnd.text() == "Arrow"
        if (hasStart && hasEnd)
            arrowStyle = "<>"
        else if (hasStart)
            arrowStyle = "<"
        else if (hasEnd)
            arrowStyle = ">"
        strokeColorText = shape.@StrokeColor.text()
    } else if (!union.Rectangle.isEmpty()) {
        def shape = union.Rectangle[0]
        roi = ROIs.createRectangleROI(shape.@X.text() as double, shape.@Y.text() as double,
            shape.@Width.text() as double, shape.@Height.text() as double, plane)
        strokeColorText = shape.@StrokeColor.text()
    } else if (!union.Ellipse.isEmpty()) {
        def shape = union.Ellipse[0]
        double cx = shape.@X.text() as double
        double cy = shape.@Y.text() as double
        double rx = shape.@RadiusX.text() as double
        double ry = shape.@RadiusY.text() as double
        roi = ROIs.createEllipseROI(cx - rx, cy - ry, rx * 2, ry * 2, plane)
        strokeColorText = shape.@StrokeColor.text()
    } else if (!union.Polygon.isEmpty()) {
        def shape = union.Polygon[0]
        roi = ROIs.createPolygonROI(parsePoints(shape.@Points.text()), plane)
        strokeColorText = shape.@StrokeColor.text()
    } else if (!union.Polyline.isEmpty()) {
        def shape = union.Polyline[0]
        roi = ROIs.createPolylineROI(parsePoints(shape.@Points.text()), plane)
        strokeColorText = shape.@StrokeColor.text()
    } else if (!union.Point.isEmpty()) {
        def xs = union.Point.collect { it.@X.text() as double } as double[]
        def ys = union.Point.collect { it.@Y.text() as double } as double[]
        roi = ROIs.createPointsROI(xs, ys, plane)
        strokeColorText = union.Point[0].@StrokeColor.text()
    } else {
        skipped << name
        return
    }

    def annotation = PathObjects.createAnnotationObject(roi)
    annotation.setName(name)
    if (description)
        annotation.setDescription(description)
    def color = fromOmeColor(strokeColorText)
    if (color != null)
        annotation.setColor(color)
    if (arrowStyle != null)
        annotation.getMetadata().put("arrowhead", arrowStyle)

    toAdd << annotation
}

addObjects(toAdd)
fireHierarchyUpdate()

def summary = "Imported ${toAdd.size()} annotation(s) from ${file.getName()}"
if (skipped)
    summary += " (skipped ${skipped.size()} with an unrecognised shape type: ${skipped.join(', ')})"
print summary
