#!/usr/bin/env python
import sys
import copy

import configobj
import validate

#from PyQt4.QtGui import *
#from PyQt4.QtCore import *
from PyQt4 import QtGui
from PyQt4 import QtCore

validator = validate.Validator()

class Option(object):
	"""Description and value of an option"""
	def __init__(self, name, section, type, args, kwargs, default, comment):
		self.name = name
		self.section = section
		self.type = type
		self.args = args
		self.kwargs = kwargs
		self.default = default
		self.comment = comment

	def get(self):
		"""Get current value of the option"""
		return self.section[self.name]

	def set(self, value):
		"""Get current value of the option"""
		# Workaround for problem in validate with lists from string
		value = str(value) # Start with a normal string
		if self.type.endswith('list'):
			value = [x.strip() for x in value.split(',')]
		try:
			self.section[self.name] = validator.functions[self.type](value, *self.args, **self.kwargs)
		except:
			pass

	def __repr__(self):
		"""Convert option to string for debugging purposes"""
		return 'Option(%s,%s,%s,%s,%s,%s,%s)'%(self.name, self.section, self.type, self.args, self.kwargs, self.default, self.comment)

	def restoreDefault(self):
		"""Change option value to the default value"""
		self.section.restore_default(self.name)

	def isDefault(self):
		"""Check whether the option has the default value"""
		return self.name in self.section.defaults


class ConfigPage(QtGui.QWidget):
	"""Container for widgets describing options in a section"""
	def __init__(self, section, item, parent=None):
		QtGui.QWidget.__init__(self, parent)
		layout = QtGui.QGridLayout(self)

		i = 0
		for option in [section[x] for x in section.scalars]:
			label = QtGui.QLabel(option.name) # Display option name
			label.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Preferred)
			layout.addWidget(label, i, 0)
			valueWidget = WidgetCreator.forOption(option) # Create a widget of appropriate type
			valueWidget.optionChanged.connect(self.optionChanged.emit) 
			layout.addWidget(valueWidget, i, 1)
			i += 1

		# Add some spacing at the bottom so the layout remains "packed"
		layout.addItem(QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding), i, 0)

		self.item = item # Store SectionBrowser item corresponding to this page
		self.conf = section # Store configuration section corresponding to this page

	optionChanged = QtCore.pyqtSignal(Option) # Chain signal upwards

	def restoreDefault(self):
		"""Restore default value to all widgets on the page"""
		for widget in [self.layout().itemAt(i) for i in range(self.layout().count())]:
			try:
				widget.widget().restoreDefault()
			except AttributeError: # Skip widgets that can't be restored
				pass

