import threading
import unittest
from compcontrol.broker import Broker, BrokerError, DemoExecutor


class SpyExecutor:
    def __init__(self):
        self.actions = []
    def execute(self, action, gate, valid):
        def dispatch():
            self.actions.append(action)
            return {'status':'executed', 'message':'test'}
        return gate(dispatch)


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.executor = SpyExecutor()
        self.now = 0
        self.broker = Broker(self.executor, clock=lambda:self.now)
    def pending(self):
        return self.broker.plan('open calculator')['approval_id']
    def test_plan_cannot_execute(self):
        self.pending()
        self.assertFalse(self.executor.actions)
    def test_approval_exactly_once(self):
        id = self.pending()
        self.broker.confirm(id)
        with self.assertRaises(BrokerError): self.broker.confirm(id)
        self.assertEqual(len(self.executor.actions),1)
    def test_cancel_expire_replace_pause_clear(self):
        for mutation in ('cancel','expire','replace','pause','clear'):
            self.broker.pause(False)
            id = self.pending()
            if mutation=='cancel': self.broker.cancel(id)
            if mutation=='expire': self.now += 121
            if mutation=='replace': self.broker.plan('time')
            if mutation=='pause': self.broker.pause(True)
            if mutation=='clear': self.broker.clear()
            with self.assertRaises(BrokerError): self.broker.confirm(id)
        self.assertFalse(self.executor.actions)
    def test_invalid_request_revokes_previous(self):
        id = self.pending()
        with self.assertRaises(ValueError): self.broker.plan('x'*2000)
        with self.assertRaises(BrokerError): self.broker.confirm(id)
    def test_concurrent_confirm_and_pause_native_dialog(self):
        entered, release = threading.Event(), threading.Event()
        spy = self.executor
        class Waiting:
            def execute(self, action, gate, valid):
                entered.set(); release.wait(3)
                return spy.execute(action, gate, valid)
        self.broker.executor = Waiting()
        id = self.pending(); outcomes=[]
        thread=threading.Thread(target=lambda:outcomes.append(self.broker.confirm(id)))
        thread.start(); self.assertTrue(entered.wait(2))
        try:
            with self.assertRaises(BrokerError): self.broker.confirm(id)
            self.broker.pause(True)
        finally:
            release.set();thread.join(3)
        self.assertFalse(spy.actions)
        self.assertEqual(outcomes[0]['status'],'cancelled')
    def test_failure_consumes_token_and_redacts_exception(self):
        class Bad:
            def execute(self,*args): raise RuntimeError('PRIVATE SECRET')
        self.broker.executor=Bad();id=self.pending()
        with self.assertRaises(BrokerError) as e: self.broker.confirm(id)
        self.assertNotIn('PRIVATE',str(e.exception))
        with self.assertRaises(BrokerError): self.broker.confirm(id)
    def test_activity_metadata_bounded(self):
        for _ in range(80):self.broker.plan('search for private customer name')
        data=self.broker.state()
        self.assertLessEqual(len(data['activity']),60)
        self.assertNotIn('private customer',str(data))
    def test_demo_cannot_execute(self):
        b=Broker(DemoExecutor(),demo=True)
        p=b.plan('open calculator')
        self.assertEqual(b.confirm(p['approval_id'])['status'],'simulated')
