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
		state=""
		name=newObject.name if newObject.name else ""
		role=newObject.role.displayString if newObject.role else ""
		accDescription = newObject.description if newObject.description else ""
		if newObject.role in(5, 6): # 5, 6 are equivalents of controlTypes.Role.CHECKBOX, controlTypes.Role.RADIOBUTTON
			state = "已选中" if 32 in newObject.states else "未选中" # 32 is the equivalent of controlTypes.STATE_CHECKED
		speech.speakMessage(name +role +state+accDescription)


	__gestures = {
"kb:tab":"pressKey",
"kb:shift+tab":"pressKey",
"kb:upArrow":"pressKey",
"kb:downArrow":"pressKey",
"kb:leftArrow":"pressKey",
"kb:rightArrow":"pressKey",
"kb:space":"pressKey",
}