class SectionBrowser(QtGui.QWidget):
	"""TreeView browser of configuration sections. Also manages creating of config pages. It's a bit messy."""
	def __init__(self, conf, parent=None):
		QtGui.QWidget.__init__(self, parent)
		layout = QtGui.QVBoxLayout(self)

		# Create treeview
		self.tree = QtGui.QTreeWidget()
		self.tree.header().hide()
		self.tree.currentItemChanged.connect(lambda new, old: self.currentItemChanged.emit(new))
		layout.addWidget(self.tree)

		# Box that displays add/remove section buttons
		buttonBox = QtGui.QWidget()
		buttonLayout = QtGui.QHBoxLayout(buttonBox)
		self.addButton = QtGui.QPushButton('Add section')
		self.addButton.setIcon(QtGui.QIcon.fromTheme('list-add'))
		self.addButton.setEnabled(False)
		self.addButton.clicked.connect(lambda: self.addEmptySection(self.tree.currentItem()))
		buttonLayout.addWidget(self.addButton)

		self.removeButton = QtGui.QPushButton('Remove section')
		self.removeButton.setIcon(QtGui.QIcon.fromTheme('list-remove'))
		self.removeButton.setEnabled(False)
		buttonLayout.addWidget(self.removeButton)
		self.removeButton.clicked.connect(lambda: self.removeSection(self.tree.currentItem()))
		layout.addWidget(buttonBox)
		self.tree.currentItemChanged.connect(self.activateButtons)

		self.conf = conf # Store configuration
		self.page_lookup = {} # Mappig from treeview item to configuration page

	# A few signals
	currentItemChanged = QtCore.pyqtSignal(QtGui.QTreeWidgetItem)
	pageAdded = QtCore.pyqtSignal(ConfigPage)
	pageRemoved = QtCore.pyqtSignal(ConfigPage)

	def addSection(self, newsection):
		"""Take a configuration section and add corresponding page and treeview item"""
		if newsection.name == None: # Top-level
			item = QtGui.QTreeWidgetItem(self.tree, ['Root'])
			self.tree.addTopLevelItem(item)
		else:
			parent_item = newsection.parent.tree_item
			item = QtGui.QTreeWidgetItem(parent_item, [newsection.name])
		item.setExpanded(True)

		page = ConfigPage(newsection, item)
		self.pageAdded.emit(page)
		newsection.tree_item = item
		self.page_lookup[item] = page

		pages = [page]
		for section in [newsection[x] for x in newsection.sections]:
			pages.extend(self.addSection(section))

		return pages

	def activateButtons(self, item):
		"""Activate add/remove section buttons if appropriate"""
		page = self.page_lookup[item]
		conf = page.conf
		self.addButton.setEnabled(conf.many)
		self.removeButton.setEnabled(conf.optional)

	def addEmptySection(self, item):
		"""Add a new empty section based on the spec of the parent section corresponding to item"""
		parent = self.page_lookup[item].conf # Load combined config for page matching selected item
		spec = parent.spec['__many__'] # Get spec
		conf = configobj.ConfigObj(configspec=spec)
		conf.validate(validator) # Create an empty config matching spec

		combined = merge_spec(conf, spec) # Combine spec and new config

		name, ok = QtGui.QInputDialog.getText(self, 'Add new section', 'Section name:')
		if ok:
			name = str(name)
			combined.name = name
			combined.parent = parent
			parent[name] = combined

			# Copy new config information into old config
			# Workaround for ConfigObj issues
			parent.conf[name] = {}
			def fix_depth(section):
				section.depth = section.parent.depth + 1
				[fix_depth(s) for s in section.sections]
			for key in conf:
				parent.conf[name][key] = conf[key]
				conf[key].parent = parent.conf[name][key]
				if isinstance(conf[key], configobj.Section):
					fix_depth(conf[key])

			self.addSection(combined)

	def removeSection(self, item):
		"""Delete configuration section corresponding to item"""
		item.parent().removeChild(item)
		page = self.page_lookup[item]
		del page.conf.conf.parent[str(item.text(0))]
		self.pageRemoved.emit(page)
		del self.page_lookup[item]


class MyScrollArea(QtGui.QScrollArea):
	"""QtGui.QScrollArea which has a more sensible sizeHint"""
	def __init__(self, parent=None):
		QtGui.QScrollArea.__init__(self, parent)
	def sizeHint(self):
		if self.widget() != None:
			return self.widget().sizeHint()*1.1
		else:
			return QtCore.QSize(10, 10)

