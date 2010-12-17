import sys
import copy

import configobj
import validate

from PyQt4.QtGui import *
from PyQt4.QtCore import *

validator = validate.Validator()

# Describes a configobj value and its type
class Option(object):
	def __init__(self, name, section, type, args, kwargs, default, comment):
		self.name = name
		self.section = section
		self.type = type
		self.args = args
		self.kwargs = kwargs
		self.default = default
		self.comment = comment
	def get(self):
		return self.section[self.name]
	def set(self, value):
		# Workaround for problem in validate with lists from string
		value = str(value) # Start with a normal string
		if self.type.endswith('list'):
			value = [x.strip() for x in value.split(',')]
		try:
			self.section[self.name] = validator.functions[self.type](value, *self.args, **self.kwargs)
		except:
			pass
	def __repr__(self):
		return 'Option(%s,%s,%s,%s,%s,%s,%s)'%(self.name, self.section, self.type, self.args, self.kwargs, self.default, self.comment)

	def restoreDefault(self):
		self.section.restore_default(self.name)


	def isDefault(self):
		return self.name in self.section.defaults


class ConfigPage(QWidget):
	def __init__(self, section, item, parent=None):
		QWidget.__init__(self, parent)
		layout = QGridLayout()
		self.setLayout(layout)
		i = 0
		for option in [section[x] for x in section.scalars]:
			label = QLabel(option.name)
			layout.addWidget(label, i, 0)
			valueWidget = WidgetCreator.forOption(option)
			layout.addWidget(valueWidget, i, 1)
			i += 1
		layout.addItem(QSpacerItem(0, 0, QSizePolicy.Preferred, QSizePolicy.Expanding), i, 0)

		self.item = item
		self.conf = section

	def restoreDefault(self):
		for widget in [self.layout().itemAt(i) for i in range(self.layout().count())]:
			try:
				widget.widget().restoreDefault()
			except AttributeError: # Skip widgets that can't be restored
				pass

class SectionBrowser(QWidget):
	def __init__(self, conf, parent=None):
		QWidget.__init__(self, parent)
		layout = QVBoxLayout(self)
		self.tree = QTreeWidget()
		self.tree.header().hide()
		self.tree.currentItemChanged.connect(lambda new,old: self.currentItemChanged.emit(new))
		layout.addWidget(self.tree)

		buttonBox = QWidget()
		buttonLayout = QHBoxLayout(buttonBox)
		self.addButton = QPushButton('Add section')
		self.addButton.setIcon(QIcon.fromTheme('list-add'))
		self.addButton.setEnabled(False)
		self.addButton.clicked.connect(lambda: self.addEmptySection(self.tree.currentItem()))
		buttonLayout.addWidget(self.addButton)

		self.removeButton = QPushButton('Remove section')
		self.removeButton.setIcon(QIcon.fromTheme('list-remove'))
		self.removeButton.setEnabled(False)
		buttonLayout.addWidget(self.removeButton)
		self.removeButton.clicked.connect(lambda: self.removeSection(self.tree.currentItem()))
		layout.addWidget(buttonBox)
		self.tree.currentItemChanged.connect(self.activateButtons)

		self.conf = conf
		self.page_lookup = {}

	currentItemChanged = pyqtSignal(QTreeWidgetItem)
	pageAdded = pyqtSignal(ConfigPage)
	pageRemoved = pyqtSignal(ConfigPage)

	def addSection(self, newsection):
		if newsection.name == None: # Top-level
			item = QTreeWidgetItem(self.tree, ['Root'])
			self.tree.addTopLevelItem(item)
		else:
			parent_item = newsection.parent.tree_item
			item = QTreeWidgetItem(parent_item, [newsection.name])

		page = ConfigPage(newsection, item)
		self.pageAdded.emit(page)
		newsection.tree_item = item
		self.page_lookup[item] = page

		pages = [page]
		for section in [newsection[x] for x in newsection.sections]:
			pages.extend(self.addSection(section))

		return pages

	def activateButtons(self, item):
		page = self.page_lookup[item]
		conf = page.conf
		self.addButton.setEnabled(conf.many)
		self.removeButton.setEnabled(conf.optional)

	def addEmptySection(self, item):
		parent = self.page_lookup[item].conf
		spec = parent.spec['__many__']
		conf = configobj.ConfigObj(configspec=spec)
		conf.validate(validator)
		combined = merge_spec(conf,spec)
		combined.parent = parent

		name, ok = QInputDialog.getText(self,'Add new section','Section name:')
		if ok:
			name = str(name)
			combined.name = name
			conf.name = name
			parent[name] = combined
			parent.conf[name] = {}
			for key in conf:
				parent.conf[name][key] = conf[key]
			self.addSection(combined)

	def removeSection(self, item):
		item.parent().removeChild(item)
		page = self.page_lookup[item]
		del page.conf.conf.parent[str(item.text(0))]
		self.pageRemoved.emit(page)
		del self.page_lookup[item]


