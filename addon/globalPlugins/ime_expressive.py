# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
from tones import beep
import globalPluginHandler,speech,characterProcessing,unicodedata,time,config,queueHandler,brailleInput,wx,api,textInfos,eventHandler,gui,NVDAHelper, controlTypes
from NVDAObjects.UIA import UIA
from NVDAObjects.behaviors import CandidateItem
from keyboardHandler import KeyboardInputGesture
from versionInfo import version_year
role = controlTypes.Role if version_year>=2022 else controlTypes.role.Role

confspec= {
  "autoReportAllCandidates": "boolean(default=False)",
  "candidateCharacterDescription": "integer(default=2)",
  "reportCandidateBeforeDescription": "integer(default=2)",
  "selectedLeftOrRight": "integer(default=0)",
  "reportCompositionStringChanges": "boolean(default=True)"
}
config.conf.spec["inputExpressive"] = confspec

pt=0
lastCandidate=''

autoReportAllCandidates=config.conf["inputExpressive"]["autoReportAllCandidates"]
candidateCharacterDescription=config.conf["inputExpressive"]["candidateCharacterDescription"]
reportCandidateBeforeDescription=config.conf["inputExpressive"]["reportCandidateBeforeDescription"]
selectedLeftOrRight=config.conf["inputExpressive"]["selectedLeftOrRight"]
reportCompositionStringChanges=config.conf["inputExpressive"]["reportCompositionStringChanges"]

entryGestures = {
		"kb:upArrow": "pressKey",
		"kb:downArrow": "pressKey",
		"kb:nvda+s": "pressKeyUp",
		"kb:nvda+f": "pressKeyDown",
}

if selectedLeftOrRight==1:
	entryGestures["kb:["] = "selectLeft"
	entryGestures["kb:]"] = "selectRight"
elif selectedLeftOrRight==2:
	entryGestures["kb:,"] = "selectLeft"
	entryGestures["kb:."] = "selectRight"
elif selectedLeftOrRight==3:
	entryGestures["kb:pageUp"] = "selectLeft"
	entryGestures["kb:pageDown"] = "selectRight"

for keyboardKey in range(1, 10):
		entryGestures[f"kb:{keyboardKey}"] = "pressKey"

autoReportAllCandidates_checkBox = None
candidateCharacterDescription_comboBox = None
reportCandidateBeforeDescription_comboBox = None
selectedLeftOrRight_comboBox = None
reportCompositionStringChanges_checkBox = None

def makeSettings(self, settingsSizer):
		global autoReportAllCandidates_checkBox, candidateCharacterDescription_comboBox, reportCandidateBeforeDescription_comboBox, selectedLeftOrRight_comboBox, reportCompositionStringChanges_checkBox
		settingsSizerHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		autoReportAllCandidates_checkBox = settingsSizerHelper.addItem(wx.CheckBox(self, label = _("自动朗读所有候选项")))
		autoReportAllCandidates_checkBox.SetValue(config.conf["inputExpressive"]["autoReportAllCandidates"])

		candidateCharacterDescription_comboBox = settingsSizerHelper.addLabeledControl(_('输入法解释方式'), wx.Choice, choices = ['不解释', '单字解释', '双字解释', '三字解释', '四字解释', '全解释'])
		candidateCharacterDescription_comboBox.SetSelection (config.conf["inputExpressive"]["candidateCharacterDescription"])

		reportCandidateBeforeDescription_comboBox = settingsSizerHelper.addLabeledControl(_('解释前先朗读候选项'), wx.Choice, choices = ['从1个字开始', '从2个字开始', '从3个字开始', '从4个字开始', '从5个字开始', '从6个字开始', '不朗读'])
		reportCandidateBeforeDescription_comboBox.SetSelection (config.conf["inputExpressive"]["reportCandidateBeforeDescription"])

		selectedLeftOrRight_comboBox = settingsSizerHelper.addLabeledControl(_('以词定字按键'), wx.Choice, choices = ['无', '左 / 右方括号', '逗号 / 句号', '上 / 下翻页'])
		selectedLeftOrRight_comboBox.SetSelection (config.conf["inputExpressive"]["selectedLeftOrRight"])

		reportCompositionStringChanges_checkBox = settingsSizerHelper.addItem(wx.CheckBox(self, label = _("读出上屏内容")))
		reportCompositionStringChanges_checkBox.SetValue(config.conf["inputExpressive"]["reportCompositionStringChanges"])
gui.settingsDialogs.InputCompositionPanel.makeSettings=makeSettings