class MyWidget(QtGui.QWidget):
	"""Base for widget describing an option"""
	def __init__(self, option, parent = None):
		QtGui.QWidget.__init__(self, parent)
		self.layout = QtGui.QHBoxLayout()
		self.setLayout(self.layout)
		self.option = option
		self.onlywidget = False

	def init(self, option, main_widget, change_signal):
		"""Initialization that has to be performed after some actions made in __init__ in derived classes"""
		self.main_widget = main_widget
		self.layout.addWidget(main_widget)

		self.myconnect(change_signal, self.setValue)
		self.myconnect(change_signal, self.validate)

		# Add validity icon
		self.isValidIcon = QtGui.QLabel()
		self.isValidIcon.setScaledContents(True)
		self.isValidIcon.setPixmap(QtGui.QApplication.style().standardIcon(QtGui.QStyle.SP_MessageBoxWarning).pixmap(256, 256))
		self.isValidIcon.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
		self.isValidIcon.setMaximumHeight(self.main_widget.height()*0.8)
		self.isValidIcon.setMaximumWidth(self.main_widget.height()*0.8)
		self.isValidIcon.hide()
		self.layout.addWidget(self.isValidIcon)

		# Add button to restore default value
		self.restoreDefaultButton = QtGui.QPushButton(self.style().standardIcon(QtGui.QStyle.SP_DialogResetButton), '')
		self.restoreDefaultButton.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Maximum)
		self.restoreDefaultButton.clicked.connect(self.restoreDefault)
		self.restoreDefaultButton.setEnabled(self.option.default != None)
		self.restoreDefaultButton.setToolTip('Restore default value')
		self.layout.addWidget(self.restoreDefaultButton)

		if option.comment:
			main_widget.setToolTip(option.comment)

		# Set displayed value if possible
		try:
			self.option.get()
		except KeyError:
			return

		# No actual change has happened, so prevent the new value from being written to config
		self.onlywidget = True
		self.updateDisplay()
		self.onlywidget = False

	def validate(self, value):
		"""Check if the entered value is valid accoring to the spec"""
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
		"""Helper to conenct to both new and old-style signals"""
		if isinstance(signal, str):
			QtCore.QObject.connect(self.main_widget, QtCore.SIGNAL(signal), func)
		else:
			signal.connect(func)

	def setIsDefault(self):
		"""Tell widget that it represents a default value"""
		style = ''
		for widget in ['QCheckBox', 'QSpinBox', 'QDoubleSpinBox', 'QComboBox', 'QLineEdit']:
			style += '%s {color: gray; font-style: italic}\n'%widget
		self.main_widget.setStyleSheet(style)
		self.restoreDefaultButton.setEnabled(False)

	def unsetIsDefault(self):
		"""Tell widget that it no longer represents a default value"""
		self.main_widget.setStyleSheet('')
		self.restoreDefaultButton.setEnabled(self.option.default != None)

	def restoreDefault(self):
		"""Reset option to default value"""
		try:
			self.option.restoreDefault()
		except KeyError:
			return

		self.onlywidget = True
		self.updateDisplay()
		self.onlywidget = False

		self.setIsDefault()
		self.optionChanged.emit(self.option)

	def updateDisplay(self):
		"""Update widget after a change in the options"""
		if self.option.isDefault():
			self.setIsDefault()

	optionChanged = QtCore.pyqtSignal(Option)

	def setValue(self, value):
		"""Set option value to value"""
		if not self.onlywidget:
			self.option.set(value)
			self.optionChanged.emit(self.option)
			self.unsetIsDefault()

# Validator to check string length
class LengthValidator(QtGui.QValidator):
	"""Validator which enforces string lenght limits"""
	def __init__(self, min=0, max=None, parent = None):
		QtGui.QValidator.__init__(self, parent)
		self.min = min
		self.max = max
	def fixup(self, input):
		if self.min and input.length() < self.min:
			input.resize(self.min)
		elif self.max and input.length() > self.max:
			input.resize(self.max)
	def validate(self, input, pos):
		if self.min and input.length() < self.min:
			return (QtGui.QValidator.Invalid, pos)
		elif self.max and input.length() > self.max:
			return (QtGui.QValidator.Invalid, pos)
		else:
			return (QtGui.QValidator.Acceptable, pos)


class MyLineEdit(MyWidget):
	"""Widget representing a text-like option"""
	def __init__(self, option, min = None, max = None, parent = None):
		MyWidget.__init__(self, option, parent)
		main_widget = QtGui.QLineEdit(self)

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
	"""Widget representing an IP address"""
	def __init__(self, option, parent = None):
		MyLineEdit.__init__(self, option, parent)
		self.main_widget.setInputMask('000.000.000.000')
		if option.get() == option.default: # Seems like a bug in QtGui.QLineEdit. If setInputMask is used, the stylesheet must be set again
			self.setIsDefault()

class MyListEdit(MyWidget):
	"""Widget representing a list"""
	def __init__(self, option, min = None, max = None, parent = None):
		MyWidget.__init__(self, option, parent)
		main_widget = QtGui.QLineEdit(self)
		self.init(option, main_widget, main_widget.textChanged)

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		self.main_widget.setText(', '.join([str(x) for x in self.option.get()]))

