// Shifts every annotation on the image (except the one currently selected)
// so its coordinates line up with a crop mask's own (0, 0) origin - run
// this after importing a slide's annotations (see
// import-annotations-from-ome-xml.groovy) and before exporting them (see
// export-annotations-as-ome-xml.groovy), with the crop mask selected.
//
// Stored annotations are recorded on the original, full-size image. A
// cropped export has its own coordinate system starting at (0, 0) in the
// crop's top-left, so annotations need translating by the crop's own
// bounds offset to land in the right place once re-imported against the
// cropped image in OMERO.
//
// Mutates each annotation's ROI in place (setROI) rather than deleting and
// recreating it, so name/colour/description/metadata are all preserved
// exactly as imported.
//
// See "Applying a slide's annotations in QuPath" (the "If you're also
// cropping this slide" section) for the full workflow.

def cropAnnotation = getSelectedObject()
if (cropAnnotation == null) {
    print "Select the crop mask first, then run this script again."
    return
}

def cropRoi = cropAnnotation.getROI()
double offsetX = cropRoi.getBoundsX()
double offsetY = cropRoi.getBoundsY()

def moved = 0
getAnnotationObjects().each { annotation ->
    if (annotation == cropAnnotation)
        return

    def roi = annotation.getROI()
    annotation.setROI(roi.translate(-offsetX, -offsetY))
    moved++
}

fireHierarchyUpdate()
print "Repositioned ${moved} annotation(s) by (${-offsetX}, ${-offsetY}) to line up with the crop mask's origin."
