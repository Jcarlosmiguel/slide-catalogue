ALTER TABLE slides
  ADD COLUMN dicom_deidentification_mode ENUM('full','non_identifying') NULL DEFAULT NULL
    COMMENT 'DICOM slides only (slide_format=DICOM). Which de-identification pass produced the file stored at physical_path: full=every identifying AND descriptive field stripped; non_identifying=identifying fields stripped, non-identifying descriptive fields (sex, age, modality, body part, study/series description, imaging parameters) kept. NULL for every non-DICOM slide, and for a DICOM slide whose source file has not yet been through a de-identification pass (must not be served/thumbnailed until it is - see app/dicom_deidentify.py).'
    AFTER slide_format,
  ADD COLUMN dicom_burned_in_annotation_warning TINYINT(1) NOT NULL DEFAULT 0
    COMMENT 'DICOM slides only. Set when the source file''s own BurnedInAnnotation tag claims patient-identifying text is baked into the pixel data itself - de-identification only touches header tags, never pixel content, so a slide flagged here needs manual visual review before being made available.'
    AFTER dicom_deidentification_mode;

INSERT INTO system_settings (setting_name, setting_value)
VALUES (
  'dicom_deidentification_default_mode',
  'full'
)
ON DUPLICATE KEY UPDATE setting_name = setting_name;
