# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022-2026 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

"""Configuration spec and settings panel for the IME Expressive.

Monkey-patches NVDA's InputCompositionPanel to add custom settings.
Widget references are stored on the panel instance (self.imeXxx) following
NVDA's own InputCompositionPanel convention.
"""

from __future__ import annotations

from collections.abc import Callable

import addonHandler
import config
import gui
import wx
from logHandler import log

from .enums import DescriptionMode, ReportThreshold, SelectKeyMode

addonHandler.initTranslation()

CONF_SECTION = "inputExpressive"

confspec: dict[str, str] = {
	"autoReportAllCandidates": "boolean(default=False)",
	"candidateCharacterDescription": "integer(default=2)",
	"reportCandidateBeforeDescription": "integer(default=2)",
	"selectedLeftOrRight": "integer(default=0)",
	"reportCompositionStringChanges": "boolean(default=True)",
}


def initConfig() -> None:
	config.conf.spec[CONF_SECTION] = confspec
	log.debug("IME_EXP: Config spec registered")


def getDescriptionMode() -> DescriptionMode:
	return DescriptionMode(config.conf[CONF_SECTION]["candidateCharacterDescription"])


def getReportThreshold() -> ReportThreshold:
	return ReportThreshold(config.conf[CONF_SECTION]["reportCandidateBeforeDescription"])


def getSelectKeyMode() -> SelectKeyMode:
	return SelectKeyMode(config.conf[CONF_SECTION]["selectedLeftOrRight"])


def isAutoReportAllCandidates() -> bool:
	return config.conf[CONF_SECTION]["autoReportAllCandidates"]


def isReportCompositionStringChanges() -> bool:
	return config.conf[CONF_SECTION]["reportCompositionStringChanges"]


def _makeSettings(self, settingsSizer: wx.Sizer) -> None:
	"""Replacement makeSettings for InputCompositionPanel.

	Stores widget references on self (the panel instance) using imeXxx prefix
	to avoid colliding with NVDA's own widget names.
	"""
	helper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
	self.imeAutoReportCheckBox = helper.addItem(
		wx.CheckBox(
			self,
			label=_(
				# Translators: The label for a checkbox in input composition settings
				# to automatically report all candidates when the candidate window appears.
				"Report all candidates automatically"
			),
		)
	)
	self.imeAutoReportCheckBox.SetValue(config.conf[CONF_SECTION]["autoReportAllCandidates"])
	self.imeDescriptionModeChoice = helper.addLabeledControl(
		_(
			# Translators: The label for a choice in input composition settings
			# configuring how many characters of a candidate should be described.
			"Candidate character description pattern"
		),
		wx.Choice,
		choices=[
			# Translators: A choice indicating character description is disabled.
			_("Off"),
			# Translators: A choice indicating up to 1 character will be described.
			_("Up to 1 character"),
			# Translators: A choice indicating up to 2 characters will be described.
			_("Up to 2 characters"),
			# Translators: A choice indicating up to 3 characters will be described.
			_("Up to 3 characters"),
			# Translators: A choice indicating up to 4 characters will be described.
			_("Up to 4 characters"),
			# Translators: A choice indicating all characters will be described.
			_("All characters"),
		],
	)
	self.imeDescriptionModeChoice.SetSelection(config.conf[CONF_SECTION]["candidateCharacterDescription"])
	self.imeReportThresholdChoice = helper.addLabeledControl(
		_(
			# Translators: The label for a choice in input composition settings
			# configuring whether the candidate name is reported before character descriptions.
			"Report candidate before description"
		),
		wx.Choice,
		choices=[
			# Translators: A choice indicating candidate name is reported for 1 char or more.
			_("For 1 character or more"),
			# Translators: A choice indicating candidate name is reported for 2 chars or more.
			_("For 2 characters or more"),
			# Translators: A choice indicating candidate name is reported for 3 chars or more.
			_("For 3 characters or more"),
			# Translators: A choice indicating candidate name is reported for 4 chars or more.
			_("For 4 characters or more"),
			# Translators: A choice indicating candidate name is reported for 5 chars or more.
			_("For 5 characters or more"),
			# Translators: A choice indicating candidate name is reported for 6 chars or more.
			_("For 6 characters or more"),
			# Translators: A choice indicating candidate name is never reported before description.
			_("Never"),
		],
	)
	self.imeReportThresholdChoice.SetSelection(config.conf[CONF_SECTION]["reportCandidateBeforeDescription"])
	self.imeSelectKeyChoice = helper.addLabeledControl(
		_(
			# Translators: The label for a choice in input composition settings
			# configuring the shortcut for selecting a candidate character.
			"Select candidate character shortcut"
		),
		wx.Choice,
		choices=[
			# Translators: A choice indicating no shortcut is assigned.
			_("None"),
			# Translators: A choice indicating left/right brackets are used as shortcuts.
			_("[ / ]"),
			# Translators: A choice indicating comma/period are used as shortcuts.
			_(", / ."),
			# Translators: A choice indicating PageUp/PageDown are used as shortcuts.
			_("PageUp / PageDown"),
		],
	)
	self.imeSelectKeyChoice.SetSelection(config.conf[CONF_SECTION]["selectedLeftOrRight"])
	self.imeReportCompChangesCheckBox = helper.addItem(
		wx.CheckBox(
			self,
			label=_(
				# Translators: The label for a checkbox in input composition settings
				# to report composition string changes during typing.
				"Report composition string changes"
			),
		)
	)
	self.imeReportCompChangesCheckBox.SetValue(config.conf[CONF_SECTION]["reportCompositionStringChanges"])


