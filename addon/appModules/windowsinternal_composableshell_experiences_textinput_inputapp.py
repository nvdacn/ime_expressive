# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2017-2022 NV Access Limited, Joseph Lee
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

# The add-on version of this module will extend the one that comes with NVDA Core (2018.3 and later).
# For IME candidate item/UI definition, Flake8 must be told to ignore it.

# Yes, this app module is powered by built-in modern keyboard (TextInputHost) app module
# (formerly WindowsInternal.ComposableShell.Experiences.TextInput.InputApp).
# #70: NVDA Core pull requests are made using the core app module, not alias modules.
from nvdaBuiltin.appModules.windowsinternal_composableshell_experiences_textinput_inputapp import (
	AppModule, ImeCandidateItem, ImeCandidateUI
)
import winVersion
import eventHandler
import UIAHandler
import controlTypes
import api
from logHandler import log
from NVDAObjects.UIA import UIA


# NVDA Core prior to 2022.4 doesn't know about Windows 11 22H2.
# This is a must as parts of the below app module needs to know if this is 22H2 beta (build 22622) or not.
WIN11_22H2 = winVersion.WinVersion(major=10, minor=0, build=22621, releaseName="Windows 11 22H2")


# Built-in modern keyboard app module powers bulk of the below app module class, so inform Mypy.
class AppModule(AppModule):  # type: ignore[no-redef]

	_symbolsGroupSelected: bool = False
	# In Windows 11, clipboard history is seen as a web document.
	# Turn off browse mode by default so clipboard history entry menu items can be announced when tabbed to.
	disableBrowseModeByDefault = True

	def _emojiPanelClosed(self, obj):
		# Move NVDA's focus object to what is actually focused on screen.
		# This is needed in Windows 11 when emoji panel closes.
		eventHandler.queueEvent("gainFocus", obj.objectWithFocus())

	def event_UIA_elementSelected(self, obj, nextHandler):
		# Do not proceed if emoji panel category item is selected when the panel itself is gone.
		# This is the case when closing emoji panel portion in Windows 11.
		if obj.UIAAutomationId.startswith("navigation-menu-item"):
			emojiPanelAncestors = [
				item.appModule for item in api.getFocusAncestors()
				if item.appModule == self
			]
			# Focus object location can be None sometimes.
			focusLocation = api.getFocusObject().location
			# System focus restored.
			if not len(emojiPanelAncestors):
				return
			# NVDA is stuck in a nonexistent edit field.
			elif focusLocation is not None and not any(focusLocation):
				self._emojiPanelClosed(obj)
				return
		# In Windows 11, candidate panel houses candidate items, not the prediction window.
		if obj.UIAAutomationId == "TEMPLATE_PART_CandidatePanel":
			obj = obj.firstChild
		# Logic for IME candidate items is handled all within its own object
		# Therefore pass these events straight on.
		# But not in Windows 11 because it also fires gain focus event.
		if isinstance(obj, ImeCandidateItem):
			return nextHandler() if winVersion.getWinVer() < winVersion.WIN11 else None
		# The following is applicable on Windows 10 and Server 2022.
		if winVersion.getWinVer() < winVersion.WIN11:
			# If emoji/kaomoji/symbols group item gets selected, just tell NVDA to treat it as the new navigator object
			# (for presentational purposes) and move on.
			if obj.parent.UIAAutomationId == "TEMPLATE_PART_Groups_ListView":
				api.setNavigatorObject(obj)
				if obj.positionInfo["indexInGroup"] != 1:
					# Symbols group flag must be set if and only if emoji panel is active,
					# as UIA item selected event is fired just before emoji panel opens
					# when opening the panel after closing it for a while.
					self._symbolsGroupSelected = True
				return
			if (
				# When changing categories (emoji, kaomoji, symbols),
				# category items are selected when in fact they have no text labels.
				obj.parent.UIAAutomationId == "TEMPLATE_PART_Sets_ListView"
				# Specifically to suppress skin tone modifiers from being announced after an emoji group was selected.
				or self._symbolsGroupSelected
			):
				return
		# NVDA Core takes care of the rest.
		super().event_UIA_elementSelected(obj, nextHandler)

	# Register modern keyboard interface elements with local event handler group.
	def _windowOpenEventInternalEventHandlerGroupRegistration(self, firstChild):
		# Gather elements to be registered inside a list so they can be registered in one go.
		localEventHandlerElements = [firstChild]
		# For dictation, add elements manually so name change event can be handled.
		# Object hierarchy is different in voice typing (Windows 11).
		if firstChild.UIAAutomationId in ("DictationMicrophoneButton", "FloatyTip"):
			if firstChild.UIAAutomationId == "DictationMicrophoneButton":
				element = firstChild.next
			else:
				element = firstChild.firstChild.firstChild
			while element.next is not None:
				localEventHandlerElements.append(element)
				element = element.next
		# Don't forget to add actual candidate item element so name change event can be handled
		# (mostly for hardware keyboard input suggestions).
		if isinstance(firstChild, ImeCandidateUI):
			imeCandidateItem = firstChild.firstChild.firstChild
			# In Windows 11, an extra element is located between candidate UI window and items themselves.
			if winVersion.getWinVer() >= winVersion.WIN11:
				# For some odd reason, suggested text is the last element.
				imeCandidateItem = imeCandidateItem.lastChild
			localEventHandlerElements.append(imeCandidateItem)
		for element in localEventHandlerElements:
			UIAHandler.handler.removeEventHandlerGroup(element.UIAElement, UIAHandler.handler.localEventHandlerGroup)
			UIAHandler.handler.addEventHandlerGroup(element.UIAElement, UIAHandler.handler.localEventHandlerGroup)

	def event_UIA_window_windowOpen(self, obj, nextHandler):
		# Ask NVDA to respond to UIA events coming from modern keyboard interface.
		# Focus change event will not work, as it'll cause focus to be lost when the panel closes.
		# This is more so on Windows 10.
		firstChild = obj.firstChild
		# Sometimes window open event is raised when the input panel closes.
		if firstChild is None:
			return
		# Log which modern keyboard header is active.
		if log.isEnabledFor(log.DEBUG):
			log.debug(
				"winapps: Automation Id for currently opened modern keyboard feature "
				f"is {firstChild.UIAAutomationId}"
			)
		# Originally part of this method, split into an internal function to reduce complexity.
		# However, in Windows 11, combined emoji panel and clipboard history moves system focus to itself.
		# Therefore there is no need to add UIA elements to local event handler group.
		try:
			if firstChild.UIAAutomationId != "Windows.Shell.InputApp.FloatingSuggestionUI":
				self._windowOpenEventInternalEventHandlerGroupRegistration(firstChild)
		except NotImplementedError:
			pass
		self._symbolsGroupSelected = False
		# Build 25115 uses modern keyboard interface to display Suggested Actions
		# if data such as phone number is copied to the clipboard.
		# Because keyboard interaction is not possible, just report suggested actions.
		# In build 25145 and later (or possibly earlier builds), Automation Id is empty.
		# Automation Id has changed yet again in build 25158 (argh).
		# Suggested Actions was backported to Windows 11 22H2 beta (build 22622).
		suggestedActionsIds = [
			"Windows.Shell.InputApp.SmartActionsUX"  # Build 25158 and 22622.436 and later
		]
		# Better to use build 22621 as base build since beta increments it by 1.
		if firstChild.UIAAutomationId in suggestedActionsIds and winVersion.getWinVer() > WIN11_22H2:
			import ui
			suggestedActions = []
			# Build 25158 changes the UI once again, suggested actions is now a grouping, backported to 22622.
			for suggestedAction in firstChild.children:
				if suggestedAction.name:
					suggestedActions.append(suggestedAction.name)
			ui.message("; ".join(suggestedActions))
		# NVDA Core takes care of the rest.
		super().event_UIA_window_windowOpen(obj, nextHandler)

	# Only on Windows 10 and Server 2022.
	if winVersion.getWinVer() < winVersion.WIN11:
		def event_nameChange(self, obj, nextHandler):
			if (
				# Forget it if there is no Automation Id and class name set.
				(obj.UIAElement.cachedClassName == "" and obj.UIAAutomationId == "")
				# Clipboard entries fire name change event when opened.
				or (obj.UIAElement.cachedClassName == "TextBlock" and obj.UIAAutomationId == "")
				# Ignore useless clipboard entry scrolling announcements.
				or obj.UIAAutomationId == "VerticalScrollBar"
			):
				return
			self._symbolsGroupSelected = False
			# NVDA Core takes care of the rest.
			super().event_nameChange(obj, nextHandler)

	def event_gainFocus(self, obj, nextHandler):
		# Focus gets stuck in Modern keyboard when clipboard history closes in Windows 11.
		if obj.parent.childCount == 0:
			self._emojiPanelClosed(obj)
		nextHandler()

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		# Recognize more candidate UI and item elements in Windows 11.
		# Return after checking each item so candidate UI and items from Windows 10 can be recognized.
		if isinstance(obj, UIA):
			# Candidate item.
			if obj.role == controlTypes.Role.LISTITEM and obj.parent.UIAAutomationId == "TEMPLATE_PART_CandidatePanel":
				clsList.insert(0, ImeCandidateItem)
				return
			# Candidate UI.
			elif (
				obj.role in (controlTypes.Role.LIST, controlTypes.Role.POPUPMENU)
				and obj.UIAAutomationId in ("TEMPLATE_PART_CandidatePanel", "IME_Prediction_Window")
			):
				clsList.insert(0, ImeCandidateUI)
				return
		# NVDA Core takes care of the rest.
		super().chooseNVDAObjectOverlayClasses(obj, clsList)
