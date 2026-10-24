---
name: Viewport-fixed overlays
description: Why global overlays must sit outside transformed page-animation containers.
---
Keep viewport-fixed overlays outside animated or transformed page containers, using a body portal when necessary.

**Why:** The page-entry animation retains a transform after finishing. That transform creates a containing block for fixed descendants, which can double-apply sidebar offsets and anchor a footer to the page content instead of the viewport.

**How to apply:** For fixed summaries or other global overlays, keep layout offsets relative to the viewport. Do not compensate for a transformed ancestor by adding more margins or left offsets. Check desktop, tablet, mobile, and scrolling, including clearance from the floating Help launcher.
