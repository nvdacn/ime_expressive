# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2025 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""IME Expressive — Enhanced Chinese IME speech feedback for NVDA.

Provides character-by-character explanations for IME candidates,
modern IME (Windows 11 UIA) support, and customizable speech behavior.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from typing import Any

import api
import brailleInput
import characterProcessing
import config
import controlTypes
import globalPluginHandler
import NVDAHelper
import queueHandler
import speech
import textInfos
import winUser
import wx
from buildVersion import version_year
from keyboardHandler import KeyboardInputGesture
from logHandler import log
from NVDAObjects import NVDAObject
from NVDAObjects.behaviors import CandidateItem
from NVDAObjects.UIA import UIA

from . import settings
from .describer import CandidateDescriber
from .provider import ImeStateManager
from .uiaHelper import ModernImeHelper

role = controlTypes.Role if version_year >= 2022 else controlTypes.role.Role

# Virtual key codes used in script_pressKey
VK_ESCAPE = 27
VK_1 = 49
VK_9 = 57
# LCID for Simplified Chinese (used to detect Chinese IME active)
LCID_CHINESE_SIMPLIFIED = 2052

CONF_SECTION = "imeExpressive"


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Enhanced Chinese IME feedback for NVDA.

	Intercepts IME callbacks from NVDAHelper and UIA events to provide
	character-by-character explanations matching Chinese user habits.
	"""

	scriptCategory = "IME Expressive"

	def __init__(self):
		super().__init__()
		settings.initConfig()
		settings.installSettingsPanel()
		self._originalHooks: dict[str, Any] = {}
		self._describer = CandidateDescriber(
			settings.getDescriptionMode(),
			settings.getReportThreshold(),
		)
		self._state = ImeStateManager()
		self._uia = ModernImeHelper()
		self._shouldMuteReturnTransition: bool = False
		self._shouldSkipCompositionStart: bool = False
		self._currentCompositionString: str = ""
		self._entryGestures: dict[str, str] = settings.buildGestureMap()
		self._installHooks()

	def _installHooks(self) -> None:
		"""Monkey-patch NVDAHelper and CandidateItem methods."""
		self._originalHooks["CandidateItem.getFormattedCandidateName"] = CandidateItem.getFormattedCandidateName
		self._originalHooks["CandidateItem.getFormattedCandidateDescription"] = CandidateItem.getFormattedCandidateDescription
		self._originalHooks["CandidateItem.reportFocus"] = CandidateItem.reportFocus
		self._originalHooks["NVDAHelper.handleInputCandidateListUpdate"] = NVDAHelper.handleInputCandidateListUpdate
		self._originalHooks["NVDAHelper.handleInputCompositionStart"] = NVDAHelper.handleInputCompositionStart
		self._originalHooks["NVDAHelper.handleInputCompositionEnd"] = NVDAHelper.handleInputCompositionEnd
		self._originalHooks["NVDAHelper.handleInputConversionModeUpdate"] = NVDAHelper.handleInputConversionModeUpdate
		CandidateItem.getFormattedCandidateName = self._noopFormatter
		CandidateItem.getFormattedCandidateDescription = self._noopDescFormatter
		CandidateItem.reportFocus = self._noopReportFocus
		NVDAHelper.handleInputCandidateListUpdate = self.handleInputCandidateListUpdate
		NVDAHelper.handleInputCompositionStart = self.handleInputCompositionStart
		NVDAHelper.handleInputCompositionEnd = self.handleInputCompositionEnd
		NVDAHelper.handleInputConversionModeUpdate = self.handleInputConversionModeUpdate

	def terminate(self) -> None:
		CandidateItem.getFormattedCandidateName = self._originalHooks.get("CandidateItem.getFormattedCandidateName", CandidateItem.getFormattedCandidateName)
		CandidateItem.getFormattedCandidateDescription = self._originalHooks.get("CandidateItem.getFormattedCandidateDescription", CandidateItem.getFormattedCandidateDescription)
		CandidateItem.reportFocus = self._originalHooks.get("CandidateItem.reportFocus", CandidateItem.reportFocus)
		NVDAHelper.handleInputCandidateListUpdate = self._originalHooks.get("NVDAHelper.handleInputCandidateListUpdate", NVDAHelper.handleInputCandidateListUpdate)
		NVDAHelper.handleInputCompositionStart = self._originalHooks.get("NVDAHelper.handleInputCompositionStart", NVDAHelper.handleInputCompositionStart)
		NVDAHelper.handleInputCompositionEnd = self._originalHooks.get("NVDAHelper.handleInputCompositionEnd", NVDAHelper.handleInputCompositionEnd)
		NVDAHelper.handleInputConversionModeUpdate = self._originalHooks.get("NVDAHelper.handleInputConversionModeUpdate", NVDAHelper.handleInputConversionModeUpdate)
		settings.restoreSettingsPanel()
		super().terminate()

	def _noopFormatter(self, number: int, candidate: str) -> None:
		pass

	def _noopDescFormatter(self, candidate: str) -> None:
		pass

	def _noopReportFocus(self) -> None:
		pass

	def event_foreground(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isModernImeProcess(obj) and not self._state.isImeSessionFinished:
			return
		if self._shouldMuteReturnTransition:
			log.debug(f"IME_EXP: Muting return foreground on {obj.name}")
			return
		nextHandler()

	def event_focusEntered(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isModernImeProcess(obj) and not self._state.isImeSessionFinished:
			return
		if self._shouldMuteReturnTransition:
			return
		nextHandler()

	def event_gainFocus(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isModernImeProcess(obj) and not self._state.isImeSessionFinished:
			return
		if self._shouldMuteReturnTransition:
			self._shouldMuteReturnTransition = False
			log.debug(f"IME_EXP: Muting return gainFocus on {obj.name}. Transition done.")
			return
		if self._uia.isMicrosoftPinyinFromUia and isinstance(obj, UIA):
			self._uia.isMicrosoftPinyinFromUia = False
		else:
			nextHandler()

	def event_UIA_window_windowOpen(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isImeCandidateWindow(obj):
			self._shouldSkipCompositionStart = True
			self._state.isMicrosoftPinyin = True
			log.debug("IME_EXP: Modern IME candidate window opened")
			try:
				firstChild = obj.firstChild
				if firstChild and firstChild.firstChild:
					self._uia.cacheWindow(obj)
					result = self._uia.findCandidateTarget()
					if result:
						target, candidateText = result
						self._uia.isMicrosoftPinyinFromUia = True
						self._state.isMicrosoftPinyin = True
						self.handleInputCandidateListUpdate(candidateText, 0, "ms")
						self._setNavigatorObject(target)
			except Exception:
				log.debug("IME_EXP: Error processing modern IME window", exc_info=True)
			return
		nextHandler()

	def event_UIA_elementSelected(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		# On Win11, elementSelected may fire before windowOpen — ignore until window is cached
		if self._uia.cachedWindow is None:
			nextHandler()
			return
		try:
			if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj, CandidateItem):
				firstChild = obj.firstChild
				lastChild = obj.lastChild
				if firstChild and lastChild:
					self._uia.isMicrosoftPinyinFromUia = True
					self._state.isMicrosoftPinyin = True
					self.handleInputCandidateListUpdate(lastChild.name, int(firstChild.name) - 1, "ms")
					self._setNavigatorObject(obj)
		except Exception:
			pass
		finally:
			nextHandler()

	def event_UIA_notification(self, obj: NVDAObject, nextHandler: Callable[[], None], *args: Any, **kwargs: Any) -> None:
		if obj.role == role.BUTTON and obj.UIAElement.cachedAutomationID == "NewNoteButton":
			pass
		else:
			nextHandler()

	def event_nameChange(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		try:
			if (
				self._state.isMicrosoftPinyin
				and obj.role == role.STATICTEXT
				and obj.windowClassName == "Windows.UI.Core.CoreWindow"
				and isinstance(obj.parent, CandidateItem)
			):
				previous = obj.previous
				if previous and previous.name:
					self._state.recordCandidateSelection(int(previous.name), obj.name)
		except Exception:
			pass
		finally:
			nextHandler()

	_inputConversionModeMessages: dict[int, tuple[str, str]] = {
		1: ("中文", "英文"),
		8: ("全角", "半角"),
		1024: ("中文标点", "英文标点"),
	}

	def handleInputConversionModeUpdate(self, oldFlags: int, newFlags: int, lcid: int) -> None:
		log.debug(f"IME_EXP: Conversion mode: {oldFlags} -> {newFlags}, lcid={lcid}")
		self._clearIme()
		for x in range(32):
			x_val = 2**x
			msgs = self._inputConversionModeMessages.get(x_val)
			if not msgs:
				continue
			newOn = bool(newFlags & x_val)
			oldOn = bool(oldFlags & x_val)
			if newOn != oldOn:
				self._speakCharacter(msgs[0] if newOn else msgs[1], cancelFirst=False)
				break

	def handleInputCandidateListUpdate(self, candidatesString: str, selectionIndex: int, inputMethod: str) -> None:
		log.debug(
			f"IME_EXP: Candidate list update: string='{candidatesString}', "
			f"index={selectionIndex}, method={inputMethod}"
		)
		self._describer.descriptionMode = settings.getDescriptionMode()
		self._describer.reportThreshold = settings.getReportThreshold()
		if NVDAHelper.lastLayoutString != self._state.lastLayoutString:
			self._state.lastLayoutString = NVDAHelper.lastLayoutString
		update = self._state.processCandidateUpdate(
			candidatesString, selectionIndex, self._currentCompositionString, inputMethod
		)
		if update is None:
			return
		candidate = update.candidate
		if settings.isAutoReportAllCandidates():
			self.bindGestures(self._entryGestures)
			msg = self._describer.formatAllCandidates(candidatesString, selectionIndex)
			isMulti = "\n" in candidatesString
			self._speakCharacter(msg, passthrough=not isMulti)
			return
		# Normal mode — use describer
		prefixText, descriptionText, cancelBeforeDescription = self._describer.buildSpeechParts(candidate)
		if prefixText is not None:
			self.bindGestures(self._entryGestures)
			self._speakCharacter(prefixText)  # cancelFirst=True by default
		if descriptionText is not None:
			self.bindGestures(self._entryGestures)
			self._speakCharacter(descriptionText, cancelFirst=cancelBeforeDescription)

	def handleInputCompositionStart(self, compositionString: str, selectionStart: int, selectionEnd: int, isReading: bool) -> None:
		log.debug(f"IME_EXP: Composition start: '{compositionString}'")
		self._currentCompositionString = compositionString
		self._state.startSession()
		if self._shouldSkipCompositionStart:
			self._shouldSkipCompositionStart = False
			return
		try:
			result = self._uia.findCandidateTarget()
			if result:
				target, candidateText = result
				self._uia.isMicrosoftPinyinFromUia = True
				self._state.isMicrosoftPinyin = True
				self.handleInputCandidateListUpdate(candidateText, 0, "ms")
				self._setNavigatorObject(target)
		except Exception:
			pass

	def handleInputCompositionEnd(self, result: str) -> None:
		log.debug(f"IME_EXP: Composition end: result='{result}'")
		if settings.isReportCompositionStringChanges():
			action = self._state.resolveCompositionEnd(result)
			if action.fallbackToPunc:
				wx.CallLater(40, self._speakPunc)
			elif action.textToSpeak is not None:
				self._speakCharacter(action.textToSpeak)
				if action.resolvedFromIndex:
					self._clearIme()
					if self._state.isMicrosoftPinyin:
						self._shouldMuteReturnTransition = True
					return
		if self._state.isMicrosoftPinyin:
			self._shouldMuteReturnTransition = True
		self._clearIme()

	def _speakCharacter(self, character: str, cancelFirst: bool = True, passthrough: bool = True) -> None:
		"""Speak a character/string with appropriate method.

		:param cancelFirst: if True, cancel current speech before speaking
		:param passthrough: if True, use speakText with symbolLevel=ALL; otherwise speakMessage
		"""
		if cancelFirst:
			speech.cancelSpeech()
		if len(character) == 1 and character.isupper():
			speech.speakTypedCharacters(character)
		else:
			if passthrough:
				speech.speakText(character, symbolLevel=characterProcessing.SymbolLevel.ALL)
			else:
				speech.speakMessage(character)

	def _speakPunc(self) -> None:
		charInfo = api.getReviewPosition().copy()
		charInfo.expand(textInfos.UNIT_CHARACTER)
		charInfo.collapse()
		charInfo.move(textInfos.UNIT_CHARACTER, -1)
		api.setReviewPosition(charInfo)
		charInfo.expand(textInfos.UNIT_CHARACTER)
		t = charInfo.text
		if t and len(t) == 1:
			if unicodedata.category(t)[0] in "PS":
				self._speakCharacter(t)
		charInfo.collapse()
		charInfo.move(textInfos.UNIT_CHARACTER, 1)
		api.setReviewPosition(charInfo)

	def _clearIme(self) -> None:
		"""Reset all IME state, navigator object, and gesture bindings."""
		self._state.clear()
		self._currentCompositionString = ""
		navObj = api.getNavigatorObject()
		if navObj and not navObj.isFocusable and self._uia.isModernImeProcess(navObj):
			self._setNavigatorObject(api.getFocusObject())
		self._uia.invalidateCache()
		self.clearGestureBindings()
		log.debug("IME_EXP: IME state and gestures cleared")

	def _setNavigatorObject(self, obj: NVDAObject) -> None:
		if config.conf["reviewCursor"]["followFocus"]:
			api.setNavigatorObject(obj)

	def script_pressKey(self, gesture: KeyboardInputGesture) -> None:
		keyCode = gesture.vkCode
		if VK_1 <= keyCode <= VK_9:
			self._state.selectedCandidateIndex = int(chr(keyCode))
		elif keyCode == VK_ESCAPE:
			self._clearIme()
		if NVDAHelper.lastLayoutString != self._state.lastLayoutString:
			self._state.lastLayoutString = NVDAHelper.lastLayoutString
			self._clearIme()
			wx.CallAfter(winUser.keybd_event, keyCode, 0, 1, 0)
			wx.CallAfter(winUser.keybd_event, keyCode, 0, 3, 0)
			return
		if NVDAHelper.lastLanguageID == LCID_CHINESE_SIMPLIFIED:
			gesture.send()
		else:
			self._clearIme()
			wx.CallAfter(winUser.keybd_event, keyCode, 0, 1, 0)
			wx.CallAfter(winUser.keybd_event, keyCode, 0, 3, 0)

	def script_pressKeyUp(self, gesture: KeyboardInputGesture) -> None:
		KeyboardInputGesture.fromName("uparrow").send()

	def script_pressKeyDown(self, gesture: KeyboardInputGesture) -> None:
		KeyboardInputGesture.fromName("downarrow").send()

	def script_selectLeft(self, gesture: KeyboardInputGesture) -> None:
		if self._state.selectedCandidate and len(self._state.selectedCandidate) > 1:
			KeyboardInputGesture.fromName("escape").send()
			queueHandler.queueFunction(queueHandler.eventQueue, speech.cancelSpeech)
			wx.CallAfter(brailleInput.handler.sendChars, self._state.selectedCandidate[0])
			self.clearGestureBindings()

	def script_selectRight(self, gesture: KeyboardInputGesture) -> None:
		length = len(self._state.selectedCandidate)
		if self._state.selectedCandidate and length > 1:
			KeyboardInputGesture.fromName("escape").send()
			chList = list(self._state.selectedCandidate)
			for c in range(length):
				ch = chList.pop()
				if unicodedata.category(ch) == "Lo":
					queueHandler.queueFunction(queueHandler.eventQueue, speech.cancelSpeech)
					wx.CallAfter(brailleInput.handler.sendChars, ch)
					break
			self.clearGestureBindings()
