# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2026 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""IME session state management.

Tracks candidate lists, selection state, and duplicate suppression.
Separated from UI/speech concerns so the controller can decide how to speak.
"""

from __future__ import annotations

import time
import unicodedata
from dataclasses import dataclass

from logHandler import log


@dataclass
class CandidateUpdate:
	"""Result of parsing a candidate list update."""

	candidate: str
	candidateList: list[str]
	isMultiCandidate: bool


@dataclass
class CompositionEndAction:
	"""Describes what the controller should do when composition ends.

	Exactly one of the following is set:
	- textToSpeak: speak this text
	- fallbackToPunc: call _speakPunc instead
	- (both None/False): do nothing
	"""

	textToSpeak: str | None = None
	fallbackToPunc: bool = False
	resolvedFromIndex: bool = False


class ImeStateManager:
	"""Manages IME session state: candidates, selection, duplicate suppression.

	This class does NOT call speech.speak or interact with UI.
	The controller reads state from here and decides what to speak.
	"""

	def __init__(self):
		self.isMicrosoftPinyin: bool = False
		self.isImeSessionFinished: bool = True
		self.selectedCandidate: str = ""
		self.selectedCandidateIndex: int = 0
		self.candidateList: list[str] = []
		self.lastCandidatesString: str = ""
		self.lastCompositionString: str = ""
		self.lastLayoutString: str = ""
		self.modernImeCandidateMap: dict[int, str] = {}
		self.lastModernImeEventTime: float = 0

	def shouldSkipUpdate(self, candidatesString: str, selectionIndex: int, compositionString: str, inputMethod: str) -> bool:
		"""Check if this update should be skipped (session finished or exact duplicate)."""
		if inputMethod == "ms" and self.isImeSessionFinished:
			log.debug("IME_EXP: Skipping update — session finished for modern IME")
			return True
		if not candidatesString:
			return True

		# Exact duplicate suppression: skip ONLY if text, selection index AND composition string
		# are all the same as last reported ones.
		if (
			candidatesString == self.lastCandidatesString
			and selectionIndex == self.selectedCandidateIndex
			and compositionString == self.lastCompositionString
		):
			log.debug("IME_EXP: Skipping exact duplicate candidate update")
			return True
		return False

	def processCandidateUpdate(
		self,
		candidatesString: str,
		selectionIndex: int,
		compositionString: str,
		inputMethod: str,
	) -> CandidateUpdate | None:
		"""Parse a candidate list update and update internal state.

		:return: CandidateUpdate if the update should be spoken, None if skipped.
		"""
		if self.shouldSkipUpdate(candidatesString, selectionIndex, compositionString, inputMethod):
			return None
		self.lastCandidatesString = candidatesString
		self.selectedCandidateIndex = selectionIndex
		self.lastCompositionString = compositionString
		self.isImeSessionFinished = False
		isMultiCandidate = "\n" in candidatesString
		if isMultiCandidate:
			self.candidateList = candidatesString.split("\n")
			candidate = self.candidateList[selectionIndex].replace(" ", "")
		else:
			if not self.isMicrosoftPinyin:
				self.candidateList.append(candidatesString)
			candidate = candidatesString
		candidate = candidate.replace("(", "").replace(")", "")
		self.selectedCandidate = candidate
		log.debug(
			f"IME_EXP: Candidate update processed: '{candidate}', "
			f"index={selectionIndex}, multi={isMultiCandidate}"
		)
		return CandidateUpdate(
			candidate=candidate,
			candidateList=self.candidateList,
			isMultiCandidate=isMultiCandidate,
		)

	def resolveCompositionEnd(self, result: str) -> CompositionEndAction:
		"""Determine what the controller should do when composition ends.

		Resolution priority: result → selectedCandidate → index → punc fallback.

		Why selectedCandidate before index:
		  For Sogou IME, compositionEnd may arrive with empty result (from TSF's
		  OnEndEdit). In some input fields a second compositionEnd with the correct
		  result follows (from IMM32's WM_IME_ENDCOMPOSITION + GCS_RESULTSTR), but
		  in others it does not — making empty-result the only event we receive.
		  In that scenario, selectedCandidateIndex carries 0-based semantics (set by
		  processCandidateUpdate from the IME's selectionIndex), while the index
		  fallback path uses candidateList[index - 1] assuming 1-based (designed for
		  digit-key selection via script_pressKey). This mismatch caused the wrong
		  candidate to be spoken.  selectedCandidate is always set correctly by both
		  arrow-key navigation (processCandidateUpdate) and digit-key selection
		  (script_pressKey), so it is the safest primary source of truth.
		"""
		if result:
			# When we have a tracked candidate, validate result against it to reject
			# stale compositionEnd events (e.g. Sogou fires two: first stale, then correct).
			if self.selectedCandidate:
				if result in self.selectedCandidate or self.selectedCandidate in result:
					log.debug(f"IME_EXP: Composition end — result matches selected candidate: '{result}'")
					return CompositionEndAction(textToSpeak=result)
				log.debug(
					f"IME_EXP: Composition end — result '{result}' doesn't match "
					f"selected candidate '{self.selectedCandidate}', skipping"
				)
				return CompositionEndAction()
			if not self.lastCandidatesString or result in self.lastCandidatesString:
				log.debug(f"IME_EXP: Composition end — result matches candidates: '{result}'")
				return CompositionEndAction(textToSpeak=result)
			log.debug(f"IME_EXP: Composition end — result '{result}' not in candidates, skipping")
			return CompositionEndAction()
		# No result — try to resolve what was selected
		# Prefer selectedCandidate (reliable from both arrow-key and digit-key paths)
		if self.selectedCandidate:
			log.debug(f"IME_EXP: Composition end — using selected candidate: '{self.selectedCandidate}'")
			return CompositionEndAction(textToSpeak=self.selectedCandidate)
		# Fallback: resolve by index (for edge cases where selectedCandidate was not set)
		if self.selectedCandidateIndex > 0:
			try:
				if self.modernImeCandidateMap:
					ch = self.modernImeCandidateMap[self.selectedCandidateIndex]
				else:
					ch = self.candidateList[self.selectedCandidateIndex - 1]
				while ch and unicodedata.category(ch[-1]) != "Lo":
					ch = ch[:-1]
				if not ch:
					log.debug(
						f"IME_EXP: Composition end — resolved empty candidate from index {self.selectedCandidateIndex}"
					)
					return CompositionEndAction()
				log.debug(
					f"IME_EXP: Composition end — resolved from index {self.selectedCandidateIndex}: '{ch}'"
				)
				return CompositionEndAction(textToSpeak=ch, resolvedFromIndex=True)
			except Exception:
				log.debug("IME_EXP: Failed to resolve candidate by index, falling back")
		log.debug("IME_EXP: Composition end — no candidate found, deferring to punctuation check")
		return CompositionEndAction(fallbackToPunc=True)

	def clear(self) -> None:
		"""Reset all IME session state."""
		log.debug("IME_EXP: Clearing IME session state")
		self.isImeSessionFinished = True
		self.lastCandidatesString = ""
		self.selectedCandidate = ""
		self.selectedCandidateIndex = 0
		self.candidateList = []
		self.isMicrosoftPinyin = False
		self.modernImeCandidateMap = {}
		self.lastCompositionString = ""
		self.lastModernImeEventTime = 0

	def startSession(self) -> None:
		"""Mark that an IME input session has started."""
		self.isImeSessionFinished = False
		log.debug("IME_EXP: IME session started")

	def recordCandidateSelection(self, index: int, name: str) -> None:
		"""Record a candidate selection from modern IME UIA nameChange events."""
		self.modernImeCandidateMap[index] = name
		log.debug(f"IME_EXP: Modern IME candidate recorded: [{index}] = '{name}'")