# Hack to make QScrollArea resize to a suitable size
class MyScrollArea(QScrollArea):
	def __init__(self, parent=None):
		QScrollArea.__init__(self, parent)
	def sizeHint(self):
		if self.widget() != None:
			return self.widget().sizeHint()*1.1
		else:
			return QSize(10, 10)

# Base for widget with associated validity and restore icons
class MyWidget(QWidget):
	def __init__(self, option, parent = None):
		QWidget.__init__(self, parent)
		self.layout = QHBoxLayout()
		self.setLayout(self.layout)
		self.option = option
		self.restoring = False

	def init(self, option, main_widget, change_signal):
		self.main_widget = main_widget
		self.layout.addWidget(main_widget)

		self.myconnect(change_signal, self.setValue)
		self.myconnect(change_signal, self.validate)

		self.isValidIcon = QLabel()
		self.isValidIcon.setScaledContents(True)
		self.isValidIcon.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(256, 256))
		self.isValidIcon.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		self.isValidIcon.setMaximumHeight(self.main_widget.height()*0.8)
		self.isValidIcon.setMaximumWidth(self.main_widget.height()*0.8)
		self.isValidIcon.hide()
		self.layout.addWidget(self.isValidIcon)

		self.restoreDefaultButton = QPushButton(self.style().standardIcon(QStyle.SP_DialogResetButton), '')
		self.restoreDefaultButton.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
		self.restoreDefaultButton.clicked.connect(self.restoreDefault)
		self.restoreDefaultButton.setEnabled(self.option.default != None)

		self.layout.addWidget(self.restoreDefaultButton)

		if option.comment:
			main_widget.setToolTip(option.comment)

		try:
			self.option.get()
		except KeyError:
			return

		# No actual change has happened, so prevent the new value from being written to config
		self.restoring = True
		self.updateDisplay()
		self.restoring = False

	def validate(self, value):
		value = str(value) # Start with a normal string
		if self.option.type.endswith('list'):
			value = [x.strip() for x in value.split(',')]
		try:
			validator.functions[self.option.type](value, *self.option.args, **self.option.kwargs)
		except Exception, e:
			self.isValidIcon.setToolTip(str(e))
			self.isValidIcon.show()
			return
		self.isValidIcon.hide()

	def myconnect(self, signal, func):
		if isinstance(signal, str):
			QObject.connect(self.main_widget, SIGNAL(signal), func)
		else:
			signal.connect(func)

	def setIsDefault(self):
		style = ''
		for widget in ['QCheckBox', 'QSpinBox', 'QDoubleSpinBox', 'QComboBox', 'QLineEdit']:
			style += '%s {color: gray; font-style: italic}\n'%widget
		self.main_widget.setStyleSheet(style)
		self.restoreDefaultButton.setEnabled(False)

	def unsetIsDefault(self):
		self.main_widget.setStyleSheet('')
		self.restoreDefaultButton.setEnabled(self.option.default != None)

	def restoreDefault(self):
		try:
			self.option.restoreDefault()
		except KeyError:
			return

		self.restoring = True
		self.updateDisplay()
		self.setIsDefault()
		self.restoring = False

	def updateDisplay(self):
		if self.option.isDefault():
			self.setIsDefault()

	def setValue(self, value):
		if not self.restoring:
			self.option.set(value)
			self.unsetIsDefault()

