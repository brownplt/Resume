from sqlobject import *
from common import *
from tex import texEscape
from pdftk import PDF
import common
import config
import sha, time, random, types, tempfile, os
import resumetext

coverTemplate = open(config.serverRoot + '/cover_template.tex','r').read()
blankPDFPath = config.serverRoot + '/blank.pdf'

serverRoot = config.serverRoot

if config.usedb == 'mysql':
	__connection__ = connectionForURI('mysql://%s:%s@localhost/%s?charset=utf8&sqlobject_encoding=utf8' % (config.dbuser,config.dbpass,config.dbname))
elif config.usedb == 'sqlite':
	__connection__ = connectionForURI('sqlite:%s' % config.dbloc)

def sendLogEmail(*args,**kwargs):
	lf = file(config.emailLog,'a')
	kwargs['logFile'] = lf
	sendEmail(*args,**kwargs)
	lf.close()

genders = [
	'Unknown',
	'Male',
	'Female']
ethnicities = {
	'am':'American Indian or Alaskan Native',
	'as':'Asian or Pacific Islander',
	'b':'Black, non-Hispanic',
	'h':'Hispanic',
	'w':'White, non-Hispanic',
	'zo':'Other',
	'zu':'Unknown'}

# Errors that should be impossible to get
class ResumeFatalException(Exception):
	pass

# Errors that users may get, that should be displayed client-side
class ResumeException(Exception):
	pass

class FileUploadException(ResumeException):
	pass

def saveFile(fstr,prefix):
	try:
		os.remove(os.path.join(config.uploadPath,'%s-pdf' % prefix))
	except OSError,e:
		pass
	if fstr[0:4] == '%PDF':
		outfile = open(os.path.join(config.uploadPath,'%s-pdf' % prefix),'w')
		outfile.write(fstr)
		outfile.close()
	elif fstr[0:8] == '\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
		outfile = open(os.path.join(config.uploadPath,'%s-doc' % prefix),'w')
		outfile.write(fstr)
		outfile.close()
		os.system('antiword -a letter %s > %s' % (
			os.path.join(config.uploadPath,'%s-doc' % prefix),
			os.path.join(config.uploadPath,'%s-pdf' % prefix)))
	else:
		raise FileUploadException('The file you uploaded is neither a PDF nor a Word document.')

class SqlJson(genSqlJson):
	ctxtname = 'department'
	ctxtfld = 'dept'

class ScoreCategory(SQLObject, SqlJson):
	class sqlmeta:
		cacheValues = False
	name = UnicodeCol(dbEncoding='utf8')
	shortform = UnicodeCol(dbEncoding='utf8')
	department = ForeignKey('DepartmentInfo')
	values = MultipleJoin('ScoreValue',joinColumn='category_id')
	
	outputFields = ['id','name','shortform','values']

	@classmethod
	def handle_delete(cls,dept,id):
		self = cls.cSelectOne(dept,id=int(id))
		if not self:
			raise ResumeFatalException('No ScoreCategory to delete!')
		ret = toJSON(self)
		for value in self.values:
			for score in Score.cSelectBy(dept,value=value):
				score.destroySelf()
			value.destroySelf()
		self.destroySelf()
		return ret

	@classmethod
	def handle_change(cls,dept,id,name,shortform):
		self = cls.cSelectOne(dept,id=int(id))
		if not self:
			raise ResumeFatalException('No ScoreCategory to change!')
		self.name = name
		self.shortform = shortform
		return toJSON(self)

	@classmethod
	def handle_add(cls,dept,name,shortform,minval,maxval):
		k = cls(name=name,shortform=shortform,department=dept)
		for x in range(int(minval),int(maxval)+1):
			ScoreValue(category=k,department=dept,explanation='',number=x)
		return toJSON(k)

	handlers = {'add' : handle_add,
				'delete' : handle_delete,
				'change' : handle_change}

class ScoreValue(SQLObject, SqlJson):
	class sqlmeta:
		cacheValues = False
		defaultOrder = 'number'

	category = ForeignKey('ScoreCategory')
	number = IntCol()
	explanation = UnicodeCol(dbEncoding='utf8')
	department=ForeignKey('DepartmentInfo')

	outputFields = ['id','number','explanation']

	@classmethod
	def handle_change(cls,dept,id,explanation):
		self = cls.cSelectOne(dept,id=int(id))
		if not self:
			raise ResumeFatalException('No ScoreValue to change!')
		self.explanation = explanation
		return toJSON(self)
	
	handlers = {'change' : handle_change}

class Score(SQLObject, SqlJson):
	class sqlmeta:
		cacheValues = False
	value = ForeignKey('ScoreValue')
	review = ForeignKey('Review')
	department = ForeignKey('DepartmentInfo')

	outputFields = ['id','valueID']

# Stores the position that a candidate is applying for. E.g. 
# 'Assistant Professor' or 'Professor'.  The autoemail field
# denotes whether requests for letters of reference should be sent 
# automatically.
class ApplicantPosition(SQLObject, SqlJson):
	class sqlmeta:
		cacheValues = False

	department = ForeignKey('DepartmentInfo')
	name = UnicodeCol(dbEncoding='utf8')
	shortform = UnicodeCol(dbEncoding='utf8')
	autoemail = BoolCol()

	outputFields = [ 'id','name', 'shortform', 'autoemail' ]	


	@classmethod 
	def handle_add(cls,dept,name,shortform,autoemail):
		if autoemail == 'true':
			return cls(department=dept,name=name,shortform=shortform,autoemail=True)
		elif autoemail == 'false':
			return cls(department=dept,name=name,shortform=shortform,autoemail=False)
		else:
			raise ResumeException('invalid argument (autoemail)')
	
	handlers = { 'add' : handle_add }

