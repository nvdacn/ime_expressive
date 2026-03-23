# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2026 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""IME Expressive — Enhanced Chinese IME speech feedback for NVDA.

Provides character-by-character descriptions for IME candidates,
modern IME (Windows 11 UIA) support, and customizable speech behavior.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from typing import Any

import api
import addonHandler
import brailleInput
import characterProcessing
from comtypes import COMError
import config
import controlTypes
import eventHandler
import globalPluginHandler
import inputCore
import NVDAHelper
import queueHandler
import speech
import textInfos
import winUser
import wx
from keyboardHandler import KeyboardInputGesture
from logHandler import log
from NVDAObjects import NVDAObject
from NVDAObjects.behaviors import CandidateItem
from NVDAObjects.UIA import UIA

from . import settings
from .describer import CandidateDescriber
from .provider import ImeStateManager
from .uiaHelper import ModernImeHelper

addonHandler.initTranslation()

# Virtual key codes used in script_pressKey
VK_ESCAPE = 27
VK_1 = 49
VK_9 = 57
# LCID for Simplified Chinese (used to detect Chinese IME active)
LCID_CHINESE_SIMPLIFIED = 2052
PRIMARY_LANGUAGE_MASK = 0x3FF
LANG_CHINESE = 0x04

CONF_SECTION = "imeExpressive"


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""Enhanced Chinese IME feedback for NVDA.

	Intercepts IME callbacks from NVDAHelper and UIA events to provide
	character-by-character descriptions matching Chinese user habits.
	"""
	_MUTE_TRANSITION_TIMEOUT_MS = 150

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
		self._currentCompositionString: str = ""
		self._lastAutoReportCandidatesString: str = ""
		self._lastNonTrackedInputTime: int | None = None
		self._lastInputToken: int | None = None
		self._nextInputToken: int = 0
		self._muteTransitionTimer: wx.CallLater | None = None
		self._entryGestures: dict[str, str] = settings.buildGestureMap()
		self._installHooks()
		inputCore.decide_executeGesture.register(self._onDecideExecuteGesture)
		settings.registerSaveCallback(self._onSettingsSaved)

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
		inputCore.decide_executeGesture.unregister(self._onDecideExecuteGesture)
		settings.unregisterSaveCallback(self._onSettingsSaved)
		settings.restoreSettingsPanel()
		super().terminate()

	def _noopFormatter(self, number: int, candidate: str) -> None:
		pass

	def _noopDescFormatter(self, candidate: str) -> None:
		pass

	def _noopReportFocus(self) -> None:
		pass

	def _onSettingsSaved(self) -> None:
		self._entryGestures = settings.buildGestureMap()
		log.debug("IME_EXP: Gesture map rebuilt after settings change")

	def _onDecideExecuteGesture(self, gesture: inputCore.InputGesture) -> bool:
		if gesture.isModifier:
			return True
		self._nextInputToken += 1
		self._lastInputToken = self._nextInputToken
		return True

	def _refreshNonTrackedDedupBoundary(self) -> None:
		if self._currentCompositionString or self._state.isMicrosoftPinyin:
			return
		currentInputToken = self._lastInputToken
		if currentInputToken is None or currentInputToken == self._lastNonTrackedInputTime:
			return
		self._lastNonTrackedInputTime = currentInputToken
		self._state.lastCandidatesString = ""

	def _shouldSuppressTypedEcho(self, ch: str) -> bool:
		# Keep this local to actual Chinese IME composition / candidate sessions
		# so that normal typing echo outside Chinese input remains untouched.
		if self._state.isImeSessionFinished and not self._currentCompositionString:
			return False
		languageID = NVDAHelper.lastLanguageID
		if languageID is None or (languageID & PRIMARY_LANGUAGE_MASK) != LANG_CHINESE:
			return False
		# Suppress only raw ASCII keystrokes that commonly leak through as pinyin /
		# typing echo during composition. Do not suppress committed CJK text.
		return ch.isascii() and (ch.isalpha() or ch in (" ", "'", "\b"))

	def _isLikelyModernImeTypedCharacterTarget(self, obj: NVDAObject, ch: str) -> bool:
		if not isinstance(obj, UIA):
			return False
		if self._uia.isModernImeProcess(obj):
			return True
		languageID = NVDAHelper.lastLanguageID
		if languageID is None or (languageID & PRIMARY_LANGUAGE_MASK) != LANG_CHINESE:
			return False
		if not ch.isascii():
			return False
		# Stale candidate UIA objects can lose enough state that process detection
		# fails, while still arriving as typedCharacter targets. Limit this fallback
		# to active Chinese IME contexts and candidate-like UIA object types.
		return type(obj).__name__ in {"ListItem", "List"}

	def _tryRedirectTypedCharacterToRealFocus(self, obj: NVDAObject, ch: str) -> bool:
		if not self._isLikelyModernImeTypedCharacterTarget(obj, ch):
			return False
		try:
			realFocus = api.getDesktopObject().objectWithFocus()
		except Exception:
			return False
		if not realFocus or realFocus == obj:
			return False
		if self._isLikelyModernImeTypedCharacterTarget(realFocus, ch):
			return False
		try:
			if not api.setFocusObject(realFocus):
				return False
		except Exception:
			log.debugWarning(
				"IME_EXP: Failed to restore real focus before replaying typedCharacter",
				exc_info=True,
			)
			return False
		log.debug(
			f"IME_EXP: Redirecting typedCharacter from IME UIA object to real focus: {ch!r}"
		)
		eventHandler.executeEvent("typedCharacter", realFocus, ch=ch)
		return True

	def event_typedCharacter(self, obj: NVDAObject, nextHandler: Callable[[], None], ch: str) -> None:
		if self._tryRedirectTypedCharacterToRealFocus(obj, ch):
			return
		if self._shouldSuppressTypedEcho(ch):
			log.debug(f"IME_EXP: Suppressing typedCharacter during IME session: {ch!r}")
			return
		try:
			nextHandler()
		except COMError:
			if self._isLikelyModernImeTypedCharacterTarget(obj, ch):
				log.debugWarning(
					"IME_EXP: Suppressed COMError in typedCharacter for unavailable IME UIA object",
					exc_info=True,
				)
				return
			raise

	def event_foreground(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isModernImeProcess(obj) and not self._state.isImeSessionFinished:
			return
		if self._shouldMuteReturnTransition:
			log.debug(f"IME_EXP: Muting return foreground on {obj.name}")
			return
		if self._state.isMicrosoftPinyin and not self._state.isImeSessionFinished:
			log.debug(f"IME_EXP: Suppressing foreground during active IME session on {obj.name}")
			return
		nextHandler()

	def event_focusEntered(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isModernImeProcess(obj) and not self._state.isImeSessionFinished:
			return
		if self._shouldMuteReturnTransition:
			return
		try:
			nextHandler()
		except TypeError:
			log.debug("IME_EXP: Suppressed TypeError in focusEntered (UIA element not ready)", exc_info=True)

	def event_gainFocus(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isModernImeProcess(obj) and not self._state.isImeSessionFinished:
			return
		if self._shouldMuteReturnTransition:
			log.debug(f"IME_EXP: Muting return gainFocus on {obj.name}.")
			return
		if self._uia.isMicrosoftPinyinFromUia and isinstance(obj, UIA):
			self._uia.isMicrosoftPinyinFromUia = False
		else:
			nextHandler()

	def event_UIA_window_windowOpen(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isImeCandidateWindow(obj):
			self._state.isMicrosoftPinyin = True
			self._state.startSession()
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
				log.debugWarning("IME_EXP: Error processing modern IME window")
			return
		try:
			nextHandler()
		except TypeError:
			log.debugWarning("IME_EXP: Suppressed TypeError in windowOpen (UIA element not ready)")

	def event_UIA_elementSelected(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self._uia.isModernImeProcess(obj):
			try:
				if isinstance(obj, CandidateItem):
					firstChild = obj.firstChild
					lastChild = obj.lastChild
					if firstChild and lastChild:
						self._uia.isMicrosoftPinyinFromUia = True
						self._state.isMicrosoftPinyin = True
						self.handleInputCandidateListUpdate(lastChild.name, int(firstChild.name) - 1, "ms")
						self._setNavigatorObject(obj)
			except Exception:
				pass
			return
		nextHandler()

	def event_nameChange(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		try:
			if (
				self._state.isMicrosoftPinyin
				and obj.role == controlTypes.Role.STATICTEXT
				and obj.windowClassName == "Windows.UI.Core.CoreWindow"
				and isinstance(obj.parent, CandidateItem)
			):
				previous = obj.previous
				if previous and previous.name:
					self._state.recordCandidateSelection(int(previous.name), obj.name)
		except Exception:
			pass
		try:
			nextHandler()
		except TypeError:
			log.debugWarning("IME_EXP: Suppressed TypeError in nameChange (UIA element not ready)")

	@property
	def _inputConversionModeMessages(self) -> dict[int, tuple[str, str]]:
		return {
			1: (
				# Translators: The message spoken when IME switches to Chinese input mode.
				_("Chinese"),
				# Translators: The message spoken when IME switches to English input mode.
				_("English"),
			),
			8: (
				# Translators: The message spoken when IME switches to full-width character mode.
				_("Full shape"),
				# Translators: The message spoken when IME switches to half-width character mode.
				_("Half shape"),
			),
			1024: (
				# Translators: The message spoken when IME switches to Chinese punctuation mode.
				_("Chinese punctuation"),
				# Translators: The message spoken when IME switches to English punctuation mode.
				_("English punctuation"),
			),
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
		self._refreshNonTrackedDedupBoundary()
		update = self._state.processCandidateUpdate(
			candidatesString, selectionIndex, self._currentCompositionString, inputMethod
		)
		if update is None:
			return

		candidate = update.candidate
		pageChanged = candidatesString != self._lastAutoReportCandidatesString
		self._lastAutoReportCandidatesString = candidatesString
		if settings.isAutoReportAllCandidates() and update.isMultiCandidate and pageChanged:
			self.bindGestures(self._entryGestures)
			msg = self._describer.formatAllCandidates(candidatesString, selectionIndex)
			self._speakCharacter(msg, passthrough=False)
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
		self._currentCompositionString = compositionString.strip()
		self._state.startSession()
		speech.clearTypedWordBuffer()
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
			action = self._state.resolveCompositionEnd(
				result,
				inputEventToken=self._lastInputToken,
			)
			if action.awaitMoreResults:
				self._clearIme()
				return
			if action.fallbackToPunc:
				wx.CallLater(40, self._speakPunc)
			elif action.textToSpeak is not None:
				self._speakCharacter(action.textToSpeak)
				# Let NVDA drop the immediate typed-character echo emitted by some IMEs
				# after the committed text has already been spoken.
				speech._suppressSpeakTypedCharacters(len(action.textToSpeak))
		wasMicrosoftPinyin = self._state.isMicrosoftPinyin
		if wasMicrosoftPinyin:
			self._beginMuteTransition()
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

	def _beginMuteTransition(self) -> None:
		"""Start mute transition to suppress redundant focus/foreground events when IME closes."""
		self._shouldMuteReturnTransition = True
		if self._muteTransitionTimer is not None:
			self._muteTransitionTimer.Stop()
		self._muteTransitionTimer = wx.CallLater(
			self._MUTE_TRANSITION_TIMEOUT_MS, self._endMuteTransition
		)

	def _endMuteTransition(self) -> None:
		self._shouldMuteReturnTransition = False
		self._muteTransitionTimer = None

	def _clearIme(self) -> None:
		"""Reset all IME state, navigator object, and gesture bindings."""
		self._state.clear()
		self._currentCompositionString = ""
		self._lastAutoReportCandidatesString = ""
		self._lastNonTrackedInputTime = None
		speech.clearTypedWordBuffer()
		navObj = api.getNavigatorObject()
		if navObj and self._uia.isModernImeProcess(navObj):
			try:
				shouldRestoreNavigator = not navObj.isFocusable
			except COMError:
				log.debugWarning(
					"IME_EXP: Navigator object became unavailable while clearing IME state",
					exc_info=True,
				)
				shouldRestoreNavigator = True
			if shouldRestoreNavigator:
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
			idx = int(chr(keyCode))
			self._state.selectedCandidateIndex = idx
			if self._state.candidateList and 0 < idx <= len(self._state.candidateList):
				raw = self._state.candidateList[idx - 1].replace(" ", "").replace("(", "").replace(")", "")
				if raw:
					self._state.selectedCandidate = raw
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
