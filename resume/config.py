serverName = 'http://resume.local'

resumeRoot = '/home/resume/resume'

usedb = 'mysql' # sqlite3 also works
dbuser = 'resume'
dbpass = 'resume'
dbname = 'resume' # for sqlite3, this is the path

smtpServer='localhost'
smtpUsername=''	#if blank, this will use normal SMTP
smtpPassword='' #given a username and password, SSMTP will be used

#
# The following settings are derived
#

resumeLog = resumeRoot + '/logs/resume.log'
emailLog = resumeRoot + '/logs/email.log'
serverRoot = resumeRoot + '/resume'
uploadPath = resumeRoot + '/uploads' # recommendations, etc. go here