def onSave(self):
		global autoReportAllCandidates, candidateCharacterDescription, reportCandidateBeforeDescription, selectedLeftOrRight, reportCompositionStringChanges, entryGestures
		config.conf["inputExpressive"]["autoReportAllCandidates"]=autoReportAllCandidates=autoReportAllCandidates_checkBox.IsChecked()
		config.conf["inputExpressive"]["candidateCharacterDescription"]=candidateCharacterDescription=candidateCharacterDescription_comboBox.GetSelection()
		config.conf["inputExpressive"]["reportCandidateBeforeDescription"]=reportCandidateBeforeDescription=reportCandidateBeforeDescription_comboBox.GetSelection()
		config.conf["inputExpressive"]["selectedLeftOrRight"]=selectedLeftOrRight=selectedLeftOrRight_comboBox.GetSelection()
		config.conf["inputExpressive"]["reportCompositionStringChanges"]=reportCompositionStringChanges=reportCompositionStringChanges_checkBox.IsChecked()
		if selectedLeftOrRight==1:
			[entryGestures.pop(key, None) for key in ['kb:,', 'kb:.', 'kb:PageUp', 'kb:pageDown']]
			entryGestures["kb:["] = "selectLeft"
			entryGestures["kb:]"] = "selectRight"
		elif selectedLeftOrRight==2:
			[entryGestures.pop(key, None) for key in ['kb:[', 'kb:]', 'kb:PageUp', 'kb:pageDown']]
			entryGestures["kb:,"] = "selectLeft"
			entryGestures["kb:."] = "selectRight"
		elif selectedLeftOrRight==3:
			[entryGestures.pop(key, None) for key in ['kb:[', 'kb:]', 'kb:,', 'kb:.']]
			entryGestures["kb:pageUp"] = "selectLeft"
			entryGestures["kb:pageDown"] = "selectRight"
		else:
			[entryGestures.pop(key, None) for key in ['kb:,', 'kb:.', 'kb:PageUp', 'kb:pageDown', 'kb:[', 'kb:]']]
gui.settingsDialogs.InputCompositionPanel.onSave=onSave

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = "输入法朗读体验优化"

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		CandidateItem.getFormattedCandidateName=self.getFormattedCandidateName
		CandidateItem.getFormattedCandidateDescription=self.getFormattedCandidateDescription
		CandidateItem.reportFocus=self.reportFocus
		NVDAHelper.handleInputCandidateListUpdate=self.handleInputCandidateListUpdate
		NVDAHelper.handleInputCompositionStart=self.handleInputCompositionStart
		NVDAHelper.handleInputCompositionEnd=self.handleInputCompositionEnd

	def getFormattedCandidateName(self,number,candidate): pass

	def getFormattedCandidateDescription(self,candidate): pass

	def reportFocus(self): pass

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
				candidate=self.candidateList[selectionIndex].replace(" ","")
			else:
				if not self.isms: self.candidateList.append(candidatesString)
				candidate=candidatesString
			self.selectedCandidate=candidate
			self.issg=True

			if autoReportAllCandidates:
				self.bindGestures (entryGestures)
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
			customCandidate=True
			if len(candidate) > reportCandidateBeforeDescription and unicodedata.category(candidate[reportCandidateBeforeDescription])=='Lo':
				customCandidate=True
			else:
				customCandidate=False
			if len(candidate) >= reportCandidateBeforeDescription+1 and customCandidate and not reportCandidateBeforeDescription==6:
				self.bindGestures (entryGestures)
				isc=False
				self.speakCharacter(candidate)
			if len(candidate) <= candidateCharacterDescription or candidateCharacterDescription>=5:
				self.bindGestures (entryGestures)
				candidate=self.getDescribedSymbols(candidate)
				self.speakCharacter(candidate,isc=isc)
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

	def handleInputCompositionStart(self,compositionString,selectionStart,selectionEnd,isReading): pass

	caret_obj=None
	def handleInputCompositionEnd(self,result):
		global pt,lastCandidate
		pt=self.pmsTime=time.time()
		if self.caret_obj and self.caret_obj.appModule.appName=='qq' and self.caret_obj.role==role.EDITABLETEXT:
			oldSpeechMode = speech.getState().speechMode
			speech.setSpeechMode(speech.SpeechMode.off)
			eventHandler.executeEvent("gainFocus",self.caret_obj)
			speech.setSpeechMode(oldSpeechMode)

		if reportCompositionStringChanges:
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
		if obj.role==role.BUTTON and obj.UIAElement.cachedAutomationID=='NewNoteButton':
			pass
		else:
			nextHandler()

	def event_UIA_elementSelected(self, obj, nextHandler):
		ct=time.time()
		if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj, CandidateItem) and ct-self.pmsTime>0.2:
			self.isms=True
			self.handleInputCandidateListUpdate(obj.lastChild.name,int(obj.firstChild.name)-1,'ms')
		else:
			nextHandler()

	msCandidateDict={}
	def event_nameChange(self,obj,nextHandler):
		if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj.parent, CandidateItem) and obj.role==role.STATICTEXT and self.isms:
			self.msCandidateDict[int(obj.previous.name)]=obj.name
		else:
			nextHandler()

	old_text=''
	old_p= 0

	def event_caret(self, obj, nextHandler):
		self.caret_obj=obj
		nextHandler()

	def event_textChange1(self, obj, nextHandler):
		if isinstance(obj, UIA) and not self.isms and not self.issg and (obj.role==role.EDITABLETEXT or obj.role==role.DOCUMENT):
			self.checkCharacter(obj)
		else:
			nextHandler()

	def event_typedCharacter1(self, obj, nextHandler):
		if not self.isms and not self.issg:
			if isinstance(obj, UIA)  and (obj.role==role.EDITABLETEXT or obj.role==role.DOCUMENT):
				self.checkCharacter(obj)
			else:
				nextHandler()

	isms=False
	issg=False
	def event_gainFocus1(self, obj, nextHandler):
		if isinstance(obj, UIA) and (self.isms or self.issg) and (obj.role==role.EDITABLETEXT or obj.role==role.DOCUMENT):
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