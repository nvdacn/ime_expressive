# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

import globalPluginHandler,speech,characterProcessing,unicodedata,keyboardHandler,time,config,queueHandler,ui,brailleInput,wx,api,textInfos,eventHandler, gui
import NVDAHelper
from NVDAObjects.UIA import UIA
from NVDAObjects.behaviors import CandidateItem
from keyboardHandler import KeyboardInputGesture
from . import settings
from gui.settingsDialogs import NVDASettingsDialog
from gui.settingsDialogs import InputCompositionPanel
from scriptHandler import script

pt=0
lastCandidate=''

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		CandidateItem.getFormattedCandidateName=self.getFormattedCandidateName
		CandidateItem.getFormattedCandidateDescription=self.getFormattedCandidateDescription
		CandidateItem.reportFocus=self.reportFocus
		NVDAHelper.handleInputCandidateListUpdate=self.handleInputCandidateListUpdate
		NVDAHelper.handleInputCompositionStart=self.handleInputCompositionStart
		NVDAHelper.handleInputCompositionEnd=self.handleInputCompositionEnd
		# 判断移除原有的输入法设置面板
		if InputCompositionPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(InputCompositionPanel)
		# 注册设置面板
		NVDASettingsDialog.categoryClasses.append(settings.expressiveInputCompositionPanel)

	def terminate(self):
		super().terminate()
		# 移除设置面板
		NVDASettingsDialog.categoryClasses.remove(settings.expressiveInputCompositionPanel)

	# 打开输入设置面板的手势，覆盖掉NVDA原有定义
	@script(
	description=_("Shows NVDA's input composition settings"),
	category=_("Configuration")
	)
	def script_activateInputCompositionDialog(self, gesture):
		gui.mainFrame._popupSettingsDialog (NVDASettingsDialog, settings.expressiveInputCompositionPanel)

	def getFormattedCandidateName(self,number,candidate):
		pass

	def getFormattedCandidateDescription(self,candidate):
		pass

	def reportFocus(self):
		pass

	entryGestures = {
		"kb:upArrow": "pressKey",
		"kb:downArrow": "pressKey",
		"kb:nvda+s": "pressKeyUp",
		"kb:nvda+f": "pressKeyDown",
}

	if config.conf["ime_expressive"]["selectedLeftOrRight"]==1:
		entryGestures["kb:["] = "selectLeft"
		entryGestures["kb:]"] = "selectRight"
	elif config.conf["ime_expressive"]["selectedLeftOrRight"]==2:
		entryGestures["kb:,"] = "selectLeft"
		entryGestures["kb:."] = "selectRight"
	elif config.conf["ime_expressive"]["selectedLeftOrRight"]==3:
		entryGestures["kb:pageUp"] = "selectLeft"
		entryGestures["kb:pageDown"] = "selectRight"

