from __future__ import print_function

import sys
import os

import sip
sip.setapi('QString', 1)

from PyQt4 import QtGui
import configobj
import configobj_gui
import validate

def main():
	datadir = os.path.dirname(__file__)
	specfile = os.path.join(datadir,'spec.txt')
	conffile = os.path.join(datadir,'config.txt')

	spec = configobj.ConfigObj(specfile, list_values=False)
	config = configobj.ConfigObj(conffile, configspec=spec)

	app = QtGui.QApplication(sys.argv)
	validator = validate.Validator()
	wnd = configobj_gui.ConfigWindow(config, spec, when_apply=configobj_gui.ConfigWindow.APPLY_OK, type_mapping={'mytype':(configobj_gui.create_widget_string, validate.is_integer)})
	wnd.show()

	def printChange(option):
		print('%s in %s changed to %s'%(option.name, option.section.name, option.get())) 
	def printSectionAdded(section):
		print('Added section %s'%(section.name))
	def printSectionRemoved(section):
		print('Removed section %s'%(section.name))

	wnd.optionChanged.connect(printChange)
	wnd.sectionAdded.connect(printSectionAdded)
	wnd.sectionRemoved.connect(printSectionRemoved)
	app.exec_()
	print(config)

main()
