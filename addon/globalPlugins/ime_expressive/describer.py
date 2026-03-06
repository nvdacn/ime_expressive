# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2025 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""Pure logic layer for describing IME candidate characters.

Given a candidate string and current settings, this module produces
the speech text to describe the candidate.
"""

from __future__ import annotations

import characterProcessing
from logHandler import log
from .enums import DescriptionMode, ReportThreshold


class CandidateDescriber:
	"""Builds speech text for IME candidate descriptions.

	Character descriptions come from characterProcessing.getCharacterDescription('zh_CN', ch).
	For Chinese characters, the first description is typically wrapped in parentheses
	like "(就是的就)" — this class strips them to produce "就是的就".
	"""

	def __init__(self, descriptionMode: DescriptionMode, reportThreshold: ReportThreshold):
		self._descriptionMode = descriptionMode
		self._reportThreshold = reportThreshold

	@property
	def descriptionMode(self) -> DescriptionMode:
		return self._descriptionMode

	@descriptionMode.setter
	def descriptionMode(self, value: DescriptionMode) -> None:
		self._descriptionMode = value

	@property
	def reportThreshold(self) -> ReportThreshold:
		return self._reportThreshold

	@reportThreshold.setter
	def reportThreshold(self, value: ReportThreshold) -> None:
		self._reportThreshold = value

	def describeCharacters(self, candidate: str) -> str:
		"""Build a space-separated description string for each character in candidate.

		For each char, looks up zh_CN character descriptions.
		If the first description is "(X)", strips parens → "X".
		Otherwise formats as "{symbol} as in {description}".
		Chars with no description are passed through as-is.
		"""
		describedSymbols: list[str] = []
		for symbol in candidate:
			try:
				symbolDescriptions = characterProcessing.getCharacterDescription('zh_CN', symbol) or []
			except TypeError:
				symbolDescriptions = []
			if len(symbolDescriptions) >= 1:
				description = symbolDescriptions[0]
				if description.startswith('(') and description.endswith(')'):
					describedSymbols.append(description[1:-1])
				else:
					describedSymbols.append(
						_(
							# Translators: Used to describe a character using a word it appears in.
							# For example: "A as in Apple".
							"{symbol} as in {description}"
						).format(symbol=symbol, description=description)
					)
			else:
				describedSymbols.append(symbol)
		result = ' '.join(describedSymbols)
		log.debug(f"IME_EXP: describeCharacters('{candidate}') -> '{result}'")
		return result

	def computeEffectiveLength(self, candidate: str) -> int:
		"""Compute candidate length ignoring trailing lowercase ASCII letters.

		Some IME candidates have trailing pinyin letters (e.g. "今tian"),
		this strips them to get the "real" character count.
		"""
		temp = candidate
		while temp and temp[-1].islower():
			temp = temp[:-1]
		return len(temp)

	def formatAllCandidates(self, candidatesString: str, selectionIndex: int) -> str:
		"""Format all candidates for autoReport mode.

		Multi-candidate: "候选1 1；候选2 2；..."
		Single candidate: "候选文本 N"
		"""
		if '\n' in candidatesString:
			items = candidatesString.split('\n')
			parts: list[str] = []
			for i, item in enumerate(items, start=1):
				parts.append(f"{item}{i}")
			return '； '.join(parts) + '； '
		return candidatesString + str(selectionIndex + 1)

	def buildSpeechParts(
		self,
		candidate: str,
	) -> tuple[str | None, str | None, bool]:
		"""Determine what to speak for a candidate, based on current settings.

		:return: (prefixText, descriptionText, cancelBeforeDescription)
			- prefixText: the raw candidate to speak before description, or None
			- descriptionText: the character-by-character description, or None
			- cancelBeforeDescription: if True, cancel speech before speaking the description

		Mirrors the original threshold logic:
		- Prefix always spoken with cancel=True (default).
		- Description spoken with cancel=True only if prefix was NOT spoken.
		"""
		try:
			candidateLen = self.computeEffectiveLength(candidate)
		except Exception:
			log.debug(f"IME_EXP: buildSpeechParts failed to compute length for '{candidate}'")
			return None, candidate, True
		prefixText: str | None = None
		descriptionText: str | None = None
		cancelBeforeDescription = True
		# Speak raw candidate as prefix when candidateLen exceeds threshold
		customCandidate = candidateLen > self._reportThreshold
		if (
			candidateLen >= self._reportThreshold + 1
			and customCandidate
			and self._reportThreshold != ReportThreshold.NEVER
		):
			prefixText = candidate
			cancelBeforeDescription = False  # prefix was spoken, don't cancel it for description
		# Produce character description when within description mode range
		if candidateLen <= self._descriptionMode or self._descriptionMode >= DescriptionMode.FULL:
			descriptionText = self.describeCharacters(candidate)
		log.debug(
			f"IME_EXP: buildSpeechParts('{candidate}', len={candidateLen}) "
			f"-> prefix={prefixText!r}, description={descriptionText!r}, cancelDescription={cancelBeforeDescription}"
		)
		return prefixText, descriptionText, cancelBeforeDescription