# Maps all 9 numeric keyboard keys to the apropriate gesture.
# It was done this way to avoid code repetition.
	for keyboardKey in range(1, 10):
		entryGestures[f'kb:{keyboardKey}'] = 'pressKey'

	selectedCandidate=''
	candidateList=[]
	selectedIndex=0
	def handleInputCandidateListUpdate(self,candidatesString,selectionIndex,inputMethod):
		global pt,lastCandidate
		ct=time.time()
		if candidatesString and ct-pt>0.05:
			isc=True
			if inputMethod=='ms':
				lastCandidate=''
			else:
				lastCandidate=candidatesString 
			if '\n' in candidatesString:
				self.candidateList=candidatesString.split('\n')
				candidate=self.candidateList[selectionIndex]
			else:
				if not self.isms: self.candidateList.append(candidatesString)
				candidate=candidatesString
			self.selectedCandidate=candidate
			self.issg=True
			if config.conf["ime_expressive"]["autoReportAllCandidates"]:
				self.bindGestures (self.entryGestures)
				t=''
				if '\n' in candidatesString:
					l=candidatesString.split('\n')
					c=0
					for i in l:
						c+=1
						t+=i+str(c)+'； '
					self.speakCharacter(t,isp=False)
					return
				else:
					self.speakCharacter(candidatesString+str(selectionIndex+1))
					return
			if len(candidate) > config.conf["ime_expressive"]["reportCandidateBeforeDescription"]+1 and not config.conf["ime_expressive"]["reportCandidateBeforeDescription"]==6:
				self.bindGestures (self.entryGestures)
				self.speakCharacter(candidate)
			if len(candidate) <= config.conf["ime_expressive"]["candidateCharacterDescription"]+1 or config.conf["ime_expressive"]["candidateCharacterDescription"]>=5:
				self.bindGestures (self.entryGestures)
				candidate=self.getDescribedSymbols(candidate)
				self.speakCharacter(candidate,isc=False)
			pt=ct

	def getDescribedSymbols(self,candidate):
				describedSymbols=[]
				for symbol in candidate:
					try:
						symbolDescriptions=characterProcessing.getCharacterDescription('zh_CN',symbol) or []
					except TypeError:
						symbolDescriptions=[]
					if len(symbolDescriptions)>=1:
						description=symbolDescriptions[0]
						if description.startswith('(') and description.endswith(')'):
							describedSymbols.append(description[1:-1])
						else:
							describedSymbols.append(_(u"{symbol} as in {description}").format(symbol=symbol,description=description))
					else:
						describedSymbols.append(symbol)
				candidate=' '.join(describedSymbols)
				return candidate

	def handleInputCompositionStart(self,compositionString,selectionStart,selectionEnd,isReading):
		pass

	def handleInputCompositionEnd(self,result):
		global pt,lastCandidate
		pt=self.pmsTime=time.time()
		if config.conf["ime_expressive"]["reportCompositionStringChanges"]:
			if result:
				if not lastCandidate:
					self.speakCharacter(result)
				elif  result in lastCandidate:
					self.speakCharacter(result)
			else:
				if self.selectedIndex>0:
					try:
						if self.msCandidateDict:
							ch=self.msCandidateDict[self.selectedIndex]
						else:
							ch=self.candidateList[self.selectedIndex-1]
						for i in range(len(ch)):
							if ch[-1]=='(' or ch[-1]==')' or ch[-1].islower() or ch[-1].isupper():
								ch=ch[:-1]
						self.speakCharacter(ch)
						self.clear_ime()
						return
					except:
						self.selectedIndex=0
						self.selectedCandidate=''
				if self.selectedCandidate:
					self.speakCharacter(self.selectedCandidate)
				else:
					wx.CallAfter(self.speakPunc)
		self.clear_ime()

	def speakPunc(self,isl=False):
					charInfo=api.getReviewPosition().copy()
					charInfo.expand(textInfos.UNIT_CHARACTER)
					charInfo.collapse()
					charInfo.move(textInfos.UNIT_CHARACTER,-1)
					api.setReviewPosition(charInfo)
					charInfo.expand(textInfos.UNIT_CHARACTER)
					t=charInfo.text
					if t and len(t)==1:
						if unicodedata.category(t)[0] in 'PS':
							self.speakCharacter(t)
						if isl and (t.islower() or t.isupper()):
							self.speakCharacter(t)
					charInfo.collapse()
					charInfo.move(textInfos.UNIT_CHARACTER,1)
					api.setReviewPosition(charInfo)


	def clear_ime(self):
		global lastCandidate
		lastCandidate=''
		self.selectedCandidate=''
		self.selectedIndex=0
		self.candidateList=[]
		self.isms=False
		self.issg=False
		self.msCandidateDict={}
		self.clearGestureBindings ()

	def speakCharacter(self,character,isc=True,isp=True):
		if isc:
			queueHandler.queueFunction(queueHandler.eventQueue,speech.cancelSpeech)
		character=character.replace('(','')
		character=character.replace(')','')
		if len(character)==1 and character.isupper():
			queueHandler.queueFunction(queueHandler.eventQueue,speech.speakTypedCharacters,character)
		else:
			if isp:
				queueHandler.queueFunction(queueHandler.eventQueue,speech.speakText,character, symbolLevel=characterProcessing.SymbolLevel.ALL)
			else:
				queueHandler.queueFunction(queueHandler.eventQueue,speech.speakMessage,character)

	pmsTime=0
	def event_UIA_notification(self, obj, nextHandler):
		if obj.role==9 and obj.UIAElement.cachedAutomationID=='NewNoteButton':
			pass
		else:
			nextHandler()

	def event_UIA_elementSelected(self, obj, nextHandler):
		ct=time.time()
		if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj, CandidateItem) and ct-self.pmsTime>0.2:
			self.isms=True
			if config.conf["ime_expressive"]["autoReportAllCandidates"]:
				self.bindGestures (self.entryGestures)
				o=obj.parent.firstChild
				t=''
				while o.role==15:
					t+=o.lastChild.name+o.firstChild.name+'； '
					o=o.next
				self.speakCharacter(t,isp=False)
			else:
				self.handleInputCandidateListUpdate(obj.lastChild.name,int(obj.firstChild.name)-1,'ms')
		else:
			nextHandler()

	msCandidateDict={}
	def event_nameChange(self,obj,nextHandler):
		if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj.parent, CandidateItem) and obj.role==7 and self.isms:
			self.msCandidateDict[int(obj.previous.name)]=obj.name
		else:
			nextHandler()

	old_text=''
	old_p= 0
	def event_caret(self, obj, nextHandler):
		if obj.appModule.appName=='qq' and obj.role==8: 
			oldSpeechMode = speech.getState().speechMode
			speech.setSpeechMode(speech.SpeechMode.off)
			eventHandler.executeEvent("gainFocus",obj)
			speech.setSpeechMode(oldSpeechMode)
			self.checkCharacter(obj)
		else:
			nextHandler()

	def event_textChange(self, obj, nextHandler):
		if isinstance(obj, UIA) and not self.isms and not self.issg and (obj.role==8 or obj.role==52):
			self.checkCharacter(obj)
		else:
			nextHandler()

	def event_typedCharacter(self, obj, nextHandler):
		if isinstance(obj, UIA) and not self.isms and not self.issg and (obj.role==8 or obj.role==52):
			self.checkCharacter(obj)
		else:
			nextHandler()

	isms=False
	issg=False
	def event_gainFocus(self, obj, nextHandler):
		if isinstance(obj, UIA) and (self.isms or self.issg) and (obj.role==8 or obj.role==52):
			self.handleInputCompositionEnd(result='')
			self.checkCharacter(obj,iss=False)
		else:
			nextHandler()

	def checkCharacter(self,obj,iss=True):
		start=obj.makeTextInfo(textInfos.POSITION_ALL)
		text=start.text
		end = obj.makeTextInfo(textInfos.POSITION_CARET)
		start.setEndPoint(end, "endToStart")
		p= len(start.text)
		if iss:
			if len(self.old_text) < len(text):
				tt=text[self.old_p:p]
				if tt==' ':
					self.speakCharacter('空格')
				elif not speech.isBlank(tt):
					self.speakCharacter(tt)
		self.old_text=text
		self.old_p= p

	def script_pressKeyUp(self,gesture):
		KeyboardInputGesture.fromName("uparrow").send()

	def script_pressKeyDown(self,gesture):
		KeyboardInputGesture.fromName("downarrow").send()

	def script_pressKey(self,gesture):
		keyCode=gesture.vkCode
		if keyCode >=49 and keyCode <=57:
			self.selectedIndex=int(chr(keyCode))
		gesture.send()

	def script_selectLeft(self,gesture):
		if self.selectedCandidate and len(self.selectedCandidate)>1:
			KeyboardInputGesture.fromName("escape").send()
			queueHandler.queueFunction(queueHandler.eventQueue,speech.cancelSpeech)
			wx.CallAfter(brailleInput.BrailleInputHandler.sendChars,self,self.selectedCandidate[0])
			self.clearGestureBindings ()

	def script_selectRight(self,gesture):
		length=len(self.selectedCandidate)
		if self.selectedCandidate and length>1:
			KeyboardInputGesture.fromName("escape").send()
			chList=list(self.selectedCandidate)
			for c in range(length):
				ch=chList.pop()
				if unicodedata.category(ch)=='Lo':
					queueHandler.queueFunction(queueHandler.eventQueue,speech.cancelSpeech)
					wx.CallAfter(brailleInput.BrailleInputHandler.sendChars,self,ch)
					break
			self.clearGestureBindings ()
