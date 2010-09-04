from mod_python import apache
from mod_python import util

import config,resume,common
import os,time,traceback

def authAll(self,ri):
	return True
def authAdmin(self,ri):
	return ri.auser and ri.auser.role == 'admin'
def authReviewer(self,ri):
	return ri.auser and (ri.auser.role == 'admin' or ri.auser.role == 'reviewer')
def authSubmitter(self,ri):
	return ri.auser and ri.auser.role == 'applicant'
def authUnverified(self,ri):
	if ri.isFinal:
		if ri.thisComp in ['add','verify', 'newApplicant']:
			return True
		elif ri.thisComp in ['addRev','getPending','delete']:
			return authAdmin(self,ri)
	return False
def authDept(self,ri):
	if ri.isFinal:
		if ri.thisComp in ['getBasic','style', 'image-header', 'image-logo', 'image-resume', 'image-header-bg']:
			return True
		elif ri.thisComp in ['getApplicants','getReviewers','getBatch.pdf','getReviewer']:
			return authReviewer(self,ri)
		elif ri.thisComp[-4:] == '.pdf':
			return authReviewer(self,ri)
		elif ri.thisComp in ['changeContacts','submitLetter','findRefs']:
			return authAdmin(self,ri)
	return True
def authApplicant(self,ri):
	if ri.thisComp in ['reject']:
		return authAdmin(self,ri)
	return authReviewer(self,ri)

class SubmitterHandler(common.Handler):
	def auth(self,ri):
		return authSubmitter(self,ri)
	def handle(self,ri):
		applicant = resume.Applicant.cSelectOne(ri.extras['dept'],auth=ri.auser)
		if applicant is None:
			raise common.HandlerException('Can\'t get this application!')
		if not ri.isFinal:
			raise common.HandlerException('Method Not Found!')
		if applicant.submitterHandlers.has_key(ri.thisComp):
			meth = resume.Applicant.submitterHandlers[ri.thisComp].__get__(applicant,applicant.__class__)
			return common.getResult(ri.applyFields(meth))
		else:
			raise common.HandlerException('Method Not Found!')

class ApplicantHandler(common.ObjHandler):
	def __init__(self,applicant):
		common.ObjHandler.__init__(self,applicant,authApplicant)
	def preHook(self,ri):
		ri.extras['applicant'] = self.underlying
	def uniAuth(self,ri):
		return ri.extras['dept'] == self.underlying.department
	def delegate(self,dname):
		if dname == 'Review':
			return common.ClassHandler(resume.Review,authReviewer)
		else:
			return None

class ApplicantsHandler(common.Handler):
	def delegate(self,dname):
		app = resume.Applicant.get(int(dname))
		return ApplicantHandler(app)

class DepartmentHandler(common.ObjHandler,common.DictDelegateHandler):
	def __init__(self,underlying):
		common.ObjHandler.__init__(self,underlying,authDept)
		common.DictDelegateHandler.__init__(self,
			{'Auth':common.ObjHandler(common.Authenticator(resume.AuthInfo,resume.AuthCookie,'dept'),authAll),
			'Submitter':SubmitterHandler(),
			'Applicant':ApplicantsHandler(),
			'AuthInfo':common.ClassHandler(resume.AuthInfo,authAll),
			'UnverifiedUser':common.ClassHandler(resume.UnverifiedUser,authUnverified),
			'ScoreCategory':common.ClassHandler(resume.ScoreCategory,authAdmin),
			'ScoreValue':common.ClassHandler(resume.ScoreValue,authAdmin),
			'Area':common.ClassHandler(resume.Area,authAdmin),
			'Admins': common.ClassHandler(resume.Admins,authAdmin),
			'ApplicantPosition': 
				common.ClassHandler(resume.ApplicantPosition,authAdmin),
			'Reference':common.ClassHandler(resume.Reference,authAll)})
	def preHook(self,ri):
		ri.extras['dept'] = self.underlying
	def uniAuth(self,ri):
		return (ri.auser is None) or ri.extras['dept'].id == ri.auser.departmentID
	def handle(self,ri):
		if ri.isFinal and ri.thisComp == '':
			return common.HttpFileResult(os.path.join(config.serverRoot,'static','login.html'))
		if ri.isFinal:
			try:
				return common.ObjHandler.handle(self,ri)
			except common.HandlerException:
				pass
			if ri.thisComp[:7] == 'letter-' and ri.thisComp[-4:] == '.pdf':
				return common.getResult(ri.extras['dept'].handle_getLetter(id=int(ri.thisComp[7:-4])))
		return common.handleFile(os.path.join(config.serverRoot,'static'),ri)

class BaseHandler(common.Handler):
	def delegate(self,dname):
		dept = resume.DepartmentInfo.selectBy(shortname=dname)
		if dept.count() == 0:
			return None
		return DepartmentHandler(dept[0])
	def handle(self,ri):
		if ri.isFinal and ri.thisComp == 'startDemo':
			return common.getResult(resume.DepartmentInfo.handle_startDemo())
		elif ri.isFinal:
			dept = resume.DepartmentInfo.selectBy(shortname=ri.thisComp)
			if dept.count() > 0:
				return common.HttpResult('Moved Permanently',status=301,Location=ri.req.uri+'/')
			if ri.thisComp == '':
				return common.HttpFileResult(os.path.join(config.serverRoot,'static-base','index.html'))
		return common.handleFile(os.path.join(config.serverRoot,'static-base'),ri)

def handler(req):
	def authfn(fields,ipaddr,req):
		if fields.has_key('cookie'):
			return common.authUser(resume.AuthCookie,ipaddr,str(fields['cookie']))
		else:
			return None
	return common.RequestProcessor(config.serverRoot,config.serverName,authfn,BaseHandler(),common.ExceptionHandler(resume.ResumeException),'text/plain').handle(req)