class MyCheckBox(MyWidget):
	"""Widget representing a boolean option"""
	def __init__(self, option, parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = QtGui.QCheckBox(self)

		self.init(option, main_widget, main_widget.toggled)

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		self.main_widget.setChecked(validate.bool_dict[self.option.get()])

class MyComboBox(MyWidget):
	"""Widget representing a multiple-choice option"""
	def __init__(self, option, options=[], parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = QtGui.QComboBox(self)
		for value in options:
			main_widget.addItem(str(value))

		self.init(option, main_widget, 'currentIndexChanged(QString)')

	def updateDisplay(self = False):
		MyWidget.updateDisplay(self)
		if self.option.get() != None:
			self.main_widget.setCurrentIndex(self.main_widget.findText(self.option.get()))

class SliderWithLineEdit(QtGui.QWidget):
	"""Slider which displays its current value in a box next to it"""
	def __init__(self, type, min, max, parent = None):
		QtGui.QWidget.__init__(self, parent)
		if type == 'float':
			self.decimals = 2
		else:
			self.decimals = 0

		self.type = type

		self.layout = QtGui.QHBoxLayout()
		self.setLayout(self.layout)
		self.slider = QtGui.QSlider(QtCore.Qt.Horizontal)
		self.slider.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Preferred)
		if type == 'float':
			min = float(min)*10**self.decimals
			max = float(max)*10**self.decimals
		else:
			min = int(min)
			max = int(max)
		self.slider.setMinimum(min)
		self.slider.setMaximum(max)
		self.layout.addWidget(self.slider)
		self.edit = QtGui.QLineEdit(str(self.slider.value()))
		self.edit.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Preferred)
		if type == 'float':
			self.edit.setValidator(QtGui.QDoubleValidator(min, max, self.decimals, None)) # Provide parent explicitly (QtGui.QTBUG-16100)
		else:
			self.edit.setValidator(QtGui.QIntValidator(min, max, None)) # Provide parent explicitly (QtGui.QTBUG-16100)
		self.layout.addWidget(self.edit)
		metrics = QtGui.QFontMetrics(QtGui.QApplication.font())
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
	"""Widget representing a number with min and max specified"""
	def __init__(self, option, min=0, max=100, parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = SliderWithLineEdit(option.type, min, max)
		self.init(option, main_widget, main_widget.edit.textChanged)

	def updateDisplay(self):
		MyWidget.updateDisplay(self)
		self.main_widget.setValue(self.option.get())

class MySpinBox(MyWidget):
	"""Widget representing a number with min or max unspecified"""
	def __init__(self, option, min=None, max=None, parent=None):
		self.decimals = 2
		MyWidget.__init__(self, option, parent)
		if option.type == 'float':
			main_widget = QtGui.QDoubleSpinBox()
			main_widget.setDecimals(self.decimals)
			conv = float
		else:
			main_widget = QtGui.QSpinBox()
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

class WidgetCreator(object):
	"""Class containing static methids for creating widgets representing various option types"""
	@staticmethod
	def forOption(option):
		"""Automatically figures out the appropriate widget type"""
		if option.type.endswith('list'):
			valueWidget = WidgetCreator.create_widget_list(option, *option.args, **option.kwargs)
		else:
			valueWidget = getattr(WidgetCreator, 'create_widget_'+option.type)(option, *option.args, **option.kwargs)
		return valueWidget

	@staticmethod
	def create_widget_integer(option, min=None, max=None):
		"""Create widget for integer option"""
		if min != None and max != None:
			widget = MySlider(option, min, max)
		else:
			widget = MySpinBox(option, min, max)
		return widget

	@staticmethod
	def create_widget_string(option, min=None, max=None):
		"""Create widget for string option"""
		widget = MyLineEdit(option, min, max)
		return widget

	@staticmethod
	def create_widget_float(option, min=None, max=None):
		"""Create widget for float option"""
		if min != None and max != None:
			widget = MySlider(option, min, max)
		else:
			widget = MySpinBox(option, min, max)
		return widget

	@staticmethod
	def create_widget_ip_addr(option):
		"""Create widget for ip_addr option"""
		widget = MyIpEdit(option)
		return widget

	@staticmethod
	def create_widget_boolean(option):
		"""Create widget for boolean option"""
		widget = MyCheckBox(option)
		return widget

	@staticmethod
	def create_widget_option(option, *options):
		"""Create widget for option option"""
		widget = MyComboBox(option, options)
		return widget

	@staticmethod
	def create_widget_list(option, min=None, max=None):
		"""Create widget for any kind of list option"""
		widget = MyListEdit(option, min, max)
		return widget

class ConfigWindow(QtGui.QMainWindow):
	"""Window which contains controls for making changes to a ConfigObj"""

	APPLY_IMMEDIATELY = 1 # GNOME style, apply settings immediately
	APPLY_OK = 2 # KDE style, apply settings when OK is pressed

	def __init__(self, conf, spec, title = 'Configure', when_apply = APPLY_IMMEDIATELY, debug = False, parent = None):
		QtGui.QMainWindow.__init__(self, parent)
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
		main = QtGui.QWidget()
		layout = QtGui.QVBoxLayout(main)
		self.setCentralWidget(main)

		splitter = QtGui.QSplitter()
		layout.addWidget(splitter)
		self.splitter = splitter
		browser = SectionBrowser(conf)
		browser.currentItemChanged.connect(self.changePage)
		browser.pageAdded.connect(self.addPage)
		browser.pageRemoved.connect(self.removePage)
		if spec.sections != []: # Sections are possible
			splitter.addWidget(browser)

		if when_apply == ConfigWindow.APPLY_IMMEDIATELY:
			buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.RestoreDefaults)
		elif when_apply == ConfigWindow.APPLY_OK:
			buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.RestoreDefaults)
		buttons.button(QtGui.QDialogButtonBox.RestoreDefaults).clicked.connect(self.resetAll)
		buttons.button(QtGui.QDialogButtonBox.RestoreDefaults).setIcon(QtGui.QApplication.style().standardIcon(QtGui.QStyle.SP_DialogResetButton))

		if debug: # Show button to print current config as seen from outside
			dump_config = QtGui.QPushButton('Dump')
			buttons.addButton(dump_config, QtGui.QDialogButtonBox.HelpRole)
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

		stacked = QtGui.QStackedWidget()
		configArea.setWidget(stacked)
		splitter.addWidget(configArea)
		configArea.setWidgetResizable(True)

		self.stacked = stacked

		self.pages = {}
		pages = browser.addSection(options)
		if debug:
			def printChange(option):
				print '%s in %s changed to %s'%(option.name, option.section.name, option.get()) 
			self.optionChanged.connect(printChange)

	optionChanged = QtCore.pyqtSignal(Option)

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
		page.optionChanged.connect(self.optionChanged.emit)

	def removePage(self, page):
		self.pages[page.item] = self.stacked.removeWidget(page)
		del self.pages[page.item]

