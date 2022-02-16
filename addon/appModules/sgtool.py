# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

import appModuleHandler, speech, api, controlTypes, ui
from keyboardHandler import KeyboardInputGesture
import controlTypes

class AppModule(appModuleHandler.AppModule):

	def script_pressKey(self,gesture):
		gesture.send()
		newObject=api.getFocusObject()
		name=newObject.name if newObject.name else ""
		role=controlTypes.roleLabels[newObject.role] if controlTypes.roleLabels[newObject.role] else ""
		accDescription = newObject.description if newObject.description else ""
		state=""
		if newObject.role in(controlTypes.ROLE_CHECKBOX, controlTypes.ROLE_RADIOBUTTON):
			state = "已选中" if controlTypes.STATE_CHECKED in newObject.states else "未选中"
		ui.message(name +role +state+accDescription)
#		speech.speakObject(newObject)

	__gestures = {
"kb:tab":"pressKey",
"kb:shift+tab":"pressKey",
"kb:upArrow":"pressKey",
"kb:downArrow":"pressKey",
"kb:leftArrow":"pressKey",
"kb:rightArrow":"pressKey",
"kb:space":"pressKey",
}