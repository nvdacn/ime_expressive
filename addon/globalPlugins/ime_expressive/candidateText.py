# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2026 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""Candidate text normalization helpers."""

_LIST_CANDIDATE_CLEANUP_TABLE = str.maketrans("", "", " ()")
_SINGLE_CANDIDATE_CLEANUP_TABLE = str.maketrans("", "", "()")


def cleanListCandidate(candidate: str) -> str:
	return candidate.translate(_LIST_CANDIDATE_CLEANUP_TABLE)


def cleanSingleCandidate(candidate: str) -> str:
	return candidate.translate(_SINGLE_CANDIDATE_CLEANUP_TABLE)
