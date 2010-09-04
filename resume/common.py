import ssmtp
import smtplib
import random, types, time, cjson, sha
import os,time,traceback
import config


def resumeLog(txt,exc=False):
	f = open(config.resumeLog,'a');
	f.write(txt);
	if exc:
		traceback.print_exc(file=f)
	f.close()


try:
	from mod_python import apache
	from mod_python import util
except ImportError, e:
	pass

def urlEncode(instr):
	def escapeChar(ch):
		if ch.isalnum() or ch in '-_.~':
			return ch
		else:
			return '%%%02X' % ord(ch)
	return ''.join([escapeChar(ch) for ch in instr])

def convertTime(secs):
	return time.strftime("%A, %B %d, %I:%M %p",time.localtime(secs))

def condDecode(instr):
	if type(instr) is types.UnicodeType:
		return instr
	else:
		return unicode(instr,'utf8')

def condEncode(instr):
	if type(instr) is types.UnicodeType:
		return instr.encode('utf8')
	else:
		return instr

def toJSON(obj):
	return cjson.encode(obj)

class JSONobj(object):
	outputFields = ['id']

	def toJSON(self,fields=None):
		if fields == None:
			return cjson.encode(self)
		else:
			dct = {}
			for field in fields:
				dct[field] = self.__getattribute__(field)
			return cjson.encode(dct)

class genSqlJson(JSONobj):
	ctxtname = ''
	ctxtfld = ''

	@classmethod
	def cSelectBy(cls,ctxt,**kwargs):
		kwargs[cls.ctxtname] = ctxt
		return cls.selectBy(**kwargs)
	@classmethod
	def cSelectOne(cls,ctxt,**kwargs):
		rl = list(cls.cSelectBy(ctxt,**kwargs))
		if len(rl) > 0:
			return rl[0]
		else:
			return None

class EmailException(Exception):
	pass

def sendEmail(smtpServer,smtpUsername,smtpPassword,senderEmail,senderName,recipient,subject,message,logFile=None):
	if logFile:
		logFile.write('[%s] EMAIL to <%s>, SUBJECT "%s"\n' % (time.ctime(),condEncode(recipient),condEncode(subject)))
	if smtpUsername != '':
		conn = ssmtp.SMTP_SSL(smtpServer)
		conn.login(smtpUsername,smtpPassword)
	else:
		conn = smtplib.SMTP(smtpServer)
	conn.ehlo()
	amended_message=(u'From: "%s" <%s>\r\nTo: %s\r\nSubject:%s\r\n\r\n%s' % (condDecode(senderName),condDecode(senderEmail),condDecode(recipient),condDecode(subject),condDecode(message))).encode('utf8')
	try:
		conn.sendmail(condEncode(senderEmail),condEncode(recipient),amended_message)
		if logFile:
			logFile.write('[%s] FINISHED EMAIL to <%s>: ' % (time.ctime(),condEncode(recipient)))
			logFile.write('SENT OK\n')
	except smtplib.SMTPRecipientsRefused:
		if logFile:
			logFile.write('RECIPIENTS REFUSED\n')
		raise EmailException('Invalid email address. Please check the address you entered and try again.')
	except smtplib.SMTPHeloError:
		if logFile:
			logFile.write('HELO ERROR\n')
		raise EmailException('There was a problem with the email server. Please try again--if this error occurs, contact the application maintainer.')
	except smtplib.SMTPSenderRefused:
		if logFile:
			logFile.write('SENDER REFUSED\n')
		raise EmailException('There was a problem with the email server. Please try again--if this error occurs, contact the application maintainer.')
	except smtplib.SMTPDataError:
		if logFile:
			logFile.write('UNKNOWN ERROR\n')
		raise EmailException('There was a problem with the email server. Please try again--if this error occurs, contact the application maintainer.')
	conn.close()
		
class HandlerException(Exception):
	pass

class AuthException(Exception):
	pass

class HttpResult(object):
	def __init__(self,value,mimetype='text/plain',status=200,**kwargs):
		self.value = value
		self.mimetype = mimetype
		self.status = status
		self.headers = kwargs
	def send(self,req):
		req.content_type = condEncode(self.mimetype)
		req.status = self.status
		for k, v in self.headers.iteritems():
			req.headers_out[k] = v
		if req.method == 'HEAD':
			req.write('')
		else:
			req.write(self.value)