def merge_spec(config, spec):
	"""Combine config and spec into one tree in the form of Option objects"""
	combined = configobj.ConfigObj()

	combined.optional = '__many__' in spec.parent and spec != spec.parent
	combined.many = '__many__' in spec

	# Store origial conf and spec
	combined.conf = config
	combined.spec = spec

	# Recursively combine sections
	for section in config.sections:
		if section in spec:
			combined[section] = merge_spec(config[section], spec[section])
		elif '__many__' in spec:
			combined[section] = merge_spec(config[section], spec['__many__'])

		combined[section].name = section
		combined[section].parent = combined

	# Combine individual options
	for option in spec.scalars:
		comment = spec.inline_comments[option]
		if comment and comment.startswith('#'):
			comment = comment[1:].strip()
		fun_name, fun_args, fun_kwargs, default = validator._parse_with_caching(spec[option]) # WARNING: Uses unoffical method!
		combined[option] = Option(option, config, fun_name, fun_args, fun_kwargs, default, comment)

	return combined


def configure_externally(config, spec):
	"""Launch a ConfigWindow in an external process"""
	import cPickle, subprocess, time
	path = __file__
	if path.endswith('.pyc'):
		path = path[:-1]
	proc = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
	newconf = cPickle.loads(proc.communicate(cPickle.dumps((config, spec)))[0])
	newconf.write(sys.stdout)

if __name__ == '__main__':
	import cPickle
	conf, spec = cPickle.loads(sys.stdin.read())
	app = QtGui.QApplication(sys.argv)
	wnd = ConfigWindow(conf, spec)
	wnd.show()
	app.exec_()
	print cPickle.dumps(conf),

