# Phase 44 PPTX fixtures

Static binary fixtures consumed by
`backend/tests/test_signage_pptx_pipeline_integration.py`.

- `tiny-valid.pptx` — a 2-slide valid PPTX (~29KB) generated once with
  `python-pptx` as a one-off dev-time script (NOT a CI dependency, and
  not added to `requirements.txt`/`requirements-dev.txt`). Titles are
  `Slide 1` / `Slide 2`. Used by the integration tests to exercise the
  full `soffice` → `pdftoppm` happy path. Regenerate with:

  ```sh
  pip install python-pptx  # one-off, do not commit to requirements
  python -c "
  from pptx import Presentation
  p = Presentation()
  layout = p.slide_layouts[0]
  for i in range(2):
      s = p.slides.add_slide(layout)
      s.shapes.title.text = f'Slide {i+1}'
  p.save('backend/tests/fixtures/signage/tiny-valid.pptx')
  "
  ```

- `corrupt.pptx` — plain-text bytes with a `.pptx` extension. Used to
  exercise the `soffice_failed` / `invalid_pptx` failure branches in
  `app.services.signage_pptx.convert_pptx`. Content is literally
  `not a real pptx just some bytes\n`.