class HttpFileResult(HttpResult):
	def __init__(self,path,mimetype=None):
		self.path = path
		self.mimetype = mimetype
	def send(self,req):
		if self.mimetype:
			req.content_type = condEncode(self.mimetype)
		else:
			pl = len(self.path)
			if pl > 4 and self.path[-4:] == '.css':
				req.content_type = "text/css"
			elif pl > 3 and self.path[-3:] == '.js':
				req.content_type = "text/javascript"
			elif pl > 5 and self.path[-5:] == '.html':
				req.content_type = "text/html"
			elif pl > 4 and self.path[-4:] == '.png':
				req.content_type = 'image/png'
			elif pl > 4 and self.path[-4:] == '.jpg':
				req.content_type = 'image/jpeg'
		req.sendfile(self.path)


class RequestInfo(object):
	thisComp = property(fget=lambda s : s.comps[0])
	isFinal = property(fget=lambda s : len(s.comps) == 1)

	@classmethod
	def fromReq(cls,req,ipaddr,auser,fields,serverName):
		comps = req.uri.split('/')[len(serverName.split('/'))-2:]
		return cls(req,comps,ipaddr,auser,fields,{})
	def __init__(self,req,comps,ipaddr,auser,fields,extras):
		self.req = req
		self.comps = comps
		self.ipaddr = ipaddr
		self.auser = auser
		self.fields = fields
		self.extras = extras
	def nextSub(self):
		if self.isFinal:
			raise HandlerException('Can\'t get subpath of single-element path!')
		return RequestInfo(self.req,self.comps[1:],self.ipaddr,self.auser,self.fields,self.extras)
	def applyFields(self,meth):
		def condConvert(l):
			if isinstance(l,util.StringField):
				return str(l)
			elif isinstance(l, list):
				return [condConvert(ll) for ll in l]
			else:
				return l
		o = {}
		for k in self.fields.keys():
			o[k] = condConvert(self.fields[k])
		for k,v in self.extras.iteritems():
			o[k] = v
		o['ipaddr'] = self.ipaddr
		o['auser'] = self.auser
		o['req'] = self.req
		return apply_args(meth,**o)
	def __str__(self):
		return '/'.join(self.comps)
			
def handleFile(baseDir,ri):
	if ri.comps[-1] == '':
		ri.comps[-1] = 'index.html'
	return HttpFileResult(os.path.join(baseDir,*ri.comps))

def apply_args(meth,**kwargs):
	#Magic stolen from mod_python
	fc = meth.im_func.func_code
	expected = fc.co_varnames[1:fc.co_argcount]
	if not (fc.co_flags & 0x08):
		for name in kwargs.keys():
			if name not in expected:
				del kwargs[name]
	return meth(**kwargs)

def getResult(res):
	if isinstance(res,HttpResult):
		return res
	else:
		return HttpResult(res)

def handleClass(cls,ri):
	if ri.isFinal and cls.handlers.has_key(ri.thisComp):
		meth = cls.handlers[ri.thisComp].__get__(None,cls)
		return getResult(ri.applyFields(meth))
	else:
		raise HandlerException('URI Not Found!')
	
def handleInstance(obj,ri):
	if ri.isFinal and obj.instanceHandlers.has_key(ri.thisComp):
		meth = obj.instanceHandlers[ri.thisComp].__get__(obj,obj.__class__)
		return getResult(ri.applyFields(meth))
	else:
		raise HandlerException('URI Not Found!')

class Handler(object):
	def delegate(self,dname):
		return None
	def preHook(self,ri):
		return None
	def uniAuth(self,ri):
		return True
	def auth(self,ri):
		return True
	def handle(self,ri):
		raise HandlerException('Method Not Found!')

	def runReq(self,ri):
		self.preHook(ri)
		if not self.uniAuth(ri):
			raise AuthException('Denied')
		if not ri.isFinal:
			dgte = self.delegate(ri.comps[0])
			if dgte is not None:
				return dgte.runReq(ri.nextSub())
		if not self.auth(ri):
			raise AuthException('Denied')
		return self.handle(ri)

class FileHandler(Handler):
	def __init__(self,baseDir):
		self.baseDir = baseDir
	def handle(self,ri):
		return handleFile(self.baseDir,ri)

