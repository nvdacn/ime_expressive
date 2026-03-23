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
	- awaitMoreResults: keep state briefly and wait for a follow-up callback
	- (both None/False): do nothing
	"""

	textToSpeak: str | None = None
	fallbackToPunc: bool = False
	awaitMoreResults: bool = False


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
		self.lastCompositionEndText: str = ""
		self.lastCompositionEndInputToken: int | None = None
		self._pendingCompositionEndInputToken: int | None = None
		self._pendingSelectedCandidate: str = ""
		self._pendingSelectedCandidateIndex: int = 0
		self._pendingCandidateList: list[str] = []
		self._pendingLastCandidatesString: str = ""
		self._pendingModernImeCandidateMap: dict[int, str] = {}

	def _clearCompositionEndSnapshot(self) -> None:
		self._pendingCompositionEndInputToken = None
		self._pendingSelectedCandidate = ""
		self._pendingSelectedCandidateIndex = 0
		self._pendingCandidateList = []
		self._pendingLastCandidatesString = ""
		self._pendingModernImeCandidateMap = {}

	def _captureCompositionEndSnapshot(self, inputEventToken: int | None) -> None:
		if inputEventToken is None:
			return
		self._pendingCompositionEndInputToken = inputEventToken
		self._pendingSelectedCandidate = self.selectedCandidate
		self._pendingSelectedCandidateIndex = self.selectedCandidateIndex
		self._pendingCandidateList = list(self.candidateList)
		self._pendingLastCandidatesString = self.lastCandidatesString
		self._pendingModernImeCandidateMap = dict(self.modernImeCandidateMap)

	def _buildCompositionEndAction(
		self,
		textToSpeak: str | None = None,
		*,
		fallbackToPunc: bool = False,
		inputEventToken: int | None = None,
	) -> CompositionEndAction:
		if textToSpeak and (
			inputEventToken is not None
			and inputEventToken == self.lastCompositionEndInputToken
			and textToSpeak == self.lastCompositionEndText
		):
			log.debug(
				f"IME_EXP: Composition end - skipping duplicate committed text "
				f"for same input: '{textToSpeak}'"
			)
			return CompositionEndAction()
		if textToSpeak:
			self.lastCompositionEndText = textToSpeak
			self.lastCompositionEndInputToken = inputEventToken
		self._clearCompositionEndSnapshot()
		return CompositionEndAction(
			textToSpeak=textToSpeak,
			fallbackToPunc=fallbackToPunc,
		)

	def _getCompositionEndContext(
		self,
		inputEventToken: int | None,
	) -> tuple[str, int, list[str], str, dict[int, str]]:
		if (
			not self.selectedCandidate
			and not self.lastCandidatesString
			and not self.candidateList
			and not self.modernImeCandidateMap
			and inputEventToken is not None
			and inputEventToken == self._pendingCompositionEndInputToken
		):
			return (
				self._pendingSelectedCandidate,
				self._pendingSelectedCandidateIndex,
				self._pendingCandidateList,
				self._pendingLastCandidatesString,
				self._pendingModernImeCandidateMap,
			)
		return (
			self.selectedCandidate,
			self.selectedCandidateIndex,
			self.candidateList,
			self.lastCandidatesString,
			self.modernImeCandidateMap,
		)

	def shouldSkipUpdate(
		self,
		candidatesString: str,
		selectionIndex: int,
		compositionString: str,
		inputMethod: str,
	) -> bool:
		"""Check if this update should be skipped (session finished or exact duplicate)."""
		if inputMethod == "ms" and self.isImeSessionFinished:
			log.debug("IME_EXP: Skipping update - session finished for modern IME")
			return True
		if not candidatesString:
			return True

		# Exact duplicate suppression: skip ONLY if text, selection index AND
		# composition string are all the same as last reported ones.
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

	def resolveCompositionEnd(
		self,
		result: str,
		inputEventToken: int | None = None,
	) -> CompositionEndAction:
		"""Determine what the controller should do when composition ends."""
		(
			selectedCandidate,
			selectedCandidateIndex,
			candidateList,
			lastCandidatesString,
			modernImeCandidateMap,
		) = self._getCompositionEndContext(inputEventToken)
		if result:
			if self.isMicrosoftPinyin:
				log.debug(
					f"IME_EXP: Composition end - trusting committed result from modern Microsoft IME: '{result}'"
				)
				return self._buildCompositionEndAction(result, inputEventToken=inputEventToken)
			# When we have a tracked candidate, validate result against it to reject
			# stale compositionEnd events (for example, a partial result arriving
			# just before the final committed text).
			if selectedCandidate:
				if result in selectedCandidate or selectedCandidate in result:
					log.debug(f"IME_EXP: Composition end - result matches selected candidate: '{result}'")
					return self._buildCompositionEndAction(result, inputEventToken=inputEventToken)
				log.debug(
					f"IME_EXP: Composition end - result '{result}' doesn't match "
					f"selected candidate '{selectedCandidate}', waiting for follow-up"
				)
				self._captureCompositionEndSnapshot(inputEventToken)
				return CompositionEndAction(awaitMoreResults=True)
			if not lastCandidatesString or result in lastCandidatesString:
				log.debug(f"IME_EXP: Composition end - result matches candidates: '{result}'")
				return self._buildCompositionEndAction(result, inputEventToken=inputEventToken)
			log.debug(f"IME_EXP: Composition end - result '{result}' not in candidates, waiting for follow-up")
			self._captureCompositionEndSnapshot(inputEventToken)
			return CompositionEndAction(awaitMoreResults=True)
		if selectedCandidate:
			log.debug(f"IME_EXP: Composition end - using selected candidate: '{selectedCandidate}'")
			return self._buildCompositionEndAction(
				selectedCandidate,
				inputEventToken=inputEventToken,
			)
		if selectedCandidateIndex > 0:
			try:
				if modernImeCandidateMap:
					ch = modernImeCandidateMap[selectedCandidateIndex]
				else:
					ch = candidateList[selectedCandidateIndex - 1]
				while ch and unicodedata.category(ch[-1]) != "Lo":
					ch = ch[:-1]
				if not ch:
					log.debug(
						f"IME_EXP: Composition end - resolved empty candidate from index {selectedCandidateIndex}"
					)
					return CompositionEndAction()
				log.debug(
					f"IME_EXP: Composition end - resolved from index {selectedCandidateIndex}: '{ch}'"
				)
				return self._buildCompositionEndAction(
					ch,
					inputEventToken=inputEventToken,
				)
			except Exception:
				log.debug("IME_EXP: Failed to resolve candidate by index, falling back")
		log.debug("IME_EXP: Composition end - no candidate found, deferring to punctuation check")
		return self._buildCompositionEndAction(
			fallbackToPunc=True,
			inputEventToken=inputEventToken,
		)

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

	def startSession(self) -> None:
		"""Mark that an IME input session has started."""
		self.isImeSessionFinished = False
		self.lastCompositionEndText = ""
		self.lastCompositionEndInputToken = None
		self._clearCompositionEndSnapshot()
		log.debug("IME_EXP: IME session started")

	def recordCandidateSelection(self, index: int, name: str) -> None:
		"""Record a candidate selection from modern IME UIA nameChange events."""
		self.modernImeCandidateMap[index] = name
		log.debug(f"IME_EXP: Modern IME candidate recorded: [{index}] = '{name}'")
