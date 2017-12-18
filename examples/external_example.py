from __future__ import print_function

import os
import configobj
import configobj_gui

def main():
	datadir = os.path.dirname(__file__)
	specfile = os.path.join(datadir,'spec.txt')
	conffile = os.path.join(datadir,'config.txt')

	spec = configobj.ConfigObj(specfile, list_values=False)
	config = configobj.ConfigObj(conffile, configspec=spec)

	# Instead of creating a ConfigWindow we spawn an external process (will block)
	config = configobj_gui.configure_externally(config, spec)
	print(config)

main()
