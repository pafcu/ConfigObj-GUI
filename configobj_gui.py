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
		return self.section.get(self.name, None)
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

	def init(self, option, main_widget, change_signal):
		self.main_widget = main_widget
		self.layout.addWidget(main_widget)

		self.myconnect(change_signal, lambda x: self.unsetIsDefault())
		self.myconnect(change_signal, option.set)
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

		if option.default != None and (option.get() == None or option.get() == validator.functions[option.type](option.default)):
			self.setIsDefault()

		if option.comment:
			main_widget.setToolTip(option.comment)

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
		pass

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
		realvalue = option.get()
		if realvalue == None:
			main_widget = QLineEdit(self)
		else:
			main_widget = QLineEdit(str(realvalue), self)

		if min != None:
			min = int(min)
		if max != None:
			max = int(max)
		main_widget.setValidator(LengthValidator(min, max))

		self.init(option, main_widget, main_widget.textChanged)

	def restoreDefault(self):
		self.main_widget.setText(self.option.default)
		self.setIsDefault()

class MyIpEdit(MyLineEdit):
	def __init__(self, option, parent = None):
		MyLineEdit.__init__(self, option, parent)
		self.main_widget.setInputMask('000.000.000.000')
		if option.get() == option.default: # Seems like a bug in QLineEdit. If setInputMask is used, the stylesheet must be set again
			self.setIsDefault()

class MyListEdit(MyWidget):
	def __init__(self, option, min = None, max = None, parent = None):
		MyWidget.__init__(self, option, parent)
		realvalue = option.get()
		if realvalue == None:
			main_widget = QLineEdit()
		else:
			main_widget = QLineEdit(', '.join([str(x) for x in realvalue]), self)
		self.init(option, main_widget, main_widget.textChanged)
	def restoreDefault(self):
		self.main_widget.setText(', '.join(self.option.default))
		self.setIsDefault()

