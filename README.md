ConfigObj-GUI provides a [PyQt](http://www.riverbankcomputing.com/software/pyqt/) based mechanism to edit [ConfigObj](http://www.voidspace.org.uk/python/configobj.html) configurations. It is intended to be used as a library to help configure PyQt based applications using ConfigObj.

Note that the library is not very robust yet as it has not been tested very much.

The basic usage is as follows:

	import sys
	from PyQt4.QtGui import QApplication
	import configobj
	import configobj_gui

	app = QApplication(sys.argv)

	spec = configobj.ConfigObj('yourspecfile', list_values=False)
	conf = configobj.ConfigObj('yourconffile', configspec=spec)

	wnd = configobj_gui.ConfigWindow(conf, spec)
	wnd.show()

	app.exec_()
	print conf

Support the developer if you like this software:
[![Donate using Liberapay](https://liberapay.com/assets/widgets/donate.svg)](https://liberapay.com/saparvia/donate)