# Validator to check string length
class LengthValidator(QValidator):
	def __init__(self, min=0, max=None, parent = None):
		QValidator.__init__(self, parent)
		self.min = min
		self.max = max
	def fixup(self, input):
		if self.min and input.length() < self.min:
			input.resize(self.min)
		elif self.max and input.length() > self.max:
			input.resize(self.max)
	def validate(self, input, pos):
		if self.min and input.length() < self.min:
			return (QValidator.Invalid, pos)
		elif self.max and input.length() > self.max:
			return (QValidator.Invalid, pos)
		else:
			return (QValidator.Acceptable, pos)


class MyLineEdit(MyWidget):
	def __init__(self, option, min = None, max = None, parent = None):
		MyWidget.__init__(self, option, parent)
		main_widget = QLineEdit(self)

		if min != None:
			min = int(min)
		if max != None:
			max = int(max)
		main_widget.setValidator(LengthValidator(min, max))

		self.init(option, main_widget, main_widget.textChanged)

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		self.main_widget.setText(str(self.option.get()))

class MyIpEdit(MyLineEdit):
	def __init__(self, option, parent = None):
		MyLineEdit.__init__(self, option, parent)
		self.main_widget.setInputMask('000.000.000.000')
		if option.get() == option.default: # Seems like a bug in QLineEdit. If setInputMask is used, the stylesheet must be set again
			self.setIsDefault()

class MyListEdit(MyWidget):
	def __init__(self, option, min = None, max = None, parent = None):
		MyWidget.__init__(self, option, parent)
		main_widget = QLineEdit(self)
		self.init(option, main_widget, main_widget.textChanged)

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		self.main_widget.setText(', '.join([str(x) for x in self.option.get()]))

