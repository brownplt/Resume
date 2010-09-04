import resume, time

bcs = resume.DepartmentInfo.selectBy(shortname='browncs')[0]

def getLastName(app):
	acmps = app.auth.name.split(' ')
	if acmps[-1].lower() in ['jr','jr.','sr','sr.','iii']:
		return ' '.join(acmps[-2:])
	else:
		return acmps[-1]
def getFirstName(app):
	acmps = app.auth.name.split(' ')
	if acmps[-1].lower() in ['jr','jr.','sr','sr.','iii']:
		return ' '.join(acmps[:-2])
	else:
		return ' '.join(acmps[:-1])

print '\n'.join(
		['"Submission Time","First Name","Last Name","Email","Gender","Ethnicity","Areas","Rejected"']+
		[
			'"%s","%s","%s","%s","%s","%s","%s","%s"' %
				(time.ctime(max([c.lastSubmitted for c in app.components]+[0])),
				 getFirstName(app),
				 getLastName(app),
				 app.email,
				 app.gender,
				 resume.ethnicities[app.ethnicity],
				 ';'.join([a.name for a in app.areas]),
				 app.rejected) for app in resume.Applicant.cSelectBy(bcs)])