class Area(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False
	name = UnicodeCol(dbEncoding='utf8')
	abbr = UnicodeCol(dbEncoding='utf8')
	department = ForeignKey('DepartmentInfo')

	applicants = RelatedJoin('Applicant')

	outputFields = ['id','name','abbr']

	@classmethod
	def handle_add(cls,dept,name,abbr):
		return cls(name=name,abbr=abbr,department=dept).toJSON()

	@classmethod
	def handle_delete(cls,dept,id):
		k = cls.cSelectOne(dept,id=int(id))
		if k:
			for a in k.applicants:
				a.removeArea(k)
				dept.updateLastChange(a)
			k.destroySelf()
			return toJSON(int(id))
		else:
			raise ResumeFatalException('No Area with That ID!')

	handlers = {
			'add': handle_add,
			'delete': handle_delete
			}

class Highlight(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False
	applicant = ForeignKey('Applicant')
	highlightee = ForeignKey('Reviewer')
	department = ForeignKey('DepartmentInfo')
	highlighteeName = property(fget = lambda self : self.highlightee.uname)

	outputFields=['id','applicantID','highlighteeID','highlighteeName']

class Review(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False
		defaultOrder = 'ord'
	applicant = ForeignKey('Applicant')
	reviewer = ForeignKey('Reviewer')
	ord = IntCol(default=0)
	advocate = EnumCol(enumValues=['advocate','detract','none','comment'],default='none')
	comments = UnicodeCol(dbEncoding='utf8')
	draft = BoolCol()
	department = ForeignKey('DepartmentInfo')
	scores = MultipleJoin('Score')

	scoreValues = property(fget = lambda self : [x.valueID for x in self.scores])
	reviewerName = property(fget = lambda self : self.reviewer.uname)
	
	outputFields = ['id','applicantID','reviewerName','scoreValues','comments','ord','advocate']
	
	@classmethod
	def handle_submit(cls,dept,applicant,auser,advdet,comments,draft,scores=[]):
		revr = Reviewer.cSelectOne(dept,authID=auser.id)
		if not revr:
			raise ResumeFatalException(str(dept.id))
			raise ResumeFatalException('Only reviewers can review applicants!')
		def fillReview(scores,advdet,comments,draft):
			urev = Review.cSelectOne(dept,applicant=applicant,reviewer=revr,draft=draft)
			if urev:
				urev.comments = comments
				urev.advocate = str(advdet)
				for s in urev.scores:
					s.destroySelf()
			else:
				urev = Review(department=dept,applicant=applicant,reviewer=revr,comments=comments,advocate=str(advdet),draft=draft)
			for s in scores:
				Score(valueID=s,review=urev,department=dept)
		if scores == '':
			scores = []
		elif not isinstance(scores,list):
			scores = [scores]
		scores = [int(s) for s in scores]
		fillReview(scores,advdet,comments,True)
		if draft != 'yes':
			fillReview(scores,advdet,comments,False)
			dept.updateLastChange(applicant)
		return applicant.handle_get()

	@classmethod
	def handle_get(cls,dept,applicant,auser):
		revr = Reviewer.cSelectOne(dept,auth=auser)
		if not revr:
			raise ResumeFatalException('Only reviewers can review applicants!')
		draft = Review.cSelectOne(dept,applicant=applicant,reviewer=revr,draft=True)
		if draft:
			return toJSON(draft)
		else:
			return 'false'

	@classmethod
	def handle_revert(cls,dept,applicant,auser):
		revr = Reviewer.cSelectOne(dept,auth=auser)
		if not revr:
			raise ResumeFatalException('Only reviewers can review applicants!')
		draft = Review.cSelectOne(dept,applicant=applicant,reviewer=revr,draft=True)
		sub = Review.cSelectOne(dept,applicant=applicant,reviewer=revr,draft=False)
		if draft:
			if sub:
				for score in draft.scores:
					score.destroySelf()
				for score in sub.scores:
					Score(valueID=score.valueID,review=draft,department=dept)
				draft.comments = sub.comments
				draft.advocate = str(sub.advocate)
				return toJSON(draft)
			else:
				draft.destroySelf()
				return 'false'
		else:
			return 'false'

	handlers = {
			"submit" : handle_submit,
			"get" : handle_get,
			"revert" : handle_revert
			}

class Reviewer(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False
	auth = ForeignKey('AuthInfo')
	email = property(fget = lambda self : self.auth.email)
	name = property(fget = lambda self : self.auth.name)
	uname = property(fget = lambda self : self.auth.username)
	role = property(fget = lambda self : self.auth.role)
	numrevs = property(fget = lambda self : len([x for x in Review.cSelectBy(self.department,draft=False,reviewerID=self.id) if x.advocate != 'comment']))
	department = ForeignKey('DepartmentInfo')
	hiddens = RelatedJoin('Applicant',addRemoveName='Hidden',intermediateTable='rev_app_hide')

	outputFields = ['id','name','uname','email','role','numrevs']


class Reference(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False

	code = IntCol()
	applicant = ForeignKey('Applicant')
	submitted = IntCol()
	submittedStr = property(fget = lambda self: convertTime(self.submitted))
	filesize = IntCol()
	name = UnicodeCol(dbEncoding='utf8')
	institution = UnicodeCol(dbEncoding='utf8')
	email = UnicodeCol(dbEncoding='utf8')
	department = ForeignKey('DepartmentInfo')
	appname = property(fget = lambda s : s.applicant.name)
	lastRequested = IntCol(default=0)
	lastRequestedStr = property(fget = lambda self:convertTime(self.lastRequested))
	
	outputFields = ['id','appname','name','institution','email','submitted',
									'lastRequested','lastRequestedStr']

	def toDict(self,showReceivedInfo):
	  dict = { 'id': self.id, 'appname': self.appname, 'name': self.name,
	           'institution': self.institution, 'email': self.email }
	  if showReceivedInfo:
	    dict['submitted'] = self.submitted
	    dict['lastRequested'] = self.lastRequested
	    dict['lastRequestedStr'] = self.lastRequestedStr
	  return dict

	def sendReferenceRequest(self):
		try:
			sendLogEmail(config.smtpServer,config.smtpUsername,config.smtpPassword,
				self.department.contactEmail,self.department.contactName,self.email,
				u'Letter of Reference: %s' % self.applicant.name,
				resumetext.makeReferenceRequest(
					applicantName=self.applicant.name,
					referenceName=condDecode(self.name),
					serverName=config.serverName,
					deptName=self.department.name,
					deptShortName=self.department.shortname,
					letterCode=self.code))
			self.lastRequested = int(time.time())
			self.department.updateLastChange(self.applicant)
		except EmailException, e:
			raise ResumeException(str(e))

	@classmethod
	def handle_getFromCode(cls,dept,code):
		ref = cls.cSelectOne(dept,code=int(code))
		if not ref:
			raise ResumeException('This code does not match any letter writing request. Please make sure you have the correct URL.')
		return ref.toJSON(['id','appname','name','submitted','submittedStr','filesize'])

	def doSubmit(self,letter):
		if isinstance(letter,types.StringType):
			raise ResumeException('Please select a file to upload.')
		try:
			saveFile(letter.value,'ref-%d' % self.code)
			self.submitted = int(time.time())
			self.filesize = len(letter.value)
			self.department.updateLastChange(self.applicant)
			sendLogEmail(config.smtpServer,config.smtpUsername,config.smtpPassword,self.department.contactEmail,self.department.contactName,self.email,u'Reference Submitted: %s' % self.applicant.name,
(u"""Dear %(name)s,

Your letter of reference for %(appname)s has been submitted successfully. In
order to update your submission, you may continue to visit the URL:

%(servername)s/%(deptname)s/letter.html?code=%(code)d
		
[This message was generated automatically by the Resume faculty
recruiting system.]

%(orgname)s""" % {'appname':self.applicant.name,'name':condDecode(self.name),'servername':config.serverName,'deptname':self.department.shortname,'code':self.code,'orgname':self.department.name}))
		except EmailException, e:
			raise ResumeException(str(e))
		return None
		
	@classmethod
	def handle_submit(cls,dept,code,letter):
		ref = cls.cSelectOne(dept,code=int(code))
		if not ref:
			raise ResumeException('The code you have used is invalid. Please check the URL you are using, or contact the administrator.')
		ref.doSubmit(letter)
		return ref.toJSON(['id','appname','name','submitted','submittedStr','filesize'])

	@classmethod
	def handle_getList(cls,dept,email):
		refinfo = u'\n'.join([u'%s:    %s/%s/letter.html?code=%d' % (ref.applicant.name,config.serverName,dept.shortname,ref.code)
					for ref in  cls.cSelectBy(dept,email=email)])
		if len(refinfo) == 0:
			raise ResumeException('You do not appear to have any references connected to that email address.')
		try:
			sendLogEmail(config.smtpServer,config.smtpUsername,config.smtpPassword,dept.contactEmail,dept.contactName,email,'Letter of Reference',
u"""Dear %s,

You have been asked to write the following letters of reference for the
%s.

In order to submit each letter, please visit the accompanying URL.

%s

If you have trouble with this procedure, visit
%s/%s/contact.html
for information on contacting the server administrator.
		
[This message was generated automatically by the Resume faculty
recruiting system.]

%s""" % (ref.name,dept.name,refinfo,config.serverName,dept.shortname,dept.name))
		except EmailException, e:
			raise ResumeException(str(e))
		return 'true'

	handlers = {"submit" 	: handle_submit,
				"getFromCode" : handle_getFromCode,
				"getList"	: handle_getList}

class ComponentType(SQLObject, SqlJson):
	class sqlmeta:
		cacheValues = False
	type = EnumCol(enumValues=['contactlong','contactshort','contactweb','statement'])
	name = UnicodeCol(dbEncoding='utf8')
	short = UnicodeCol(dbEncoding='utf8')
	department = ForeignKey('DepartmentInfo')

	outputFields = ['id','type','name','short']

# Dummy class of methods that require reviewer authorization.
class Admins:

	@classmethod
	def handle_requestReference(cls,id):
		reference = Reference.get(id=id)
		if reference == None:
			raise ResumeException('Invalid reference')

		reference.sendReferenceRequest()
		return 'true'

	handlers = { "requestReference": handle_requestReference }

class Component(SQLObject, SqlJson):
	class sqlmeta:
		cacheValues = False
	applicant = ForeignKey('Applicant')
	type = ForeignKey('ComponentType')
	value = UnicodeCol(dbEncoding='utf8')
	lastSubmitted = IntCol()
	lastSubmittedStr = property(fget = lambda self: convertTime(self.lastSubmitted))
	department = ForeignKey('DepartmentInfo')

	outputFields = ['id','typeID','value','lastSubmitted','lastSubmittedStr']

class Applicant(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False
	json = UnicodeCol(default='')
	auth = ForeignKey('AuthInfo')
	gender = EnumCol(enumValues = genders,default='Unknown')
	ethnicity = EnumCol(enumValues = ethnicities.keys(),default='zu')
	rejected = BoolCol(default=False)
	rtime = IntCol(default=0)
	firstname =  UnicodeCol(dbEncoding='utf8')
	lastname =  UnicodeCol(dbEncoding='utf8')
	email = property(fget = lambda self : self.auth.email)
	name = property(fget = lambda self : self.firstname + u' ' + self.lastname)
	uname = property(fget = lambda self : self.auth.username)
	ethname = property(fget = lambda self : ethnicities[self.ethnicity])
	department = ForeignKey('DepartmentInfo')
	areas = RelatedJoin('Area')
	hiddens = RelatedJoin('Reviewer',addRemoveName='Hidden',intermediateTable='rev_app_hide')
	components = MultipleJoin('Component')
	areviews = MultipleJoin('Review')
	references = MultipleJoin('Reference')
	highlights = MultipleJoin('Highlight')
	position = ForeignKey('ApplicantPosition')

	reviews = property(fget = lambda s : [r for r in s.areviews if not r.draft])
	hiddenunames = property(fget = lambda s : [x.uname for x in s.hiddens])
	refletters = property(fget = lambda s : [{'id':x.id,'name':x.name,'institution':x.institution,'email':x.email,'submitted':x.submitted,'lastRequested': x.lastRequested, 'lastRequestedStr': x.lastRequestedStr} for x in s.references])
	
	outputFields = ['id','gender','ethnicity','position','ethname','name','uname','email','components','areas','reviews','refletters','highlights','rejected','hiddenunames', 'firstname', 'lastname']

	def handle_get(self):
		return self.toJSON()

	def getJSON(self,auser):
		def getReviews():
			return [{'id':r.reviewerID,
					'rname':r.reviewerName,
					'svals':r.scoreValues} for r in self.areviews if ((not r.draft) and (r.advocate != 'comment'))]
		def getComments():
			return [{'id':r.reviewerID,
					 'rname':r.reviewerName} for r in self.areviews if ((not r.draft) and (r.advocate == 'comment'))]
		def getWeb():
			return [{'name':x.type.short,'value':x.value} for x in self.components if (x.value != '' and x.type.type == 'contactweb')]
		def getStatements():
			return [x.type.id for x in self.components if x.type.type=='statement' and x.lastSubmitted != 0]
		if self.json == '':
			self.json = toJSON(
					{'id':self.id,
					 'gender':self.gender,
           'position': self.position.id,
					 'ethname':self.ethname,
					 'name':self.name,
					 'areas':self.areas,
					 'refletters':self.refletters,
					 'rejected':self.rejected,
           'firstname': self.firstname,
           'lastname': self.lastname,
					 'reviews':getReviews(),
					 'comments':getComments(),
					 'web':getWeb(),
					 'statements':getStatements()})
		return self.json
	def namesort(self):
		return self.lastname.lower(),self.firstname.lower()

	def handle_highlight(self,highlightee):
		rev = Reviewer.cSelectOne(self.department,id=int(highlightee))
		if not rev:
			raise ResumeFatalException('Reviewer being referenced does not exist!')
		h = Highlight.cSelectOne(self.department,applicantID=self.id,highlighteeID=rev.id)
		if not h:
			h = Highlight(department=self.department,applicant=self,highlightee=rev)
		self.department.updateLastChange(self)
		return self.handle_get()
	def handle_unhighlight(self,auser):
		rev = Reviewer.cSelectOne(self.department,authID=auser.id)
		if not rev:
			raise ResumeFatalException('User is not a reviewer!')
		for h in Highlight.cSelectBy(self.department,applicantID=self.id,highlighteeID=rev.id):
			h.destroySelf()
		self.department.updateLastChange(self)
		return self.handle_get()
	def handle_hide(self,auser,hide):
		rev = Reviewer.cSelectOne(self.department,authID=auser.id)
		if not rev:
			raise ResumeFatalException('User is not a reviewer!')
		if hide == 'no':
			if rev in self.hiddens:
				self.removeHidden(rev)
		elif hide == 'yes':
			if rev not in self.hiddens:
				self.addHidden(rev)
		self.department.updateLastChange(self)
		return self.handle_get()
	def handle_reject(self,reject):
		self.rejected = (reject == 'yes')
		if self.rejected:
			self.rtime = int(time.time())
		self.department.updateLastChange(self)
		return self.handle_get()
	def handle_setAreas(self,areas=[]):
		if areas == '':
			areas = []
		elif isinstance(areas,types.StringType):
			areas = [areas]
		areas = [int(a) for a in areas]
		for a in self.areas:
			self.removeArea(a)
		for a in areas:
			ar = Area.cSelectOne(self.department,id=a)
			if ar:
				self.addArea(ar)
		self.department.updateLastChange(self)
		return self.handle_get()
	
	def handle_setGender(self,gender):
		if gender in genders:
			self.gender = gender
			self.department.updateLastChange(self)
		return self.handle_get()
	def handle_setEthnicity(self,ethnicity):
		if ethnicity in ethnicities.keys():
			self.ethnicity = ethnicity
			self.department.updateLastChange(self)
		return self.handle_get()

	def handle_setPosition(self,id):
		position = ApplicantPosition.cSelectOne(self.department,id=id)
		if not position:
			raise ResumeException('invalid position specified')
		self.position = position
		self.department.updateLastChange(self)
		return self.handle_get()

	def handle_submitStatement(self,comp,newcomp):
		ct = ComponentType.cSelectOne(self.department,id=int(comp))
		if (ct == None) or (ct.type != 'statement'):
			raise ResumeFatalException('No Statement Type With That ID.')
		if isinstance(newcomp,types.StringType):
			raise ResumeException('No file uploaded.')
		saveFile(newcomp.value,'%d-%d' % (self.id,ct.id))
		oldcomp = Component.cSelectOne(self.department,applicant=self,type=ct)
		if oldcomp:
			oldcomp.lastSubmitted = int(time.time())
			oldcomp.value = str(len(newcomp.value))
		else:
			Component(applicant=self,type=ct,value=str(len(newcomp.value)),lastSubmitted=int(time.time()),department=self.department)
		self.department.updateLastChange(self)
		return '{"component":%s,"app":%s}' % (toJSON(ct.name),self.toJSON(['id','name','email','components','areas','references']))
	def handle_getStatement(self,comp):
		ct = ComponentType.cSelectOne(self.department,id=int(comp))
		if (ct == None) or (ct.type != 'statement'):
			raise ResumeFatalException('No Statement Type With That ID!')
		comp = Component.cSelectOne(self.department,applicant=self,type=ct)
		if comp:
			return HttpFileResult(os.path.join(config.uploadPath,'%d-%d-pdf' % (self.id,ct.id)),'application/pdf')
		else:
			raise ResumeFatalException('Statement Not Yet Submitted!')

	def rmCombined(self):
		try:
			os.remove(os.path.join(config.uploadPath,'%d-combined-pdf' % self.id))
		except OSError, e:
			pass

	def makeCombined(self):
		if os.access(os.path.join(config.uploadPath,'%d-combined-pdf' % self.id),os.F_OK):
			return os.path.join(config.uploadPath,'%d-combined-pdf' % self.id)
		cts = ComponentType.cSelectBy(self.department,type='statement')
		lcomps = []
		ltrs = [os.path.join(config.uploadPath,'ref-%d-pdf' % r.code) for r in self.references if r.submitted]
		for ct in cts:
			comp = Component.cSelectOne(self.department,applicant=self,type=ct)
			if comp:
				lcomps.append(os.path.join(config.uploadPath,'%d-%d-pdf' % (self.id,ct.id)))
		lcomps.reverse()
		tdir = tempfile.mkdtemp()
		tfile = open(os.path.join(tdir,'o.tex'),'w')
		
		def getRevTex(rev):
			def getAdv():
				if rev.advocate == 'comment':
					return ' (comment)'
				elif rev.advocate == 'advocate':
					return ' (advocate)'
				elif rev.advocate == 'detract':
					return ' (detract)'
				else:
					return ''
			def getRscores():
				if rev.advocate == 'comment' or len(rev.scores) == 0:
					return ''
				else:
					return ', '.join(['%s: %d' % (texEscape(sc.value.category.shortform),sc.value.number) for sc in rev.scores])
			return '{\\bf %s} %s %s\n\n%s\n\n' % (texEscape(rev.reviewer.auth.username), getRscores(), getAdv(), texEscape(rev.comments))
		tfile.write(coverTemplate
		% (
			texEscape(self.name),
			texEscape(self.email),
			'\n\n'.join(['{\\bf %s:} %s' % 
				(texEscape(c.type.name), texEscape(c.value)) for c in self.components if c.type.type != 'statement']),
			'\n\n'.join(texEscape(a.name) for a in self.areas),
			'\n\\medskip\n'.join([getRevTex(rev) for rev in self.reviews])))
		tfile.close()
		os.system('pdflatex -output-directory %s %s' % (tdir,os.path.join(tdir,'o.tex')))
		os.system('pdftk %s %s cat output %s dont_ask' % 
				(os.path.join(tdir,'o.pdf'),' '.join(lcomps+ltrs),os.path.join(config.uploadPath,'%d-combined-pdf' % self.id)))
		os.system('rm -r %s' % tdir)
		if not os.access(os.path.join(config.uploadPath,'%d-combined-pdf' % self.id),os.F_OK):
			raise ResumeFatalException('The combined PDF for this applicant could not be created because of PDF errors.')
		return os.path.join(config.uploadPath,'%d-combined-pdf' % self.id)
	def handle_getCombined(self):
		return HttpFileResult(self.makeCombined(),'application/pdf')
	def handle_submitContactInfo(self,**kwargs):
		for key, val in kwargs.iteritems():
			if key.find('comp-') == 0:
				ct = ComponentType.cSelectOne(self.department,id=int(key[5:]))
				if ct:
					oldcomp = Component.cSelectOne(self.department,applicant=self,type=ct)
					if oldcomp:
						oldcomp.value = val
						oldcomp.lastSubmitted = int(time.time())
					else:
						Component(applicant=self,type=ct,value=val,lastSubmitted=int(time.time()),department=self.department)
		self.department.updateLastChange(self)
		return 'true'

	# Application information for applicants
	def handle_getApp(self):
	  dict = { 'id': self.id, 'name': self.name, 'email': self.email,
             'position': self.position,
	           'components': self.components, 'areas': self.areas, 
	           'references': 
	             map(lambda ref: ref.toDict(self.position.autoemail),
	                 self.references) }
	  return cjson.encode(dict)
	
	def handle_requestReference(self,name,institution,email):
		if Reference.cSelectOne(self.department,applicant=self,email=email):
			raise ResumeException('You have already asked this person to write you a letter. If you wish to contact this person, please do so outside the Resume system.')
		if name == '':
			raise ResumeException('No name was provided, please provide a name for the letter writer')
		if institution == '':
			raise ResumeException('No institution was provided, please provide a name for the institution')
		if email == '':
			raise ResumeException('No email was provided, please provide an email for the reference request')
		Ncode = random.randint(0,999999999)
		ref = Reference(code = ncode,applicant = self,submitted=0,filesize=0,
			name=name,institution=institution,email=email,department=self.department)
		self.department.updateLastChange(self)
		if self.position.autoemail:
			ref.sendReferenceRequest()
		return ref.toJSON()


	submitterHandlers = {"get"				: handle_getApp,
						"submitContactInfo" : handle_submitContactInfo,
						"submitStatement" 	: handle_submitStatement,
						"requestReference"	: handle_requestReference}
						
	instanceHandlers = {"getStatement.pdf" 	: handle_getStatement,
						"getCombined.pdf"  	: handle_getCombined,
						"setAreas"			: handle_setAreas,
						"setGender"			: handle_setGender,
						"setPosition"	: handle_setPosition,
						"setEthnicity"		: handle_setEthnicity,
						"get"				: handle_get,
						"highlight"			: handle_highlight,
						"unhighlight"		: handle_unhighlight,
						"hide"				: handle_hide,
						"reject"			: handle_reject}

class UnverifiedUser(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False
	email = UnicodeCol(dbEncoding='utf8')
	name = UnicodeCol(dbEncoding='utf8')
	role = EnumCol(enumValues=['applicant','reviewer','admin'])
	verify = IntCol()
	department = ForeignKey('DepartmentInfo')

	outputFields = ['id','name','email','role']

	@classmethod
	def add(cls,dept,email,role,name):
		verify = random.randint(0,999999999)
		ea = AuthInfo.cSelectOne(dept,email=email)
		if ea:
			raise ResumeException('A user with that email address already exists.')
		#TODO: better email!
		if role == 'applicant':
			emailstr = u"""Dear Applicant,

In order to continue the application process with Resume, please visit the URL:

%(servername)s/%(deptname)s/newapp.html?verify=%(vfy)d

To return to your application once you have created an account, you must log in
at:

%(servername)s/%(deptname)s/login.html

If you have trouble with this procedure, visit
%(servername)s/%(deptname)s/contact.html
for information on contacting the server administrator.
		
[This message was generated automatically by the Resume faculty
recruiting system.]

%(orgname)s"""
		else:
			emailstr = u"""Dear %(name)s,

A new Resume account is being created for you. To select a username and password, please visit:

%(servername)s/%(deptname)s/verify.html?verify=%(vfy)d&app=n

To login after your account has been created, you can go to:

%(servername)s/%(deptname)s/login.html

[This message was generated automatically by the Resume faculty
recruiting system.]

%(orgname)s"""
		try:
			sendLogEmail(config.smtpServer,config.smtpUsername,config.smtpPassword,dept.contactEmail,dept.contactName,email,u'%s Job Search Account' % dept.name,
				emailstr % {'name':condDecode(name),'servername':config.serverName,'deptname':dept.shortname,'vfy':verify,'orgname':dept.name})
			uu = UnverifiedUser(department=dept,email=email,name=name,verify=verify,role=role)
		except EmailException, e:
			raise ResumeException(str(e))
		return toJSON(uu)

	# Handle new applicants
	@classmethod
	def handle_add(cls,dept,email):
		return cls.add(dept,email,'applicant',u'')

	@classmethod
	def handle_addRev(cls,dept,email,role,name):
		return cls.add(dept,email,role,name)

	@classmethod
	def handle_verify(cls,dept,verify,username,password,position,
										gender='Unknown',ethnicity='zu'):
		ve = cls.cSelectOne(dept,verify=int(verify))
		if not ve:
			raise ResumeException('Resume can\'t find any user associated with this URL who hasn\'t yet activated their account. Please check that the URL you have entered is correct, or try requesting an account again.')
		usn = list(AuthInfo.cSelectBy(dept,username=username))
		if len(usn) > 0:
			raise ResumeException('That username is already in use. Please select another.')

		ai = AuthInfo(department=dept,
				username=username,
				password_hash=condEncode(sha.new(password).hexdigest()),
				email=condEncode(ve.email),
				name=condEncode(ve.name),
				role=condEncode(ve.role)
				)
		if ve.role == 'applicant':
			applicantPosition = ApplicantPosition.cSelectOne(dept,id=position)
			if not applicantPosition:
				raise ResumeException('Internal error: position specified incorrectly')
			ap = Applicant(department=dept,auth=ai,gender=gender,
						position=applicantPosition,ethnicity=ethnicity)
		else:
			rev = Reviewer(department=dept,auth=ai)
		for uvu in UnverifiedUser.cSelectBy(dept,email=ai.email):
			uvu.destroySelf()
		dept.updateLastChange()
		return '{}'
	
	@classmethod
	def handle_newApplicant(cls,dept,verify,username,password,position,
										firstname,lastname,
										gender='Unknown',ethnicity='zu'):
		ve = cls.cSelectOne(dept,verify=int(verify))
		if not ve:
			raise ResumeException('Resume can\'t find any user associated with this URL who hasn\'t yet activated their account. Please check that the URL you have entered is correct, or try requesting an account again.')
		usn = list(AuthInfo.cSelectBy(dept,username=username))
		if len(usn) > 0:
			raise ResumeException('That username is already in use. Please select another.')
		if ve.role != 'applicant':
			raise ResumeFatalException("You have reached this page in error; " +
				"please contact the system administrator (reviewer on newapp.html)")

		ai = AuthInfo(department=dept,
				username=username,
				password_hash=condEncode(sha.new(password).hexdigest()),
				email=condEncode(ve.email),
				name=condEncode(ve.name),
				role=condEncode(ve.role)
				)
		applicantPosition = ApplicantPosition.cSelectOne(dept,id=position)
		if not applicantPosition:
			raise ResumeFatalException('You have reached this page in error. '
				+ 'Please contact the system administrator (position unspecified)')
		ap = Applicant(department=dept,auth=ai,gender=gender,firstname=firstname,
						lastname=lastname,position=applicantPosition,ethnicity=ethnicity)
		
		for uvu in UnverifiedUser.cSelectBy(dept,email=ai.email):
			uvu.destroySelf()
		dept.updateLastChange()
		return '{}'

	@classmethod
	def handle_getPending(cls,dept):
		return toJSON([x for x in cls.select() if x.role != 'applicant'])

	@classmethod
	def handle_delete(cls,dept,id):
		self = cls.cSelectOne(dept,id=int(id))
		if not self:
			raise ResumeException('That unverified user no longer exists.')
		x = toJSON(self)
		self.destroySelf()
		return x

	handlers = {"add"	: handle_add,
				"addRev" : handle_addRev,
				"verify": handle_verify,
				"newApplicant": handle_newApplicant,
				"getPending" : handle_getPending,
				"delete" : handle_delete}

class AuthInfo(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False
	username = UnicodeCol(dbEncoding='utf8')
	password_hash = UnicodeCol(dbEncoding='utf8')
	email = UnicodeCol(dbEncoding='utf8')
	name = UnicodeCol(dbEncoding='utf8')
	role = EnumCol(enumValues=['applicant','reviewer','admin'])
	verify = IntCol(default=0)
	department = ForeignKey('DepartmentInfo')

	outputFields = ['id','username','role']

	@classmethod
	def handle_resetPassword(cls,dept,email):
		au = cls.cSelectOne(dept,email=email)
		if not au:
			raise ResumeException('No user with the email address "%s" exists.' % email)
		pverify = random.randint(1,999999999)
		try:
			sendLogEmail(config.smtpServer,config.smtpUsername,config.smtpPassword,dept.contactEmail,dept.contactName,email,u'%s Job Search: Change Password' % dept.name,
u"""There has been a password change request for your %(orgname)s job search
account with username "%(uname)s". To enter a new password, or to cancel this
request, please go to

%(servername)s/%(deptname)s/chpwd.html?uid=%(uid)d&verify=%(vfy)d

[This message was generated automatically by the Resume faculty
recruiting system.]
""" % {'servername':config.serverName,'deptname':dept.shortname,
	'name':au.name,'uid':au.id,'uname':au.username,'vfy':pverify,'orgname':dept.name})
		except EmailException, e:
			raise ResumeException(str(e))
		au.verify = pverify
		return '{}'

	@classmethod
	def handle_cancelChange(cls,dept,id,verify):
		self = cls.cSelectOne(dept,id=int(id))
		if not (self.verify == int(verify)):
			raise ResumeException('This URL is no longer valid.')
		else:
			self.verify = 0
			
	@classmethod
	def handle_getFromVfy(cls,dept,id,verify):
		self = cls.cSelectOne(dept,id=int(id))
		if not (self.verify == int(verify)):
			raise ResumeException('This URL is no longer valid.')
		return toJSON(self)

	@classmethod
	def handle_changePassword(cls,dept,id,password,verify):
		self = cls.cSelectOne(dept,id=int(id))
		if not (self.verify == int(verify)):
			raise ResumeException('This URL is no longer valid.')
		self.password_hash = sha.new(password).hexdigest()
		self.verify = 0
		return toJSON(self)
	
	handlers = {"resetPassword"	: handle_resetPassword,
				"getFromVfy" : handle_getFromVfy,
				"changePassword" : handle_changePassword,
				"cancelChange"	: handle_cancelChange}

class AuthCookie(SQLObject):
	class sqlmeta:
		cacheValues = False
	value = UnicodeCol(dbEncoding='utf8')
	ipaddr = UnicodeCol(dbEncoding='utf8')
	user = ForeignKey('AuthInfo')
	expires = IntCol()

	@classmethod
	def create(cls,ipaddr,theuser):
		hval = sha.new("%d%s%s" % (random.randint(0,999999999),ipaddr,theuser.username)).hexdigest()
		return cls(value=hval,ipaddr=ipaddr,userID=theuser.id,expires=int(time.time())+1800)

class DepartmentInfo(SQLObject,SqlJson):
	class sqlmeta:
		cacheValues = False
	name = UnicodeCol(dbEncoding='utf8')
	shortname = UnicodeCol(dbEncoding='utf8')
	lastChange = IntCol()
	headerImage = UnicodeCol(dbEncoding='utf8')
	logoImage = UnicodeCol(dbEncoding='utf8')
	resumeImage = UnicodeCol(dbEncoding='utf8')
	headerBgImage = UnicodeCol(dbEncoding='utf8')
	brandColor = UnicodeCol(dbEncoding='utf8')
	contactName = UnicodeCol(dbEncoding='utf8')
	contactEmail = UnicodeCol(dbEncoding='utf8')
	techEmail = UnicodeCol(dbEncoding='utf8')
	outputFields = ['name','shortname','contactName','contactEmail','techEmail']

	def handle_getStyle(self):
		return HttpResult(
		"""
body { 
	background: %(brandColor)s;
}

div.bottom {
	background: %(brandColor)s;
}

h2 {
	color: %(brandColor)s;
}
""" % {'brandColor':self.brandColor},mimetype='text/css')

	def sendImage(self,field):
		imagePath = os.path.join(config.serverRoot,field)
		return HttpFileResult(imagePath)
	def handle_headerImage(self):
		return self.sendImage(self.headerImage)
	def handle_logoImage(self):
		return self.sendImage(self.logoImage)
	def handle_resumeImage(self):
		return self.sendImage(self.resumeImage)
	def handle_headerBgImage(self):
		return self.sendImage(self.headerBgImage)

	def handle_changeContacts(self,contactName,contactEmail,techEmail):
		self.contactName = contactName
		self.contactEmail = contactEmail
		self.techEmail = techEmail
		return '{}'

	def updateLastChange(self,applicant=None):
		self.lastChange = int(time.time())
		if applicant == 'all':
			for a in Applicant.cSelectBy(self):
				a.json = ''
				a.rmCombined()
		elif applicant:
			applicant.json = ''
			applicant.rmCombined()

	def handle_getBasic(self):
		return toJSON(
			{'areas':list(Area.cSelectBy(self)),
			 'positions': list(ApplicantPosition.cSelectBy(self)),
			 'components':list(ComponentType.cSelectBy(self)),
			 'info':self,
			 'genders':genders,
			 'ethnicities':ethnicities,
			 'scores':list(ScoreCategory.cSelectBy(self))})
	
	def handle_submitLetter(self,id,letter):
		ltr = Reference.cSelectOne(self,id=int(id))
		if not ltr:
			raise ResumeFatalException('Letter does not exist!')
		elif ltr.submitted:
			raise ResumeFatalException('Letter has already been submitted!')
		ltr.doSubmit(letter)
		return ltr.toJSON()
	
	def handle_getLetter(self,id):
		ltr = Reference.cSelectOne(self,id=int(id))
		if not ltr:
			raise ResumeFatalException('Letter does not exist!')
		elif not ltr.submitted:
			raise ResumeFatalException('Cannot get that letter: it has not yet been submitted!')
		else:
			return HttpFileResult(os.path.join(config.uploadPath,'ref-%d-pdf' % ltr.code),'application/pdf')
	
	def handle_getBatch(self,req,apps=[]):
		names = []
		if not isinstance(apps,list):
			apps = [apps]
		fnames = [app.makeCombined() for app in [Applicant.cSelectOne(self,id=int(aid)) for aid in apps] if app is not None]
		fh,fn = tempfile.mkstemp()
		os.close(fh)

		def insertBlank(path):
			if PDF(path=path).numPages % 2 == 1:
				return [path, blankPDFPath]
			else:
				return [path]

		# Python doesn't have append / concat?
		bundlesAndBlanks = reduce(lambda x, y: x + y, map(insertBlank,fnames), [ ])
		
		os.system('pdftk %s cat output %s dont_ask' % 
				(' '.join(bundlesAndBlanks),fn))
		req.content_type = 'application/pdf'
		req.sendfile(fn)
		os.system('rm %s' % fn)
		return HttpResult('',mimetype='application/pdf')
	
	def handle_getApplicants(self,auser,lastChangeVal):
		if int(lastChangeVal) == self.lastChange:
			return '{"changed":false}'
		else:
			al = list(Applicant.cSelectBy(self))
			al.sort(key=lambda s : s.namesort())
			return '{"changed":true,"lastChange":%d,"value":[%s]}' % (self.lastChange,','.join(a.getJSON(auser) for a in al))
	
	def handle_getReviewers(self):
		return toJSON(list(Reviewer.cSelectBy(self)))

	def handle_findRefs(self,email):
		return toJSON([{'appname':x.applicant.name,'appid':x.applicantID,'appemail':x.applicant.email} for x in Reference.cSelectBy(self,email=email)])

	def handle_getReviewer(self,auser):
		rev = Reviewer.cSelectOne(self,auth=auser)
		if not rev:
			raise ResumeFatalException('User is not a reviewer!')
		return toJSON({'auth':rev.auth,
						'hiddens':[x.id for x in rev.hiddens],
						'highlights':[x.applicantID for x in Highlight.cSelectBy(self,highlightee=rev)]})

	def destroy(self):
		allTableClasses = [Area,Review,Reviewer,Reference,ComponentType,Component,Applicant,UnverifiedUser,AuthInfo,ScoreCategory,ScoreValue]
		for c in Component.cSelectBy(self):
			if c.type.type == 'statement':
				os.remove(os.path.join(config.uploadPath,'%d-%d-pdf' % (c.applicant.id,c.type.id)))
		for r in Reference.cSelectBy(self):
			if r.submitted:
				os.remove(os.path.join(config.uploadPath,'ref-%d-pdf' % r.code))
		for a in Applicant.cSelectBy(self):
			a.rmCombined()
		for cl in allTableClasses:
			for obj in cl.cSelectBy(self):
				obj.destroySelf()
		self.destroySelf()

	@classmethod
	def startDept(cls,deptname,	shortname,
			adminname, adminemail, adminusername, techemail,
			headerImage, logoImage,	resumeImage, headerBgImage,
			brandColor):
		dept = cls(name=deptname,shortname=shortname,lastChange=int(time.time()),
				headerImage=headerImage,
				logoImage=logoImage,
				resumeImage=resumeImage,
				headerBgImage=headerBgImage,
				brandColor=brandColor,
				contactName=adminname,
				contactEmail=adminemail,
				techEmail=techemail
				)
		def genRandChar():
			x = random.randint(0,61)
			if x < 10:
				return chr(x+48)
			elif x < 36:
				return chr(x+55)
			else:
				return chr(x+61)
		password = ''.join([genRandChar() for x in range(8)])
		ai = AuthInfo(department=dept, name=adminname, username=adminusername,email=adminemail,role='admin',
				password_hash = sha.new(password).hexdigest())
		aa = Reviewer(department=dept,auth=ai)

		ApplicantPosition(department=dept, name='Assistant Professor',
			shortform='AsstProf', autoemail = True)
		
		ComponentType(department=dept,type='statement',name='Cover Letter',short='Cover')
		ComponentType(department=dept,type='statement',name='Curriculum Vitae',short='CV')
		ComponentType(department=dept,type='statement',name='Research Statement',short='Research')
		ComponentType(department=dept,type='statement',name='Teaching Statement',short='Teaching')
		ComponentType(department=dept,type='contactweb',name='Web Page',short='home')
		ComponentType(department=dept,type='contactweb',name='Application Web Page',short='app')
		ComponentType(department=dept,type='contactshort',name='Home Phone',short='homephone')
		ComponentType(department=dept,type='contactshort',name='Work Phone',short='workphone')
		ComponentType(department=dept,type='contactshort',name='Mobile Phone',short='mobilephone')
		ComponentType(department=dept,type='contactlong',name='Postal Address',short='postal')

		return password

	@classmethod
	def handle_startDemo(cls):
		try:
			for dept in cls.select():
				if dept.shortname[:4] == 'demo':
					if int(time.time()) - int(dept.shortname[5:]) > 3600:
						dept.destroy()
		except OSError, e:
			resumeLog('Error (I/O) while deleting content for expired demos: '
				+ e.__str__())
			
		
		deptname = 'demo-%d' % int(time.time())
		dept = cls(name='Demo Department',shortname=deptname,lastChange=int(time.time()),
				headerImage='static/images/demo-header.png',
				logoImage='static/images/demo-logo.png',
				resumeImage='static/images/demo-resume.png',
				headerBgImage='static/images/demo-bg.png',
				brandColor='#0f2847',
				contactName='Mr. Singh',
				contactEmail='noreply@example.com',
				techEmail='arjun@cs.brown.edu')
		
		ApplicantPosition(department=dept, name='Assistant Professor',
			shortform='AsstProf', autoemail = True)

		ScoreCategory.handle_add(dept,'Overall','Ov',1,10)

		cl = ComponentType(department=dept,type='statement',name='Cover Letter',short='Cover')
		cv = ComponentType(department=dept,type='statement',name='Curriculum Vitae',short='CV')
		rs = ComponentType(department=dept,type='statement',name='Research Statement',short='Research')
		ts = ComponentType(department=dept,type='statement',name='Teaching Statement',short='Teaching')
		web = ComponentType(department=dept,type='contactweb',name='Web Page',short='home')
		app = ComponentType(department=dept,type='contactweb',name='Application Web Page',short='app')
		hp = ComponentType(department=dept,type='contactshort',name='Home Phone',short='homephone')
		wp = ComponentType(department=dept,type='contactshort',name='Work Phone',short='workphone')
		mp = ComponentType(department=dept,type='contactshort',name='Mobile Phone',short='mobilephone')
		pa = ComponentType(department=dept,type='contactlong',name='Postal Address',short='postal')
	
		firstnames = [
			'Reginald','Bertie','Mabel','Egbert','Charlie','Dahlia','Tom','Bonzo','Angela','George','Agatha','Spenser','Thomas','Percy','Florence','Edwin','Zenobia','Willoughby','Henry','Emily','Claude','Eustace','Maud','Harold','Cyril','Francis','Rupert','Freddie','Marmaduke','Myrtle','Seabury','Bruce','Alexander','Muriel','Augustus','Hildebrand','Bingo','Gussie','Rosie','Algernon','Mortimer'
			]
		lastnames = [
			'Wooster','Travers','Gregson','Craye','Wilberforce','Scholfield','Anstruther','Bassington-Bassington','Bickersteth','Biffen','Bingham','Bullivant','Vickers','Chuffnell','Corcoran','Worple','Fink-Nottle','Fittleworth','Glossop','Herring','Little','Potter-Pirbright','Sipperley','Pringle','Moon','Rockmetteller','Bassett','Spode','Braythwayt','Pendlebury','Stoker','Wickhammersley','Worplesdon','Witherspoon','Brinkley','Morehead','Upjohn','Tomlinson','Mainwaring','Heppenstall','Psmith','Jellicoe','Stone','Robinson','Rossiter','Bickersdyke','Waller','Preble','Jackson','Brady','Jarvis','Ukridge','Lawlor','Previn','Derrick','Twitleston','Ickenham','Chugwater','Bleke','Paradene','Pilbeam'
			]
	
		reviewers = [
			('jeeves','Reginald Jeeves'),
			('bingley','Rupert Bingley'),
			('maple','Mr. Maple'),
			('mulready','Mr. Mulready'),
			('oakshott','Mr. Oakshott'),
			('purvis','Mr. Purvis'),
			('seppings','Mr. Seppings'),
			('waterbury','Mr. Waterbury')]
		for un,fn in reviewers:
			ai = AuthInfo(department = dept, name=fn, username=un,password_hash = sha.new('').hexdigest(),email='demo@example.com',role='admin')
			aa = Reviewer(department=dept,auth=ai)
			if un == 'jeeves':
				ai.role = 'admin'

		sys = Area(department=dept,name='Systems',abbr='Sys')
		ml = Area(department=dept,name='Machine Learning',abbr='ML')
		pl = Area(department=dept,name='Programming Languages',abbr='PL')
		db = Area(department=dept,name='Databases',abbr='DB')
		gr = Area(department=dept,name='Graphics',abbr='Graph')
		areas = [sys,ml,pl,db,gr]

		for ln in lastnames:
			firstname = random.choice(firstnames)
			ai = AuthInfo(department=dept,name='%s %s' % (firstname,ln),username=ln,password_hash = sha.new('').hexdigest(),email='goingonit@gmail.com',role='applicant')
			aa = Applicant(department=dept,auth=ai, firstname=firstname, 
						lastname=ln,
						position = ApplicantPosition.cSelectOne(dept,
												shortform='AsstProf'))
			aa.gender = random.choice(genders)
			aa.ethnicity = random.choice(ethnicities.keys())
			for area in areas:
				if random.randint(1,10) < 3:
					aa.addArea(area)
			Component(applicant=aa,type=wp,value='401-555-1234',lastSubmitted=int(time.time()),department=dept)
			Component(applicant=aa,type=hp,value='401-555-4321',lastSubmitted=int(time.time()),department=dept)
			Component(applicant=aa,type=mp,value='401-555-9876',lastSubmitted=int(time.time()),department=dept)
			Component(applicant=aa,type=web,value='http://www.example.com/~me/',lastSubmitted=int(time.time()),department=dept)
			Component(applicant=aa,type=app,value='http://www.example.com/~me/app',lastSubmitted=int(time.time()),department=dept)
			Component(applicant=aa,type=pa,value='123 Fake St\nSometown, USA 55555',lastSubmitted=int(time.time()),department=dept)
			os.system('ln %s %s' % (os.path.join(serverRoot,'demoutils','sample-cover.pdf'),os.path.join(config.uploadPath,'%d-%d-pdf' % (aa.id, cl.id))))
			Component(applicant=aa,type=cl,value='100',lastSubmitted=int(time.time()),department=dept)
			os.system('ln %s %s' % (os.path.join(serverRoot,'demoutils','sample-cv.pdf'),os.path.join(config.uploadPath,'%d-%d-pdf' % (aa.id, cv.id))))
			Component(applicant=aa,type=cv,value='100',lastSubmitted=int(time.time()),department=dept)
			os.system('ln %s %s' % (os.path.join(serverRoot,'demoutils','sample-research.pdf'),os.path.join(config.uploadPath,'%d-%d-pdf' % (aa.id, rs.id))))
			Component(applicant=aa,type=rs,value='100',lastSubmitted=int(time.time()),department=dept)
			os.system('ln %s %s' % (os.path.join(serverRoot,'demoutils','sample-teaching.pdf'),os.path.join(config.uploadPath,'%d-%d-pdf' % (aa.id, ts.id))))
			Component(applicant=aa,type=ts,value='100',lastSubmitted=int(time.time()),department=dept)
			for r in range(3):
				rr = Reference(code=random.randint(0,1000000),applicant=aa,submitted=0,filesize=0,name = 'Professor %d' % (r+1),institution='Podunk U.',email='something@example.com',department=dept)
				if random.randint(0,10) > 2:
					os.system('cp %s %s' % (os.path.join(serverRoot,'demoutils','sample-letter.pdf'),os.path.join(config.uploadPath,'ref-%d-pdf' % rr.code)))
					rr.submitted = int(time.time())
					rr.filesize = 100
		return deptname
	
	instanceHandlers = {
			'getBasic':handle_getBasic,
			'getApplicants':handle_getApplicants,
			'getReviewers':handle_getReviewers,
			'style':handle_getStyle,
			'image-header':handle_headerImage,
			'image-logo':handle_logoImage,
			'image-resume':handle_resumeImage,
			'image-header-bg':handle_headerBgImage,
			'changeContacts':handle_changeContacts,
			'submitLetter':handle_submitLetter,
			'getBatch.pdf':handle_getBatch,
			'findRefs':handle_findRefs,
			"getReviewer":handle_getReviewer}

def initDB():
	tblClasses = [UnverifiedUser,Area,Review,Reviewer,Reference,ComponentType,Component,Applicant,AuthInfo,AuthCookie,DepartmentInfo,Highlight,Score,ScoreCategory,ScoreValue,ApplicantPosition]
	for c in tblClasses:
		c.dropTable(ifExists=True)
		c.createTable()
