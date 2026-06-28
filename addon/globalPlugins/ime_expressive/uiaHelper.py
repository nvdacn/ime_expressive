# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2026 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""UIA helper for Windows 11 modern IME candidate windows.

Handles detection and caching of the modern IME window (TextInputHost.exe)
which uses UIA instead of IMM/TSF for candidate display.

The UIAAutomationId-based filtering distinguishes IME candidate windows
from emoji panel, clipboard history, and other TextInputHost windows.
These IDs are sourced from NVDA's built-in appModule:
  windowsinternal_composableshell_experiences_textinput_inputapp.py
"""

from __future__ import annotations

import winVersion
from NVDAObjects import NVDAObject
from NVDAObjects.behaviors import CandidateItem

# UIAAutomationIds that identify IME candidate-related windows.
# Checked on the firstChild of a TextInputHost window to distinguish
# IME candidates from emoji panel, clipboard history, etc.
_IME_CANDIDATE_AUTOMATION_IDS = frozenset(
	{
		"IME_Candidate_Window",
		"IME_Prediction_Window",
		"TEMPLATE_PART_CandidatePanel",
		"CandidateWindowControl",
	},
)


class ModernImeHelper:
	"""Caches and manages UIA objects for the modern IME candidate window."""

	def __init__(self):
		self._cachedWindow: NVDAObject | None = None
		self.isMicrosoftPinyinFromUia: bool = False

	@staticmethod
	def isModernImeProcess(obj: NVDAObject) -> bool:
		"""Check if an NVDA object belongs to TextInputHost.exe.

		This is a broad process-level check. Use isImeCandidateWindow()
		for precise IME candidate detection.
		"""
		try:
			appModule = obj.appModule if obj is not None else None
			return appModule is not None and appModule.appName.lower() == "textinputhost"
		except Exception:
			return False

	@staticmethod
	def isImeCandidateWindow(obj: NVDAObject) -> bool:
		"""Check if a TextInputHost window is specifically an IME candidate window.

		Uses UIAAutomationId on the first child to distinguish IME candidates
		from emoji panel, clipboard history, and other TextInputHost windows.
		Falls back to True if firstChild has no UIAAutomationId (conservative).
		"""
		try:
			if obj is None or obj.windowClassName != "Windows.UI.Core.CoreWindow":
				return False
			appModule = obj.appModule
			if appModule is None or appModule.appName.lower() != "textinputhost":
				return False
			firstChild = obj.firstChild
			if firstChild is None:
				return False
			automationId = getattr(firstChild, "UIAAutomationId", None)
			if automationId is None:
				# No AutomationId available — conservative fallback
				return True
			return automationId in _IME_CANDIDATE_AUTOMATION_IDS
		except Exception:
			return False

	def cacheWindow(self, obj: NVDAObject) -> None:
		"""Cache the modern IME window object, adjusting for Win11 structure."""
		isWin11 = winVersion.getWinVer() >= winVersion.WIN11
		if isWin11:
			firstChild = obj.firstChild
			self._cachedWindow = firstChild if firstChild else obj
		else:
			self._cachedWindow = obj

	def invalidateCache(self) -> None:
		self._cachedWindow = None
		self.isMicrosoftPinyinFromUia = False

	def findCandidateTarget(self) -> tuple[NVDAObject, str] | None:
		"""Try to find the candidate target from the cached modern IME window.

		:return: (candidateTarget, candidateText) or None if not found.
		"""
		window = self._cachedWindow
		if not window:
			return None
		try:
			firstChild = window.firstChild
			if firstChild:
				target = firstChild.firstChild
				if (
					isinstance(target, CandidateItem)
					and target.windowClassName == "Windows.UI.Core.CoreWindow"
				):
					lastChild = target.lastChild
					candidateText = lastChild.name if lastChild else ""
					self.isMicrosoftPinyinFromUia = True
					return target, candidateText
		except Exception:
			pass
		return None