def _onSave(self) -> None:
	"""Replacement onSave for InputCompositionPanel."""
	config.conf[CONF_SECTION]["autoReportAllCandidates"] = self.imeAutoReportCheckBox.IsChecked()
	config.conf[CONF_SECTION]["candidateCharacterDescription"] = self.imeDescriptionModeChoice.GetSelection()
	config.conf[CONF_SECTION]["reportCandidateBeforeDescription"] = self.imeReportThresholdChoice.GetSelection()
	config.conf[CONF_SECTION]["selectedLeftOrRight"] = self.imeSelectKeyChoice.GetSelection()
	config.conf[CONF_SECTION]["reportCompositionStringChanges"] = self.imeReportCompChangesCheckBox.IsChecked()
	log.debug("IME_EXP: Settings saved")
	for cb in _saveCallbacks:
		cb()

_saveCallbacks: list[Callable[[], None]] = []
_original_makeSettings = None
_original_onSave = None


def registerSaveCallback(callback: Callable[[], None]) -> None:
	"""Register a callback to be invoked after settings are saved."""
	if callback not in _saveCallbacks:
		_saveCallbacks.append(callback)


def unregisterSaveCallback(callback: Callable[[], None]) -> None:
	"""Unregister a previously registered save callback."""
	if callback in _saveCallbacks:
		_saveCallbacks.remove(callback)


def installSettingsPanel() -> None:
	"""Monkey-patch NVDA's InputCompositionPanel with our custom settings."""
	global _original_makeSettings, _original_onSave
	_original_makeSettings = gui.settingsDialogs.InputCompositionPanel.makeSettings
	_original_onSave = gui.settingsDialogs.InputCompositionPanel.onSave
	gui.settingsDialogs.InputCompositionPanel.makeSettings = _makeSettings
	gui.settingsDialogs.InputCompositionPanel.onSave = _onSave
	log.debug("IME_EXP: Settings panel monkey-patched")


def restoreSettingsPanel() -> None:
	"""Restore the original InputCompositionPanel methods."""
	global _original_makeSettings, _original_onSave
	if _original_makeSettings:
		gui.settingsDialogs.InputCompositionPanel.makeSettings = _original_makeSettings
		_original_makeSettings = None
	if _original_onSave:
		gui.settingsDialogs.InputCompositionPanel.onSave = _original_onSave
		_original_onSave = None
	log.debug("IME_EXP: Settings panel restored")


def buildGestureMap() -> dict[str, str]:
	"""Build the gesture map based on current selectKeyMode setting."""
	gestures: dict[str, str] = {
		"kb:upArrow": "pressKey",
		"kb:downArrow": "pressKey",
		"kb:leftArrow": "pressKey",
		"kb:rightArrow": "pressKey",
		"kb:escape": "pressKey",
		"kb:nvda+s": "pressKeyUp",
		"kb:nvda+f": "pressKeyDown",
	}
	mode = getSelectKeyMode()
	if mode == SelectKeyMode.BRACKETS:
		gestures["kb:["] = "selectLeft"
		gestures["kb:]"] = "selectRight"
	elif mode == SelectKeyMode.COMMA_PERIOD:
		gestures["kb:,"] = "selectLeft"
		gestures["kb:."] = "selectRight"
	elif mode == SelectKeyMode.PAGE_UPDOWN:
		gestures["kb:pageUp"] = "selectLeft"
		gestures["kb:pageDown"] = "selectRight"
	for keyboardKey in range(1, 10):
		gestures[f"kb:{keyboardKey}"] = "pressKey"
	return gestures