class MyCheckBox(MyWidget):
	def __init__(self, option, parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = QCheckBox(self)

		if option.get() != None:
			main_widget.setChecked(option.get())

		self.init(option, main_widget, main_widget.toggled)

	def restoreDefault(self):
		self.main_widget.setChecked(validate.bool_dict[self.option.default.lower()])
		self.setIsDefault()

class MyComboBox(MyWidget):
	def __init__(self, option, options=[], parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = QComboBox(self)
		for value in options:
			main_widget.addItem(str(value))
		selected = -1
		if option.get() != None: # Try setting the correct value
			selected = main_widget.findText(option.get())
		elif selected == -1 and option.default != None: # If no value or it's invalid
			selected = main_widget.findText(option.default)
		else: # No value, no default
			main_widget.insertItem(0, '')
			selected = 0

		main_widget.setCurrentIndex(selected)

		self.init(option, main_widget, 'currentIndexChanged(QString)')

	def restoreDefault(self):
		self.main_widget.setCurrentIndex(self.main_widget.findText(self.option.default))
		self.setIsDefault()

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

class MySlider(MyWidget):
	def __init__(self, option, min=0, max=100, parent=None):
		MyWidget.__init__(self, option, parent)
		main_widget = SliderWithLineEdit(option.type, min, max)
		main_widget.slider.setValue(int(option.get()))
		self.init(option, main_widget, main_widget.edit.textChanged)

	def restoreDefault(self):
		self.main_widget.setSliderValue(self.option.default)
		self.main_widget.setEditValue(self.main_widget.slider.value())
		self.setIsDefault()

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
		main_widget.setValue(conv(option.get()))
		self.init(option, main_widget, main_widget.valueChanged)

	def restoreDefault(self):
		if self.option.default != None:
			self.main_widget.setValue(self.option.default)
			self.setIsDefault()

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
		realvalue = option.get()
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
		realvalue = option.get()
		if min != None and max != None:
			widget = MySlider(option, min, max)
		else:
			widget = MySpinBox(option, min, max)

		return widget
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
		if option.default == None:
			option.default = options[0]
		widget = MyComboBox(option, options)
		return widget

	@staticmethod
	def create_widget_list(option, min=None, max=None):
		widget = MyListEdit(option, min, max)

		return widget

class ConfigWindow(QMainWindow):
	APPLY_IMMEDIATELY = 1
	APPLY_OK = 2
	def __init__(self, conf, spec, title = 'Configure', when_apply = APPLY_IMMEDIATELY, debug = False, parent = None):
		QMainWindow.__init__(self, parent)

		res = conf.validate(validate.Validator(), preserve_errors=True)

		# Make changes to a copy of the original conf if needed
		if when_apply != ConfigWindow.APPLY_IMMEDIATELY:
			self.original_conf = conf
			conf = copy.deepcopy(conf)
		else:
			self.original_conf = conf

		self.conf = conf

		self.setWindowTitle(title)
		res = conf.validate(validate.Validator(), preserve_errors=True)
		options = configobj.ConfigObj(merge_spec(conf, spec))
		main = QWidget()
		layout = QVBoxLayout(main)
		self.setCentralWidget(main)

		splitter = QSplitter()
		layout.addWidget(splitter)
		self.splitter = splitter
		tree = QTreeWidget()
		tree.header().hide()
		splitter.addWidget(tree)

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

		pages = {}
		self.widgets = []

		def addToTree(root, tree):
			for section in [root[x] for x in root.sections]:
				section = root[section.name]
				item = QTreeWidgetItem(tree, [section.name])
				addToTree(section, item)
				page = createConfigPage(section)
				pages[item] = stacked.addWidget(page)

		def createConfigPage(section):
			widget = QWidget()
			layout = QGridLayout()
			widget.setLayout(layout)
			i = 0
			for option in [section[x] for x in section.scalars]:
				label = QLabel(option.name)
				layout.addWidget(label, i, 0)
				valueWidget = WidgetCreator.forOption(option)
				layout.addWidget(valueWidget, i, 1)
				self.widgets.append(valueWidget)
				i += 1
			layout.addItem(QSpacerItem(0, 0, QSizePolicy.Preferred, QSizePolicy.Expanding), i, 0)
			return widget

		addToTree(options, tree)

		tree.currentItemChanged.connect(self.changePage)

		self.pages = pages
		self.stacked = stacked

	def changePage(self, current, previous):
		index = self.pages[current]
		self.stacked.setCurrentIndex(index)

	def updateOriginalConf(self):
		if self.original_conf:
			for key in self.conf:
				self.original_conf[key] = self.conf[key]
	def resetAll(self):
		for widget in self.widgets:
			widget.restoreDefault()

def merge_spec(config, spec):
	combined = {}
	for section in config.sections:
		if section in spec:
			combined[section] = merge_spec(config[section], spec[section])
		elif '__many__' in spec:
			combined[section] = merge_spec(config[section], spec['__many__'])
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
			[main]
			mystring = string(default='foo',min=2,max=10) # A string
			myinteger = integer(default=4, min=-2, max=10) # A integer with min and max
			myinteger2 = integer(default=2, min=-1) # A integer with min but no max
			myoption = option(bar,baz) # Options
			myip = ip_addr(default='127.0.0.1') # An IP address
			mylist = list(default=list('a','b')) # A list
			myintlist = int_list(default=list(1,2)) # A list of integers
			myfloat = float(default=2.2, min=-1, max=10.0) # A float with min and max
			myfloat2 = float(default=1.1, min=-0.2) # A float with min but no max
			mycheckbox = boolean(default=True) # A checkbox
			nondefault = integer # An integer with no default value

			[other]
			[[level2]]
			enabled = boolean(default=True)
		"""
		configtxt = """
			[main]
			nondefault = 4
		"""
		spec = configobj.ConfigObj(spectxt.split('\n'), list_values=False)
		config = configobj.ConfigObj(configtxt.split('\n'), configspec=spec)

		app = QApplication(sys.argv)
		wnd = ConfigWindow(config, spec, when_apply=ConfigWindow.APPLY_OK, debug=True)
		wnd.show()
		app.exec_()
		print config

	main()
