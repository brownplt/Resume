#!/usr/bin/python

import sys
import resume
import config

def getDefault(default):
	ret = sys.stdin.readline()[:-1]
	if (ret == ''):
		return default
	else:
		return ret

if len(sys.argv) > 1:
	if sys.argv[1] == 'initdb':
		sys.stdout.write("""This will completely DESTROY any existing data in the database. Are you sure you want to do this? [y/n] """)
		response = sys.stdin.readline()
		if response[0] == 'y':
			resume.initDB()
			print "Database Initialized."
			sys.exit(0)
		else:
			sys.exit(0)
	elif sys.argv[1] == 'create':
		def getOrCancel():
			ret = sys.stdin.readline()[:-1]
			if ret == 'cancel':
				print 'Exiting immediately.'
				sys.exit(1)
			return ret
		print "Creating a new department installation."
		print "You will now be asked a number of questions. Type Ctrl + C to abort"
		print "at any time."
		print ""
		notcorrect = True
		while notcorrect:
			print "What is the name of your department?"
			print "(default: Brown University Deparment of Horticulture)"
			deptname = getDefault("Brown University Department of Horticulture")
			
			print "What 'short name' do you want to be used in your department's URL?"
			print "(default: brownhort)"
			shortname = getDefault('brownhort')
			print "URL: " + config.serverName + "/" + shortname + "\n"

			print "Now selecting images for custom branding."
			print "Image paths are relative to " + config.serverRoot
			print ""
			
			print "Header image (default: static/browncs-images/header.png)"
			headerImage = getDefault("static/browncs-images/header.png")

			print "Logo image (default: static/browncs-images/logo.png)"
			logoImage = getDefault("static/browncs-images/logo.png")

			print "Resume brand image (default: static/browncs-images/resume.png)"
			resumeImage = getDefault("static/browncs-images/resume.png")

			print "Header background image (default: static/browncs-images/header-bg.png)"
			headerBgImage = getDefault("static/browncs-images/header-bg.png")

			print ""
			print "Title and dark background color (default: #3a1e1a)"
			brandColor = getDefault("#3a1e1a")

			print ""
			print "Now configuring the administrator's account.  This is the first"
			print "account that will be created.  In addition, the administrator's"
			print "email address is placed on all email sent by Resume to applicants"
			print "and letter writers."
			print ""
			print "What is the full name of the main administrator?"
			adminName = getOrCancel()
			print "What is the email address of the main administrator?"
			adminEmail = getOrCancel()
			print "What should the username of the main administrator be?"
			adminUsername = getOrCancel()

			print "The system maintainer is is the person who handles technical"
			print "questions and troubleshooting requests."
			print "(Hint: it's neither Jacob nor Arjun)"
			print ""
			print "What is the email of the system  maintainer?"
			techEmail = getOrCancel()
			print """Thanks. Here's the data you entered:

Department Name:    %s
Short Name:         %s
Header Image:       %s
Logo:               %s
Resume logo:        %s
Header Background:  %s
Title Color:        %s

Admin Name:         %s
Admin Email:        %s
Admin Username:     %s
Resume Maintainer:  %s

Please review this information. If it is correct, a new department installation
will be created, and the password for the main administrator will be returned.
Please record this password, as there is no way to get it subsequently.""" % (deptname,shortname,headerImage,logoImage,resumeImage,headerBgImage,brandColor,adminName,adminEmail,adminUsername,techEmail)
			sys.stdout.write("Is this information correct? [y/n]")
			infocorrect = sys.stdin.readline()
			if infocorrect[0] == 'y':
				notcorrect=False
		password = resume.DepartmentInfo.startDept(deptname,shortname,adminName,adminEmail,adminUsername,techEmail,headerImage,logoImage,resumeImage,headerBgImage,brandColor)
		print "Department Created. Admin password is:"
		print password
		sys.exit(0)

print """install.py: perform installation tasks for Resume
USAGE: ./install.py <action>
ACTIONS:
	initdb: prepare a new "fresh" database (deleting all existing departments)
	create: create a new department installation
"""
sys.exit(1)

