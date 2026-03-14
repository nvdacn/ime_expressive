# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2026 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

from enum import IntEnum


class DescriptionMode(IntEnum):
	"""Controls how many characters in a candidate get phonetic descriptions.

	Values map directly to config "candidateCharacterDescription".
	For example, DOUBLE means candidates with <= 2 chars will be described
	character-by-character using getCharacterDescription.
	"""

	NONE = 0
	SINGLE = 1
	DOUBLE = 2
	TRIPLE = 3
	QUADRUPLE = 4
	FULL = 5


class ReportThreshold(IntEnum):
	"""Controls when to speak the raw candidate before the description.

	Values map to config "reportCandidateBeforeDescription".
	E.g. FROM_2 means candidates with > 2 chars are spoken as-is first,
	then the description follows.
	"""

	FROM_1 = 0
	FROM_2 = 1
	FROM_3 = 2
	FROM_4 = 3
	FROM_5 = 4
	FROM_6 = 5
	NEVER = 6


class SelectKeyMode(IntEnum):
	"""Key bindings for selecting the first/last character from a candidate phrase."""

	DISABLED = 0
	BRACKETS = 1
	COMMA_PERIOD = 2
	PAGE_UPDOWN = 3
