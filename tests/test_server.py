import http.client
import json
import threading
import unittest
from unittest.mock import patch
from compcontrol.server import AppServer


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=AppServer(('127.0.0.1',0),demo=True)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.origin=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path='/api/state',body=None,headers=None,auth=True):
        h={'Origin':self.origin}
        if auth:h['Authorization']='Bearer '+self.server.token
        if body is not None:h['Content-Type']='application/json'
        h.update(headers or {})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h)
        r=conn.getresponse();result=(r.status,r.read(),dict(r.getheaders()));conn.close();return result
    def test_no_auth(self):self.assertEqual(self.request(auth=False)[0],401)
    def test_bad_origin(self):self.assertEqual(self.request(headers={'Origin':'https://evil.com'})[0],403)
    def test_bad_host(self):self.assertEqual(self.request(headers={'Host':'evil.com'})[0],403)
    def test_null_origin(self):self.assertEqual(self.request(body={},headers={'Origin':'null'})[0],403)
    def test_client_cannot_inject_actions(self):
        status,_,_=self.request('/api/plan',{'text':'help','actions':[{'kind':'shell'}]})
        self.assertEqual(status,400)
    def test_full_approval_roundtrip(self):
        status,data,_=self.request('/api/plan',{'text':'open Spotify and play sad Hindi songs'})
        self.assertEqual(status,200);plan=json.loads(data)
        self.assertTrue(plan['destinations'][0].startswith('spotify:search:'))
        status,data,_=self.request('/api/confirm',{'approval_id':plan['approval_id']})
        self.assertEqual(status,200);self.assertEqual(json.loads(data)['status'],'simulated')
        self.assertEqual(self.request('/api/confirm',{'approval_id':plan['approval_id']})[0],409)
    def test_demo_disables_ai(self):
        self.assertFalse(json.loads(self.request()[1])['provider']['enabled'])
        self.assertEqual(self.request('/api/chat',{'text':'hi','consent':True})[0],422)
    def test_no_traversal_and_csp(self):
        self.assertEqual(self.request('/../providers.py')[0],404)
        status,body,headers=self.request('/',auth=False)
        self.assertEqual(status,200);self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline',headers['Content-Security-Policy'])
    def test_real_mode_external_bind_denied(self):
        with self.assertRaises(ValueError):AppServer(('0.0.0.0',0))
    def test_local_mode_token_not_in_html_and_no_iframe(self):
        with patch('compcontrol.server.platform.system',return_value='Windows'):
            local=AppServer(('127.0.0.1',0))
        thread=threading.Thread(target=local.serve_forever,daemon=True);thread.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',local.server_port);conn.request('GET','/')
            r=conn.getresponse();html=r.read()
            self.assertNotIn(local.token.encode(),html)
            self.assertEqual(r.getheader('X-Frame-Options'),'DENY')
            self.assertFalse(local.allowed_host('localhost:'+str(local.server_port)))
            self.assertFalse(local.allowed_host('8765-sandbox.e2b.app'))
            conn.close()
        finally:local.shutdown();local.server_close();thread.join()
