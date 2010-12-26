import sys
import os
from PyQt4 import QtGui
import configobj
import configobj_gui

def main():
	datadir = os.path.dirname(__file__)
	specfile = os.path.join(datadir,'spec.txt')
	conffile = os.path.join(datadir,'config.txt')

	spec = configobj.ConfigObj(specfile, list_values=False)
	config = configobj.ConfigObj(conffile, configspec=spec)

	# Instead of creating a ConfigWindow we spawn an external process (will block)
	app = QtGui.QApplication(sys.argv)
	wnd = configobj_gui.ConfigWindow(config, spec, when_apply=configobj_gui.ConfigWindow.APPLY_OK)
	wnd.show()
	def printChange(option):
		print '%s in %s changed to %s'%(option.name, option.section.name, option.get()) 
	def printSectionAdded(section):
		print 'Added section %s'%(section.name)
	def printSectionRemoved(section):
		print 'Removed section %s'%(section.name)

	wnd.optionChanged.connect(printChange)
	wnd.sectionAdded.connect(printSectionAdded)
	wnd.sectionRemoved.connect(printSectionRemoved)
	app.exec_()
	print config

main()