class MyCheckBox(MyWidget):
	def __init__(self, option, parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = QCheckBox(self)

		self.init(option, main_widget, main_widget.toggled)

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		self.main_widget.setChecked(validate.bool_dict[self.option.get()])

class MyComboBox(MyWidget):
	def __init__(self, option, options=[], parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = QComboBox(self)
		for value in options:
			main_widget.addItem(str(value))

		self.init(option, main_widget, 'currentIndexChanged(QString)')

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		if self.option.get() != None:
			self.main_widget.setCurrentIndex(self.main_widget.findText(self.option.get()))

class SliderWithLineEdit(QWidget):
	def __init__(self, type, min, max, parent = None):
		QWidget.__init__(self, parent)
		if type == 'float':
			self.decimals = 2
		else:
			self.decimals = 0

		self.type = type

		self.layout = QHBoxLayout()
		self.setLayout(self.layout)
		self.slider = QSlider(Qt.Horizontal)
		self.slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		if type == 'float':
			min = float(min)*10**self.decimals
			max = float(max)*10**self.decimals
		else:
			min = int(min)
			max = int(max)
		self.slider.setMinimum(min)
		self.slider.setMaximum(max)
		self.layout.addWidget(self.slider)
		self.edit = QLineEdit(str(self.slider.value()))
		self.edit.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
		if type == 'float':
			self.edit.setValidator(QDoubleValidator(min, max, self.decimals, None)) # Provide parent explicitly (QTBUG-16100)
		else:
			self.edit.setValidator(QIntValidator(min, max, None)) # Provide parent explicitly (QTBUG-16100)
		self.layout.addWidget(self.edit)
		metrics = QFontMetrics(QApplication.font())
		if type == 'float':
			self.edit.setMaximumWidth(metrics.width(len(str(max))*"8"+"."+"8"))
		else:
			self.edit.setMaximumWidth(metrics.width(len(str(max))*"8"+"8"))
		self.edit.textChanged.connect(self.setSliderValue)
		self.slider.valueChanged.connect(self.setEditValue)

		self.reaction = False

	def setSliderValue(self, s):
		if self.reaction: # Prevent lineedit change from triggering this
			self.reaction = False
			return
		self.reaction = True
		try:
			if self.type == 'float':
				self.slider.setValue((round(float(s)*10**self.decimals)))
			else:
				self.slider.setValue(int(s))
		except TypeError:
			pass
		except ValueError:
			if s == '':
				self.slider.setValue(self.slider.minimum())

	def setEditValue(self, i):
		if self.reaction: # Prevent slider change from triggering this
			self.reaction = False
			return
		self.reaction = True
		if self.type == 'float':
			format = '%.'+str(self.decimals)+'f'
			self.edit.setText(format%(float(i)/float(10**self.decimals)))
		else:
			self.edit.setText(str(i))

	def setValue(self, value):
		self.setSliderValue(str(value))
		self.edit.setText(str(value))


class MySlider(MyWidget):
	def __init__(self, option, min=0, max=100, parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = SliderWithLineEdit(option.type, min, max)
		self.init(option, main_widget, main_widget.edit.textChanged)

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		self.main_widget.setValue(self.option.get())

class MySpinBox(MyWidget):
	def __init__(self, option, min=None, max=None, parent=None):
		self.decimals = 2
		MyWidget.__init__(self, option, parent)
		if option.type == 'float':
			main_widget = QDoubleSpinBox()
			main_widget.setDecimals(self.decimals)
			conv = float
		else:
			main_widget = QSpinBox()
			if option.default != None:
				option.default = int(option.default)
			conv = int

		if option.default != None:
			option.default = conv(option.default)
		if min != None:
			main_widget.setMinimum(conv(min))
		if max != None:
			main_widget.setMaximum(conv(max))

		self.init(option, main_widget, main_widget.valueChanged)

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		if self.option.get() != None:
			self.main_widget.setValue(self.option.get())

# Some wrappers to create correct Widget based on type
class WidgetCreator(object):
	@staticmethod
	def forOption(option):
		if option.type.endswith('list'):
			valueWidget = WidgetCreator.create_widget_list(option, *option.args, **option.kwargs)
		else:
			valueWidget = getattr(WidgetCreator, 'create_widget_'+option.type)(option, *option.args, **option.kwargs)
		return valueWidget

	@staticmethod
	def create_widget_integer(option, min=None, max=None):
		if min != None and max != None:
			widget = MySlider(option, min, max)
		else:
			widget = MySpinBox(option, min, max)

		return widget

	@staticmethod
	def create_widget_string(option, min=None, max=None):
		widget = MyLineEdit(option, min, max)
		return widget

	@staticmethod
	def create_widget_float(option, min=None, max=None):
		if min != None and max != None:
			widget = MySlider(option, min, max)
		else:
			widget = MySpinBox(option, min, max)

		return widget

	@staticmethod
	def create_widget_ip_addr(option):
		widget = MyIpEdit(option)
		return widget

	@staticmethod
	def create_widget_boolean(option):
		widget = MyCheckBox(option)
		return widget

	@staticmethod
	def create_widget_option(option, *options):
		widget = MyComboBox(option, options)
		return widget

	@staticmethod
	def create_widget_list(option, min=None, max=None):
		widget = MyListEdit(option, min, max)

		return widget

class ConfigWindow(QMainWindow):
	APPLY_IMMEDIATELY = 1 # GNOME style, apply settings immediately
	APPLY_OK = 2 # KDE style, apply settings when OK is pressed
	def __init__(self, conf, spec, title = 'Configure', when_apply = APPLY_IMMEDIATELY, debug = False, parent = None):
		QMainWindow.__init__(self, parent)
		res = conf.validate(validator, preserve_errors=True)

		# Make changes to a copy of the original conf if needed
		if when_apply != ConfigWindow.APPLY_IMMEDIATELY:
			self.original_conf = conf
			conf = copy.deepcopy(conf)
		else:
			self.original_conf = conf

		self.conf = conf

		self.setWindowTitle(title)
		res = conf.validate(validate.Validator(), preserve_errors=True)
		options = merge_spec(conf, spec)
		main = QWidget()
		layout = QVBoxLayout(main)
		self.setCentralWidget(main)

		splitter = QSplitter()
		layout.addWidget(splitter)
		self.splitter = splitter
		browser = SectionBrowser(conf)
		browser.currentItemChanged.connect(self.changePage)
		browser.pageAdded.connect(self.addPage)
		browser.pageRemoved.connect(self.removePage)
		splitter.addWidget(browser)

		if when_apply == ConfigWindow.APPLY_IMMEDIATELY:
			buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.RestoreDefaults)
		elif when_apply == ConfigWindow.APPLY_OK:
			buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults)
		buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self.resetAll)
		buttons.button(QDialogButtonBox.RestoreDefaults).setIcon(QApplication.style().standardIcon(QStyle.SP_DialogResetButton))

		if debug: # Show button to print current config as seen from outside
			dump_config = QPushButton('Dump')
			buttons.addButton(dump_config, QDialogButtonBox.HelpRole)
			def dump():
				print self.original_conf
			dump_config.clicked.connect(dump)

		buttons.accepted.connect(self.close)
		buttons.accepted.connect(self.updateOriginalConf)

		buttons.rejected.connect(self.close)

		layout.addWidget(buttons)

		configArea = MyScrollArea()
		self.configArea = configArea
		splitter.addWidget(configArea)
		splitter.setStretchFactor(1, 2)

		stacked = QStackedWidget()
		configArea.setWidget(stacked)
		splitter.addWidget(configArea)
		configArea.setWidgetResizable(True)

		self.stacked = stacked

		self.pages = {}
		pages = browser.addSection(options)

	def changePage(self, newItem):
		index = self.pages[newItem]
		self.stacked.setCurrentIndex(index)

	def updateOriginalConf(self):
		if self.original_conf:
			for key in self.conf:
				if key not in self.conf.defaults:
					self.original_conf[key] = self.conf[key]

	def resetAll(self):
		for page in [self.stacked.widget(i) for i in range(self.stacked.count())]:
			page.restoreDefault()

	def addPage(self, page):
		self.pages[page.item] = self.stacked.addWidget(page)
	def removePage(self, page):
		self.pages[page.item] = self.stacked.removeWidget(page)
		del self.pages[page.item]

