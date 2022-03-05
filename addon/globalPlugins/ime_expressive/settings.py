import wx, tones
import config
from gui import guiHelper, settingsDialogs
# 初始化输入法配置信息
config.conf.spec["ime_expressive"] = {
  "autoReportAllCandidates": "boolean(default=False)",
  "candidateCharacterDescription": "integer(default=2)",
  "reportCandidateBeforeDescription": "integer(default=2)",
  "selectedLeftOrRight": "integer(default=0)",
  "reportCompositionStringChanges": "boolean(default=True)"
}

# 输入法设置界面类
class expressiveInputCompositionPanel(settingsDialogs.SettingsPanel):
	title = "输入法"

	def makeSettings(self, settingsSizer):
		bshSettings = guiHelper.BoxSizerHelper(self, sizer = settingsSizer)
		# 是否自动朗读所有候选项的复选框
		self.autoReportAllCandidates = bshSettings.addItem(wx.CheckBox(self, label = _("自动朗读所有候选项")))
		self.autoReportAllCandidates.SetValue(config.conf["ime_expressive"]["autoReportAllCandidates"])
		# 输入法解释方式的组合框
		self.candidateCharacterDescription = bshSettings.addLabeledControl(_('输入法解释方式'), wx.Choice, choices = ['不解释', '单字解释', '双字解释', '三字解释', '四字解释', '全解释'])
		self.candidateCharacterDescription.SetSelection (config.conf["ime_expressive"]["candidateCharacterDescription"])
		# 解释前先朗读候选项的组合框
		self.reportCandidateBeforeDescription = bshSettings.addLabeledControl(_('解释前先朗读候选项'), wx.Choice, choices = ['从1个字开始', '从2个字开始', '从3个字开始', '从4个字开始', '从5个字开始', '从6个字开始', '不朗读'])
		self.reportCandidateBeforeDescription.SetSelection (config.conf["ime_expressive"]["reportCandidateBeforeDescription"])
		# 选择以词定字按键的组合框
		self.selectedLeftOrRight = bshSettings.addLabeledControl(_('以词定字按键（重启NVDA后生效）'), wx.Choice, choices = ['无', '左 / 右方括号', '逗号 / 句号', '上 / 下翻页'])
		self.selectedLeftOrRight.SetSelection (config.conf["ime_expressive"]["selectedLeftOrRight"])
		# 是否读出上屏内容的复选框
		self.reportCompositionStringChanges = bshSettings.addItem(wx.CheckBox(self, label = _("读出上屏内容")))
		self.reportCompositionStringChanges.SetValue(config.conf["ime_expressive"]["reportCompositionStringChanges"])

	def onSave(self):
		# 保存配置数据
		config.conf["ime_expressive"]["autoReportAllCandidates"] = self.autoReportAllCandidates.IsChecked()
		config.conf["ime_expressive"]["candidateCharacterDescription"] = self.candidateCharacterDescription.GetSelection()
		config.conf["ime_expressive"]["reportCandidateBeforeDescription"] = self.reportCandidateBeforeDescription.GetSelection()
		config.conf["ime_expressive"]["selectedLeftOrRight"] = self.selectedLeftOrRight.GetSelection()
		config.conf["ime_expressive"]["reportCompositionStringChanges"] = self.reportCompositionStringChanges.IsChecked()
