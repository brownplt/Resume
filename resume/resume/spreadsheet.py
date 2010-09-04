#!/usr/bin/env python
from resume import *
import sys


dept = DepartmentInfo.selectBy(shortname='cs')[0]
applicants = list(Applicant.cSelectBy(dept))

#
# Print header
#

print dept.name

scoreCategories = ScoreCategory.selectBy(department=dept)
reviewers = Reviewer.selectBy(department=dept)

print "First Name, Last Name, Gender, Ethnicity, Received (approx), Email",
for cat in scoreCategories:
  print ", %s (Avg.)" % cat.shortform, # Trailing commas omit the newline ...
for cat in scoreCategories:
  for rev in reviewers:
    print ", %s (%s)" % (cat.shortform,rev.uname),
print

def averageScore(applicant,category):
  reviews = applicant.reviews
  net = 0
  num = 0
  for review in reviews:
    for score in review.scores:
      if (score.value.category == category):
        net = net + score.value.number
        num = num + 1
  if num == 0:
    return ""
  else:
    return float(net) / float(num)

def scoreBy(applicant,reviewer,category):
  reviews = list(Review.selectBy(applicant=applicant,draft=False,
                                 reviewer=reviewer))
  if len(reviews) == 0:
    return ""
  elif len(reviews) > 1:
    raise "Multiple reviews for %s by %s" % (applicant,reviewer)
  else:
    scores = reviews[0].scores
    for score in scores:
      if score.value.category == category:
        return score.value.number
    return ""
    



def getCV(comps):
	cvs = filter(lambda c : c.type.short == u"CV", comps)
	if len(cvs) == 1:
		return cvs[0].lastSubmittedStr
	else:
		return u"no CV"

def formatReferences(refs):
	str = ""
	for ref in refs:
		if ref.submitted:
			sub = ref.submittedStr
		else:
			sub = "letter not received"
		str = str + u',"' + ref.name + u'","' + sub + u'"'
	return str

for app in applicants:
  times = map(lambda c : c.lastSubmitted, app.components)
  if len(times) == 0:
    received = u"incomplete"
  else:
    received = convertTime(max(times))
  refs = formatReferences(app.references)
  print u'"%s","%s","%s","%s","%s","%s"' % (
     app.firstname.encode("ascii","replace"),
     app.lastname.encode("ascii","replace"),
     app.gender, 
     ethnicities[app.ethnicity], received, app.email),
  for cat in scoreCategories:
    print ", %s" % averageScore(app,cat),
  for cat in scoreCategories:
    for rev in reviewers:
      print ", %s" % scoreBy(app,rev,cat),
  print
    


