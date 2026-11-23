# Copyright (c) 2026, Klisia / SeminaryERP and contributors
# See license.txt
"""WCAG 2 colour contrast (061a, 102 §8).

Pure functions: no database, no Frappe. Website Branding refuses a colour pair below
`MIN_RATIO`, and the portal theme slot checks a theme's pairs with the same arithmetic.
"""

import math
import re

#: WCAG 2.2 AA for body text (success criterion 1.4.3).
MIN_RATIO = 4.5

#: The bar inks Website Branding derives (061a).
LIGHT_INK = "#ffffff"
DARK_INK = "#1a2330"

_RGB = re.compile(
	r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(0|1|0?\.\d+)\s*)?\)$",
	re.IGNORECASE,
)


def channels(colour):
	"""(r, g, b) in 0-255 for #rgb, #rrggbb or an opaque rgb()/rgba(); None otherwise.

	A translucent colour has no contrast of its own (it depends on what is under it),
	so it reads as None rather than as a guess."""
	value = (colour or "").strip()
	match = _RGB.match(value)
	if match:
		alpha = match.group(4)
		if alpha is not None and float(alpha) < 1:
			return None
		rgb = tuple(int(match.group(i)) for i in (1, 2, 3))
		return rgb if all(c <= 255 for c in rgb) else None
	value = value.lstrip("#")
	if len(value) == 3:
		value = "".join(c * 2 for c in value)
	if len(value) != 6:
		return None
	try:
		return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
	except ValueError:
		return None


def luminance(colour):
	"""WCAG relative luminance of a colour, or None when it can't be read."""
	rgb = channels(colour)
	if rgb is None:
		return None
	r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (v / 255 for v in rgb))
	return 0.2126 * r + 0.7152 * g + 0.0722 * b


def luminance_ratio(a, b):
	"""Contrast ratio of two luminances."""
	lighter, darker = max(a, b), min(a, b)
	return (lighter + 0.05) / (darker + 0.05)


def contrast_ratio(foreground, background):
	"""Contrast ratio of two colours (1 to 21), or None when either can't be read."""
	a, b = luminance(foreground), luminance(background)
	if a is None or b is None:
		return None
	return luminance_ratio(a, b)


def passes(foreground, background, minimum=MIN_RATIO):
	"""True when the pair reaches `minimum`, or can't be read (nothing to judge)."""
	ratio = contrast_ratio(foreground, background)
	return ratio is None or ratio >= minimum


def format_ratio(ratio):
	"""'4.48:1', rounded down, so a pair just short of the minimum never reads as 4.5."""
	return f"{math.floor(ratio * 100) / 100:.2f}:1"


def bar_ink(background, text_colour=None):
	"""The ink with the higher contrast on `background`: white, or the
	school's Text colour (near-black when that is blank or too light).
	None when the background can't be read, so the CSS fallback applies."""
	bg = luminance(background)
	if bg is None:
		return None
	text = luminance(text_colour)
	dark = text_colour.strip() if text is not None and text < 0.2 else DARK_INK
	if luminance_ratio(bg, luminance(dark)) > luminance_ratio(bg, 1.0):
		return dark
	return LIGHT_INK
