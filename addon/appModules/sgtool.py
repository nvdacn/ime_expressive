# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

import appModuleHandler, speech, api
from keyboardHandler import KeyboardInputGesture

class AppModule(appModuleHandler.AppModule):

	def script_tabKey(self,gesture):
		KeyboardInputGesture.fromName("tab").send()
		newObject=api.getFocusObject()
		speech.speakObject(newObject)

	def script_shiftTabKey(self,gesture):
		KeyboardInputGesture.fromName("shift+tab").send()
		newObject=api.getFocusObject()
		speech.speakObject(newObject)

	def script_upArrowKey(self,gesture):
		KeyboardInputGesture.fromName("upArrow").send()
		newObject=api.getFocusObject()
		speech.speakObject(newObject)

	def script_downArrowKey(self,gesture):
		KeyboardInputGesture.fromName("downArrow").send()
		newObject=api.getFocusObject()
		speech.speakObject(newObject)

	def script_leftArrowKey(self,gesture):
		KeyboardInputGesture.fromName("leftArrow").send()
		newObject=api.getFocusObject()
		speech.speakObject(newObject)

	def script_rightKey(self,gesture):
		KeyboardInputGesture.fromName("rightArrow").send()
		newObject=api.getFocusObject()
		speech.speakObject(newObject)

	def script_spaceKey(self,gesture):
		KeyboardInputGesture.fromName("space").send()
		newObject=api.getFocusObject()
		speech.speakObject(newObject)

	__gestures = {
"kb:tab":"tabKey",
"kb:shift+tab":"shiftTabKey",
"kb:upArrow":"upArrowKey",
"kb:downArrow":"downArrowKey",
"kb:leftArrow":"leftArrowKey",
"kb:rightArrow":"rightArrowKey",
"kb:space":"spaceKey",
}