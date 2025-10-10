# -*- coding: UTF-8 -*-
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022 NVDA Chinese Community Contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

import globalPluginHandler,speech,characterProcessing,unicodedata,time,config,queueHandler,brailleInput,wx,api,textInfos,eventHandler,gui,NVDAHelper, controlTypes,winUser,ui
import winVersion
from logHandler import log
from NVDAObjects.UIA import UIA
from NVDAObjects.behaviors import CandidateItem
from keyboardHandler import KeyboardInputGesture
from buildVersion import version_year
role = controlTypes.Role if version_year>=2022 else controlTypes.role.Role

confspec= {
  "autoReportAllCandidates": "boolean(default=False)",
  "candidateCharacterDescription": "integer(default=2)",
  "reportCandidateBeforeDescription": "integer(default=2)",
  "selectedLeftOrRight": "integer(default=0)",
  "reportCompositionStringChanges": "boolean(default=True)",
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
		"kb:leftArrow": "pressKey",
		"kb:rightArrow": "pressKey",
		"kb:escape": "pressKey",
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
		NVDAHelper.handleInputConversionModeUpdate=self.handleInputConversionModeUpdate

	inputConversionModeMessages={
		1:('中文','英文'),
		8:('全角','半角'),
		1024:('中文标点','英文标点')
	}

	def handleInputConversionModeUpdate(self,oldFlags,newFlags,lcid):
		self.clear_ime()
		for x in range(32):
			x=2**x
			msgs=self.inputConversionModeMessages.get(x)
			if not msgs: continue
			newOn=bool(newFlags&x)
			oldOn=bool(oldFlags&x)
			if newOn!=oldOn:
				if newOn:
					self.speakCharacter(msgs[0],isc=False)
				else:
					self.speakCharacter(msgs[1],isc=False)
				break

	def getFormattedCandidateName(self,number,candidate): pass

	def getFormattedCandidateDescription(self,candidate): pass

	def reportFocus(self): pass

	selectedCandidate=''
	candidateList=[]
	selectedIndex=0
	def handleInputCandidateListUpdate(self,candidatesString,selectionIndex,inputMethod):
		if inputMethod == 'ms' and self.inputEnd: return
		global pt,lastCandidate
		if candidatesString:
			ct=time.time()
			if candidatesString==lastCandidate and ct-pt<0.05: return
			pt=ct
			lastCandidate=candidatesString
			if NVDAHelper.lastLayoutString != self.lastLayoutString:
				self.lastLayoutString=NVDAHelper.lastLayoutString
			self.previousCandadatesString=candidatesString
			isc=True
			if inputMethod=='ms':
				lastCandidate=''
			if '\n' in candidatesString:
				self.candidateList=candidatesString.split('\n')
				candidate=self.candidateList[selectionIndex].replace(" ","")
			else:
				if not self.isms: self.candidateList.append(candidatesString)
				candidate=candidatesString
			candidate=candidate.replace('(','')
			candidate=candidate.replace(')','')
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
			try:
				temp=candidate
				while temp[-1].islower():
					temp=temp[:-1]
				candidateLen=len(temp)
			except:
				self.bindGestures (entryGestures)
				self.speakCharacter(candidate)
				return

			if candidateLen > reportCandidateBeforeDescription: # and unicodedata.category(candidate[reportCandidateBeforeDescription])=='Lo':
				customCandidate=True
			else:
				customCandidate=False
			if candidateLen >= reportCandidateBeforeDescription+1 and customCandidate and not reportCandidateBeforeDescription==6:
				self.bindGestures (entryGestures)
				isc=False
				self.speakCharacter(candidate)
			if candidateLen <= candidateCharacterDescription or candidateCharacterDescription>=5:
				self.bindGestures (entryGestures)
				candidate=self.getDescribedSymbols(candidate)
				self.speakCharacter(candidate,isc=isc)

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

	isSkip=False
	def handleInputCompositionStart(self,compositionString,selectionStart,selectionEnd,isReading):
		self.inputEnd = False
		if self.isSkip:
			self.isSkip=False
			return
		try:
			if self.ms_obj and self.ms_obj.firstChild and self.ms_obj.firstChild.firstChild:
				obj=self.ms_obj.firstChild.firstChild
				if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj, CandidateItem):
					self.ismsf=True
					self.isms=True
					self.handleInputCandidateListUpdate(obj.lastChild.name,0,'ms')
					self.setNavigatorObject(obj)
		except AttributeError as ae:
			log.warning(f"AttributeError in handleInputCompositionStart: {ae}")

	caret_obj=None
	def handleInputCompositionEnd(self,result):
		global pt,lastCandidate
		pt=self.pmsTime=time.time()
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
						while unicodedata.category(ch[-1])!='Lo':
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
					wx.CallLater(40,self.speakPunc)
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

	inputEnd = True
	def clear_ime(self):
		self.inputEnd = True
		global lastCandidate
		if api.getNavigatorObject() and api.getNavigatorObject().windowText=='Microsoft Text Input Application' and (not api.getNavigatorObject().isFocusable): self.setNavigatorObject(api.getFocusObject())
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
			speech.cancelSpeech()
		if len(character)==1 and character.isupper():
			speech.speakTypedCharacters(character)
		else:
			if isp:
				speech.speakText(character, symbolLevel=characterProcessing.SymbolLevel.ALL)
			else:
				speech.speakMessage(character)

	pmsTime=0
	def event_UIA_notification(self, obj, nextHandler, *args, **kwargs):
		if obj.role==role.BUTTON and obj.UIAElement.cachedAutomationID=='NewNoteButton':
			pass
		else:
			nextHandler()

	ismsf=False
	ms_obj=None
	def event_UIA_window_windowOpen(self, obj, nextHandler):
		self.isSkip=True
		try:
			if obj.firstChild and obj.firstChild.firstChild:
				self.ms_obj = obj.firstChild if winVersion.getWinVer().releaseName >= winVersion.WIN11.releaseName else obj
				obj=self.ms_obj.firstChild.firstChild
				if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj, CandidateItem):
					self.ismsf=True
					self.isms=True
					self.handleInputCandidateListUpdate(obj.lastChild.name,0,'ms')
					self.setNavigatorObject(obj)
		except AttributeError as ae:
			log.warning(f"AttributeError in event_UIA_window_windowOpen: {ae}")
		except Exception as e:
			log.warning(f"Exception in event_UIA_window_windowOpen: {e}")
		finally:
			nextHandler()

	def event_UIA_elementSelected(self, obj, nextHandler):
		try:
			if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj, CandidateItem):
				self.ismsf=True
				self.isms=True
				self.handleInputCandidateListUpdate(obj.lastChild.name,int(obj.firstChild.name)-1,'ms')
				self.setNavigatorObject(obj)
		except AttributeError as ae:
			log.warning(f"AttributeError in event_UIA_elementSelected: {ae}")
		except Exception as e:
			log.warning(f"Exception in event_UIA_elementSelected: {e}")
		finally:
			nextHandler()

	msCandidateDict={}
	def event_nameChange(self,obj,nextHandler):
		try:
			if obj.windowClassName == "Windows.UI.Core.CoreWindow" and isinstance(obj.parent, CandidateItem) and obj.role==role.STATICTEXT and self.isms:
				self.msCandidateDict[int(obj.previous.name)]=obj.name
		except AttributeError as ae:
			log.warning(f"AttributeError in event_nameChange: {ae}")
		except Exception as e:
			log.warning(f"Exception in event_nameChange: {e}")
		finally:
			nextHandler()

	old_text=''
	old_p= 0

	def event_caret(self, obj, nextHandler):
		self.caret_obj=obj
		nextHandler()

	isms=False
	issg=False
	def event_gainFocus(self, obj, nextHandler):
		if self.ismsf and isinstance(obj, UIA):
			self.ismsf=False
		else:
			nextHandler()

	def script_pressKeyUp(self,gesture):
		KeyboardInputGesture.fromName("uparrow").send()

	def script_pressKeyDown(self,gesture):
		KeyboardInputGesture.fromName("downarrow").send()

	lastLayoutString=''
	def script_pressKey(self,gesture):
		keyCode=gesture.vkCode
		if keyCode >=49 and keyCode <=57:
			self.selectedIndex=int(chr(keyCode))
		elif keyCode==27:
			self.clear_ime()
		if NVDAHelper.lastLayoutString != self.lastLayoutString:
				self.lastLayoutString=NVDAHelper.lastLayoutString
				self.clear_ime()
				wx.CallAfter(winUser.keybd_event,keyCode, 0, 1, 0)
				wx.CallAfter(winUser.keybd_event,keyCode, 0, 3, 0)
				return
		if NVDAHelper.lastLanguageID==2052:
			gesture.send()
		else:
			self.clear_ime()
			wx.CallAfter(winUser.keybd_event,keyCode, 0, 1, 0)
			wx.CallAfter(winUser.keybd_event,keyCode, 0, 3, 0)

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

	def setNavigatorObject(self, obj):
		if config.conf["reviewCursor"]["followFocus"]:
			api.setNavigatorObject(obj)
