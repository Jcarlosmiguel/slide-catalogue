"""Pragmatic DICOM header de-identification - two modes, always shown in full
before whoever runs this tool picks one (see MODE_DESCRIPTIONS below).

This is a deliberately pragmatic subset of the DICOM standard's own PS3.15
Basic De-identification Profile, not a certified implementation of it -
review the actual tag lists below before relying on this for a real
release/compliance decision. It only touches header tags: neither mode
inspects pixel data, so a scanner-burned-in text overlay (patient name
printed directly onto the image) is not detected or removed by either mode -
see BURNED_IN_ANNOTATION_CAVEAT.
"""

from pydicom.uid import generate_uid

FULL = "full"
NON_IDENTIFYING = "non_identifying"
MODES = (FULL, NON_IDENTIFYING)

MODE_DESCRIPTIONS = {
    FULL: (
        "full - complete anonymiser (most conservative): removes every "
        "direct patient/institution identifier (name, ID, birth date, "
        "address, contact details, physician names, institution, accession "
        "number, all dates/times) AND every descriptive field that could "
        "narrow down who the patient is even indirectly (age, size, "
        "weight, free-text study/series descriptions, comments). What's "
        "left is only the technical imaging data needed to display and "
        "study the image (modality, dimensions, imaging parameters) - no "
        "context about the patient or exam at all."
    ),
    NON_IDENTIFYING: (
        "non_identifying - partial, teaching-value-preserving: removes "
        "every direct identifier (name, ID, birth date, address, contact "
        "details, physician names, institution, accession number, all "
        "dates/times) but KEEPS non-identifying descriptive fields that "
        "carry real teaching value - patient sex, age, body part "
        "examined, modality, study/series description, imaging "
        "parameters. Loosely based on the DICOM standard's own PS3.15 "
        "Basic De-identification Profile, but a practical subset of it, "
        "not a certified implementation - spot-check output, especially "
        "free-text description fields, before treating it as safe to "
        "publish."
    ),
}

BURNED_IN_ANNOTATION_CAVEAT = (
    "Neither mode inspects pixel data - a scanner-burned-in text overlay "
    "(patient name printed onto the image itself) is NOT detected or "
    "removed by either mode. Visually check output before publishing, "
    "especially if the source file's own BurnedInAnnotation tag says YES."
)

# Direct identifiers and quasi-identifying dates/times - always removed,
# in both modes.
TRUE_IDENTIFIER_KEYWORDS = [
    "PatientName", "PatientID", "PatientBirthDate", "PatientBirthTime",
    "PatientAddress", "PatientTelephoneNumbers", "PatientMotherBirthName",
    "OtherPatientIDs", "OtherPatientNames", "OtherPatientIDsSequence",
    "IssuerOfPatientID", "PatientReligiousPreference", "EthnicGroup",
    "MilitaryRank", "MedicalRecordLocator", "ResponsiblePerson",
    "ResponsibleOrganization", "CurrentPatientLocation",
    "PatientInstitutionResidence",
    "ReferringPhysicianName", "ReferringPhysicianAddress",
    "ReferringPhysicianTelephoneNumbers",
    "ReferringPhysicianIdentificationSequence",
    "PerformingPhysicianName", "PerformingPhysicianIdentificationSequence",
    "OperatorsName", "OperatorIdentificationSequence",
    "NameOfPhysiciansReadingStudy", "PhysiciansOfRecord",
    "RequestingPhysician", "ScheduledPerformingPhysicianName",
    "InstitutionName", "InstitutionAddress", "InstitutionalDepartmentName",
    "InstitutionCodeSequence",
    "StationName", "DeviceSerialNumber", "DetectorID", "PlateID",
    "CassetteID", "GeneratorID",
    "PerformedStationAETitle", "PerformedStationName",
    "ScheduledStationAETitle", "ScheduledStationName",
    "AccessionNumber", "RequestingService", "RequestedProcedureID",
    "AdmissionID", "IssuerOfAdmissionID",
    "ImageComments", "AdditionalPatientHistory", "PatientComments",
    "DerivationDescription", "RequestAttributesSequence",
    "ContentCreatorName", "VerifyingObserverName", "VerifyingObserverSequence",
    "PersonName", "PersonAddress", "PersonTelephoneNumbers",
    "StudyDate", "SeriesDate", "AcquisitionDate", "ContentDate",
    "InstanceCreationDate", "OverlayDate", "CurveDate",
    "StudyTime", "SeriesTime", "AcquisitionTime", "ContentTime",
    "InstanceCreationTime", "OverlayTime", "CurveTime",
]

# Non-identifying descriptive fields with real teaching value - kept in
# NON_IDENTIFYING mode, also stripped in FULL mode.
DESCRIPTIVE_KEYWORDS = [
    "PatientSex", "PatientAge", "PatientSize", "PatientWeight",
    "PatientPosition", "BodyPartExamined", "Modality", "StudyDescription",
    "SeriesDescription", "ProtocolName", "Manufacturer",
    "ManufacturerModelName", "SoftwareVersions", "MagneticFieldStrength",
    "KVP", "SliceThickness", "PixelSpacing", "ImageType", "ViewPosition",
    "Laterality", "ImageLaterality", "ContrastBolusAgent",
    "ScanningSequence", "SequenceVariant", "RepetitionTime", "EchoTime",
    "ExposureTime", "XRayTubeCurrent", "Exposure",
]

# Internal structural identifiers - not human-identifying by themselves, but
# regenerated in both modes so a de-identified file can't be linked back to
# the source system's records for that patient/study via UID lookup.
UID_KEYWORDS_TO_REMAP = [
    "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID",
    "FrameOfReferenceUID", "SynchronizationFrameOfReferenceUID",
]


class UidRemapper:
    """Keeps original->new UID mappings consistent across every file
    processed in the same run, so files from the same original study/series
    still share the same (new) UIDs after de-identification.
    """

    def __init__(self):
        self._map = {}

    def get(self, original_uid):
        if original_uid not in self._map:
            self._map[original_uid] = generate_uid()
        return self._map[original_uid]


def _remove(ds, keyword):
    if keyword in ds:
        del ds[keyword]


def is_burned_in(ds):
    value = ds.get("BurnedInAnnotation", None)
    return value is not None and str(value).strip().upper() == "YES"


def deidentify_dataset(ds, mode, uid_remapper=None):
    """Mutates `ds` (a pydicom Dataset) in place. Returns a dict of findings
    the caller should surface to whoever is running this (e.g. the
    burned-in-annotation warning) - the mode's own removal isn't something a
    caller needs to inspect the dataset again to learn.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown de-identification mode: {mode!r} (must be one of {MODES})")

    burned_in = is_burned_in(ds)

    for keyword in TRUE_IDENTIFIER_KEYWORDS:
        _remove(ds, keyword)

    if mode == FULL:
        for keyword in DESCRIPTIVE_KEYWORDS:
            _remove(ds, keyword)

    if uid_remapper is not None:
        for keyword in UID_KEYWORDS_TO_REMAP:
            if keyword in ds:
                original = getattr(ds, keyword)
                setattr(ds, keyword, uid_remapper.get(original))

    ds.PatientIdentityRemoved = "YES"
    # DeidentificationMethod is VR=LO - hard 64-char limit, so this has to
    # stay a short pointer, not a real explanation (see module docstring
    # for the actual description of what each mode does).
    ds.DeidentificationMethod = f"slide-crawler pragmatic de-id ({mode})"[:64]

    return {"burned_in_annotation_warning": burned_in}
