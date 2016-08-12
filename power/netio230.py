#!/usr/bin/env python

import urllib2
import hashlib
from random import choice
from ansible.module_utils.basic import AnsibleModule


class netio230Error(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)
		
		
def _querycgi(url_):
	response   = urllib2.urlopen(url_)
	response_html = response.read()
	# e.g.: <html>100 HELLO</html>
	if not response_html.startswith('<html>') or not response_html.endswith('</html>'):
		raise netio230Error('Unexpected reply from netio230: ' + response_html)
	return response_html[6:-7]


def _logincgi(url_, login_, password_):
	salt = ''
	for i in range(32):
		salt += choice('0123456789abcdef')
	# http://$NETIO/cgi/control.cgi?hash=$SALT
	session_id = _querycgi(url_+'?hash='+salt)
	hashed_login = hashlib.md5(login_+password_+session_id).hexdigest()
	
	# REPLY=`$WGET "http://$NETIO/cgi/control.cgi?login=c:${LOGIN}:${PW}"`
	
	answer = _querycgi(url_+'?login=c:'+login_+':'+hashed_login)
	if answer != '100 HELLO':
		raise netio230Error('Login to netio230 failed: '+answer)

def _get_portscgi(cgiurl_):
	response_html = _querycgi(cgiurl_+'?port=list')
	return response_html.replace(' ','')

def _set_portscgi(cgiurl_, ports_):
	return _querycgi(cgiurl_+'?port='+ports_)

def _logoutcgi(cgiurl_):
	urllib2.urlopen(cgiurl_+'?quit=quit')


def main():
	module = AnsibleModule(
		argument_spec = dict(
			name     = dict(required=True, type='str'),
			cgiport  = dict(default='80'),
			login    = dict(required=True, type='str'),
			password = dict(required=True, type='str', no_log=False),
			value    = dict(required=True, type='str'),
		),
		supports_check_mode=False
	)

	new_value = module.params['value']
	name      = module.params['name']
	cgiport   = module.params['cgiport']
	login     = module.params['login']
	password  = module.params['password']
	
	try:
		if not set(new_value) <= set('01u'):
			raise netio230Error('invalid required argument: value('+new_value+') must contain 0,1 and u only.')

		cgiurl = 'http://'+name+':'+cgiport+'/cgi/control.cgi'
		_logincgi(cgiurl, login_ = login, password_ = password)
		old_value = _get_portscgi(cgiurl)
		
		# compare port stati and fix differences.
		# e.g 
		# old_value    : 0011
		#     value    : u101
		# write to dev : u10u
		write_value = ''
		changed = False
		for (old, new) in zip (old_value, new_value):
			if old == new or new == 'u':
				write_value += 'u'
			else:
				write_value += new
				changed = True
		
		if changed == True:
			_set_portscgi(cgiurl, write_value)
		
		_logoutcgi(cgiurl)
		module.exit_json(
			changed   = changed,
			old_value = old_value,
			changes   = write_value
		)
	except urllib2.URLError as err:
		module.fail_json(msg= str(err))
	except netio230Error as err:
		module.fail_json(msg = str(err))

if __name__ == "__main__":
	main()
