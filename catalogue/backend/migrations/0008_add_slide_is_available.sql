-- Public-visibility switch, distinct from asset_status. asset_status is
-- about technical/curatorial disposition (is this a real, usable catalogue
-- asset - ACTIVE/CORRUPT_FILE/DUPLICATE_SLIDE/etc.); is_available is about
-- access rights, an orthogonal concern - a slide can be perfectly ACTIVE and
-- still need to be hidden from public view while provenance/rights
-- questions are being resolved for it specifically.
--
-- Why now: today every viewer of this catalogue is already inside the
-- university network or on VPN, so unresolved rights questions on a handful
-- of slides don't matter yet - nobody outside the university can see them
-- regardless. That changes the moment this catalogue (or some view of it)
-- is ever made public: at that point, specific slides may need to stay
-- hidden until their rights/provenance are confirmed, without deleting
-- anything or disrupting the university-only access that already works
-- today.
--
-- Defaults to 1 (available) for every existing and future row, so nothing
-- changes for current access - this is purely a switch to flip to 0 later,
-- per-slide, by query, for the specific slides that turn out to need it.
--
-- Schema-only for now: no backend/API code reads or filters on this column
-- yet - that's a separate, later step once it's clear exactly which
-- endpoints need to respect it for a public-facing view.
--
-- Run against catalogue, e.g.:
--   docker exec -i catalogue_mariadb mariadb -u catalogue_app -p'...' catalogue \
--     < 0008_add_slide_is_available.sql

ALTER TABLE slides
  ADD COLUMN is_available TINYINT(1) NOT NULL DEFAULT 1
  COMMENT 'Public-visibility switch, independent of asset_status. 1 = available/visible (default, current behaviour for all slides); 0 = hidden pending provenance/rights resolution. Only matters once this catalogue (or a view of it) is public - university/VPN access is unaffected either way today.'
  AFTER asset_status;