class ObjHandler(Handler):
	def __init__(self,underlying,authFn):
		self.underlying = underlying
		self.authFn = authFn
	def auth(self,ri):
		return self.authFn(self,ri)
	def handle(self,ri):
		return handleInstance(self.underlying,ri)

class ClassHandler(Handler):
	def __init__(self,underlying,authFn):
		self.underlying = underlying
		self.authFn = authFn
	def auth(self,ri):
		return self.authFn(self,ri)
	def handle(self,ri):
		return handleClass(self.underlying,ri)

class DictDelegateHandler(Handler):
	def __init__(self,delegates):
		self.delegates = delegates
	def delegate(self,dname):
		if self.delegates.has_key(dname):
			return self.delegates[dname]
		else:
			return None

class ExceptionHandler(object):
	def __init__(self,extype=None):
		self.extype = extype
	def runReq(self,e):
		if self.extype and isinstance(e,self.extype):
			return HttpResult('{"error":%s}' % toJSON(str(e)))
		else:
			return HttpResult('{"exception":"exception","value":%s}' % toJSON(str(e)))

class RequestProcessor(object):
	def __init__(self,serverRoot,serverName,getAuth,baseHandler,exceptionHandler,defaultMime):
		self.serverRoot = serverRoot
		self.serverName = serverName
		self.baseHandler = baseHandler
		self.exceptionHandler = exceptionHandler
		self.defaultMime = defaultMime
		self.getAuth = getAuth
	
	def log(self,txt,exc=False):
		f = open(config.resumeLog,'a');
		f.write(txt);
		if exc:
			traceback.print_exc(file=f)
		f.close()

	def handle(self,req):
		try:
			before = time.time()
			ipaddr = req.get_remote_host(apache.REMOTE_NOLOOKUP)
			fields = util.FieldStorage(req,keep_blank_values=1)
			auser = self.getAuth(fields,ipaddr,req)
			rinfo = RequestInfo.fromReq(req,ipaddr,auser,fields,self.serverName)
			result = self.baseHandler.runReq(rinfo)
			after = time.time()
			self.log("%s: Request %s took %d ms.\n" % (time.ctime(),req.uri,int((after-before)*1000)))
		except Exception,e:
			self.log("Exception in request %s: %s\n" % (req.uri, e),True)
			result = self.exceptionHandler.runReq(e)
		result.send(req)
		return apache.OK

class Authenticator(object):
	def __init__(self,usercls,cookiecls,ctxtfld):
		self.usercls = usercls
		self.cookiecls = cookiecls
		self.ctxtfld = ctxtfld

	def get_cookie(self,ipaddr,username,password,**kwargs):
		theuser = self.usercls.cSelectBy(kwargs[self.ctxtfld],username=username)
		if theuser.count():
			theuser = theuser[0]
		else:
			return 'false'
		ostensible_pwh = sha.new(password).hexdigest()
		if theuser.password_hash == ostensible_pwh:
			auth = self.cookiecls.create(ipaddr,theuser)
			return toJSON([auth.value,theuser])
		else:
			return 'false'

	def invalidate_cookie(self,ipaddr,cookie):
		cobjs = list(self.cookiecls.selectBy(ipaddr=ipaddr,value=cookie))
		if len(cobjs) > 0:
			for co in cobjs:
				co.destroySelf()
			return 'true'
		else:
			return 'false'

	def user_from_cookie(self,ipaddr,cookie=None,**kwargs):
		if cookie is None:
			raise AuthException('No User Found')	
		u = authUser(self.cookiecls,ipaddr,cookie)
		return toJSON(u)

	instanceHandlers = {
		"getCookie":get_cookie,
		"logOut":invalidate_cookie,
		"currentUser":user_from_cookie
	}

def authUser(cookiecls,ipaddr,cookie):
	if random.randint(0,100) == 0:
		exs = cookiecls.select(cookiecls.q.expires < int(time.time()))
		for ex in exs:
			ex.destroySelf()
	cobj = list(cookiecls.selectBy(ipaddr=ipaddr,value=cookie))
	if len(cobj) > 0:
		cobj = cobj[0]
		if cobj.expires >= int(time.time()):
			cobj.expires = int(time.time()) + 18000
			return cobj.user
	raise AuthException('denied')

