import io
import json
import unittest
from unittest.mock import Mock
from compcontrol.providers import ProviderConfig, TextProvider, ProviderError, NoRedirect, LIMIT


class ProviderTests(unittest.TestCase):
    def config(self,kind='ollama',url='http://127.0.0.1:11434'):
        return ProviderConfig(kind,url,'test-model','test-secret')
    def test_invalid_urls(self):
        for cfg in (self.config(url='http://localhost:11434'),self.config(url='https://evil.com'),
                    self.config(url='http://127.0.0.1:11434/?x=1'),self.config('openai','http://api.example.com'),
                    self.config('openai','https://key:secret@example.com'),self.config('openai','https://example.com/#x')):
            with self.assertRaises(ProviderError):cfg.validate()
    def test_secrets_not_public_or_repr(self):
        cfg=self.config('openai','https://api.example.com/v1')
        self.assertNotIn('test-secret',repr(cfg));self.assertNotIn('test-secret',str(cfg.public()))
    def test_chat_is_explicit_text_only(self):
        transport=Mock();transport.open.return_value=io.BytesIO(json.dumps({'message':{'content':'open calculator'}}).encode())
        p=TextProvider(self.config(),transport)
        self.assertEqual(p.answer('hi'),'open calculator')
        request=transport.open.call_args.args[0];payload=json.loads(request.data)
        self.assertNotIn('tools',payload);self.assertNotIn('Authorization',request.headers)
        self.assertEqual(payload['messages'][-1],{'role':'user','content':'hi'})
    def test_openai_auth_is_only_transport(self):
        transport=Mock();transport.open.return_value=io.BytesIO(b'{"choices":[{"message":{"content":"hello"}}]}')
        p=TextProvider(self.config('openai','https://api.example.com/v1'),transport)
        self.assertEqual(p.answer('hi'),'hello')
        req=transport.open.call_args.args[0]
        self.assertEqual(req.full_url,'https://api.example.com/v1/chat/completions')
        self.assertEqual(req.headers['Authorization'],'Bearer test-secret')
        self.assertNotIn('test-secret',req.data.decode())
    def test_size_limit_and_bad_shape(self):
        for response in (b'x'*(LIMIT+1),b'{}',b'[]',b'not-json'):
            transport=Mock();transport.open.return_value=io.BytesIO(response)
            with self.assertRaises(ProviderError):TextProvider(self.config(),transport).answer('hi')
    def test_redirect_blocked(self):
        with self.assertRaises(ProviderError):NoRedirect().redirect_request(None,None,302,'',{},'https://evil')
    def test_off_never_calls_network(self):
        transport=Mock()
        with self.assertRaises(ProviderError):TextProvider(ProviderConfig(),transport).answer('hi')
        transport.open.assert_not_called()
