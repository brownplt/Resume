
def makeReferenceRequest(applicantName,referenceName,serverName,deptName,
                         deptShortName,letterCode):
  return u"""Dear %(name)s,

%(appname)s has requested that you provide a letter of reference to
%(orgname)s.

To submit your letter, please visit the URL:

%(servername)s/%(deptname)s/letter.html?code=%(code)d
	
If you have trouble with this procedure, visit
%(servername)s/%(deptname)s/contact.html
for information on contacting the server administrator.

[This message was generated automatically by the Resume faculty
recruiting system.]

%(orgname)s""" % {'appname': applicantName,
                  'name': referenceName,
                  'servername': serverName,
                  'deptname': deptShortName,
                  'code': letterCode,
                  'orgname': deptName}
