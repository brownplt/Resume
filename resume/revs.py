import resume

bcs = resume.DepartmentInfo.selectBy(shortname='browncs')[0]
potl = resume.ScoreCategory.get(5)

reviewers = resume.Reviewer.cSelectBy(bcs)
applicants = resume.Applicant.cSelectBy(bcs)

def getReview(app,rev):
	scv = -1
	rev = resume.Review.cSelectOne(bcs,reviewer=rev,applicant=app,draft=False)
	if rev:
		for sc in rev.scores:
			if sc.value.category.id == 7:
				return sc.value.number
	return scv

print '\n'.join(
		[','.join([str(getReview(app,rev)) for rev in reviewers])
			for app in applicants])