def merge_spec(config, spec):
	combined = configobj.ConfigObj()

	combined.optional = '__many__' in spec.parent and spec != spec.parent# Anything in __many__ is optional
	combined.many = '__many__' in spec
	combined.conf = config
	combined.spec = spec

	for section in config.sections:
		if section in spec:
			combined[section] = merge_spec(config[section], spec[section])
		elif '__many__' in spec:
			combined[section] = merge_spec(config[section], spec['__many__'])

		combined[section].name = section
		combined[section].parent = combined

	for option in spec.scalars:
		comment = spec.inline_comments[option]
		if comment and comment.startswith('#'):
			comment = comment[1:].strip()
		fun_name, fun_args, fun_kwargs, default = validator._parse_with_caching(spec[option]) # WARNING: Uses unoffical method!
		combined[option] = Option(option, config, fun_name, fun_args, fun_kwargs, default, comment)

	return combined

if __name__ == '__main__':
	def main():
		spectxt = """
			mystring = string(default='foo',min=2,max=10) # A string
			myinteger = integer(default=4, min=-2, max=10) # A integer with min and max
			myinteger2 = integer(default=2, min=-1) # A integer with min but no max
			myoption = option(default='baz','bar','baz') # Options
			myip = ip_addr(default='127.0.0.1') # An IP address
			mylist = list(default=list('a','b')) # A list
			myintlist = int_list(default=list(1,2)) # A list of integers
			myfloat = float(default=2.2, min=-1, max=10.0) # A float with min and max
			myfloat2 = float(default=1.1, min=-0.2) # A float with min but no max
			mycheckbox = boolean(default=True) # A checkbox
			nondefault = integer # An integer with no default value

			[__many__]
			[[level2]]
			enabled = boolean(default=True)
		"""
		configtxt = """
			notinspec = foo
			[section]
			[[level2]]
			[other]
		"""
		app = QApplication(sys.argv)

		spec = configobj.ConfigObj(spectxt.split('\n'), list_values=False)
		config = configobj.ConfigObj(configtxt.split('\n'), configspec=spec)

		wnd = ConfigWindow(config, spec, when_apply=ConfigWindow.APPLY_IMMEDIATELY, debug=True)
		wnd.show()
		app.exec_()
		print '\n'.join(config.write())

	main()
