# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

import appModuleHandler, speech, api
from keyboardHandler import KeyboardInputGesture

class AppModule(appModuleHandler.AppModule):

	def script_pressKey(self,gesture):
		gesture.send()
		newObject=api.getFocusObject()
		speech.speakObject(newObject)

	__gestures = {
"kb:tab":"pressKey",
"kb:shift+tab":"pressKey",
"kb:upArrow":"pressKey",
"kb:downArrow":"pressKey",
"kb:leftArrow":"pressKey",
"kb:rightArrow":"pressKey",
"kb:space":"pressKey",
}