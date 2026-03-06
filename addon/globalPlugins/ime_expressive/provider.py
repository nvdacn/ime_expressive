# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2025 NVDA Chinese Community Contributors
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

	DEBOUNCE_INTERVAL: float = 0.05  # 50ms duplicate suppression

	def __init__(self):
		self.isMicrosoftPinyin: bool = False
		self.isImeSessionFinished: bool = True
		self.selectedCandidate: str = ""
		self.selectedCandidateIndex: int = 0
		self.candidateList: list[str] = []
		self.lastCandidatesString: str = ""
		self.lastCandidateSpeechTime: float = 0
		self.lastLayoutString: str = ""
		self.modernImeCandidateMap: dict[int, str] = {}
		self.lastModernImeEventTime: float = 0

	def shouldSkipUpdate(self, candidatesString: str, inputMethod: str) -> bool:
		"""Check if this update should be skipped (session finished or duplicate)."""
		if inputMethod == "ms" and self.isImeSessionFinished:
			log.debug("IME_EXP: Skipping update — session finished for modern IME")
			return True
		if not candidatesString:
			return True
		currentTime = time.time()
		if (
			candidatesString == self.lastCandidatesString
			and currentTime - self.lastCandidateSpeechTime < self.DEBOUNCE_INTERVAL
		):
			log.debug("IME_EXP: Skipping duplicate candidate within debounce window")
			return True
		return False

	def processCandidateUpdate(
		self,
		candidatesString: str,
		selectionIndex: int,
		inputMethod: str,
	) -> CandidateUpdate | None:
		"""Parse a candidate list update and update internal state.

		:return: CandidateUpdate if the update should be spoken, None if skipped.
		"""
		if self.shouldSkipUpdate(candidatesString, inputMethod):
			return None
		self.lastCandidateSpeechTime = time.time()
		self.lastCandidatesString = candidatesString
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

		Mirrors the original handleInputCompositionEnd branch structure:
		  if result:    speak result only if it matches lastCandidatesString
		  else:         try index → selectedCandidate → fallback to punc
		"""
		self.lastCandidateSpeechTime = self.lastModernImeEventTime = time.time()
		if result:
			if not self.lastCandidatesString or result in self.lastCandidatesString:
				log.debug(f"IME_EXP: Composition end — result matches candidates: '{result}'")
				return CompositionEndAction(textToSpeak=result)
			log.debug(f"IME_EXP: Composition end — result '{result}' not in candidates, skipping")
			return CompositionEndAction()
		# No result — try to resolve what was selected
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
				self.selectedCandidateIndex = 0
				self.selectedCandidate = ""
		if self.selectedCandidate:
			log.debug(f"IME_EXP: Composition end — using selected candidate: '{self.selectedCandidate}'")
			return CompositionEndAction(textToSpeak=self.selectedCandidate)
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

	def startSession(self) -> None:
		"""Mark that an IME input session has started."""
		self.isImeSessionFinished = False
		log.debug("IME_EXP: IME session started")

	def recordCandidateSelection(self, index: int, name: str) -> None:
		"""Record a candidate selection from modern IME UIA nameChange events."""
		self.modernImeCandidateMap[index] = name
		log.debug(f"IME_EXP: Modern IME candidate recorded: [{index}] = '{name}'")
