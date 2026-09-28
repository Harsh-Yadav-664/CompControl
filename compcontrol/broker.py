"""One-use expiring approvals. All execution passes through this boundary."""
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass

from .actions import destination, validate
from .models import Plan
from .planner import plan_request


class BrokerError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


class DemoExecutor:
    def execute(self, action, gate, valid):
        return gate(lambda: {'status': 'simulated', 'message': 'Preview only — no browser, app or media key was opened. '
                'Run CompControl on Windows for real desktop actions.'})


@dataclass(frozen=True)
class Pending:
    id: str
    plan: Plan
    expires: float


class Broker:
    def __init__(self, executor, *, demo=False, clock=time.monotonic, ttl=120):
        self.executor = executor
        self.demo = demo
        self.clock, self.ttl = clock, ttl
        self.pending = None
        self.paused = False
        self._lock = threading.Lock()
        self._execution_lock = threading.Lock()
        self._events = deque(maxlen=60)
        self._counter = 0
        self._generation = 0

    def _record(self, title, status):
        self._counter += 1
        # Metadata only. No prompts, URLs, search queries, AI messages or credentials.
        self._events.appendleft({'id': self._counter, 'title': title, 'status': status,
                                 'time': time.strftime('%H:%M')})

    def _expire(self):
        if self.pending and self.clock() >= self.pending.expires:
            self._record(self.pending.plan.title, 'expired')
            self.pending = None

    def state(self):
        with self._lock:
            self._expire()
            return {'paused': self.paused, 'activity': list(self._events),
                    'pending_id': self.pending.id if self.pending else None,
                    'busy': self._execution_lock.locked()}

    def plan(self, text, browser='default'):
        with self._lock:
            # New requests invalidate old approvals, even if parsing fails.
            if self.pending:
                self._record(self.pending.plan.title, 'superseded')
                self.pending = None
            if self._execution_lock.locked():
                raise BrokerError('Finish the Windows approval dialog before sending another request.')
            plan = plan_request(text, browser)
            for action in plan.actions:
                validate(action)
            if len(plan.actions) > 1:
                raise BrokerError('Multi-action execution is disabled.')
            result = plan.to_dict()
            result['destinations'] = [destination(a) for a in plan.actions]
            result['approval_id'] = None
            result['expires_in'] = 0
            if plan.actions:
                if self.paused:
                    raise BrokerError('Actions are paused. Resume explicitly to create an approval.')
                pending = Pending(secrets.token_urlsafe(24), plan, self.clock() + self.ttl)
                self.pending = pending
                result.update(approval_id=pending.id, expires_in=self.ttl)
                self._record(plan.title, 'awaiting approval')
            return result

    def confirm(self, approval_id):
        if not self._execution_lock.acquire(blocking=False):
            raise BrokerError('Another approval is being processed.')
        try:
            with self._lock:
                self._expire()
                if self.paused:
                    raise BrokerError('Actions are paused.')
                if not self.pending or not secrets.compare_digest(self.pending.id, approval_id):
                    raise BrokerError('Approval expired, was cancelled, or is no longer current.')
                pending, self.pending = self.pending, None  # consume before external side effects
                generation = self._generation
            try:
                def valid():
                    with self._lock:
                        return not self.paused and generation == self._generation and self.clock() < pending.expires

                def gate(dispatch):
                    # This locked check is the commit point. Once committed, the single OS
                    # dispatch cannot be recalled. Do not hold policy lock across OS calls.
                    with self._lock:
                        if self.paused or generation != self._generation or self.clock() >= pending.expires:
                            return {'status': 'cancelled', 'message': 'Approval expired or was revoked while waiting. Nothing was dispatched.'}
                    return dispatch()
                outcome = self.executor.execute(pending.plan.actions[0], gate, valid)
            except Exception as exc:
                with self._lock:
                    self._record(pending.plan.title, 'failed')
                # Do not reflect arbitrary OS exceptions, private paths or provider data.
                from .actions import ActionError
                message = str(exc) if isinstance(exc, ActionError) else 'Action failed. No automatic retry was attempted.'
                raise BrokerError(message, 422) from exc
            with self._lock:
                self._record(pending.plan.title, outcome['status'])
            return outcome
        finally:
            self._execution_lock.release()

    def cancel(self, approval_id):
        with self._lock:
            self._expire()
            if self.pending and secrets.compare_digest(self.pending.id, approval_id):
                self._record(self.pending.plan.title, 'cancelled')
                self.pending = None
                return {'message': 'Cancelled. No action was dispatched.'}
            raise BrokerError('This approval is no longer pending.')

    def pause(self, enabled):
        with self._lock:
            self.paused = enabled
            self._generation += 1
            if enabled:
                self.pending = None
            self._record('Action control', 'paused' if enabled else 'resumed')
            return {'paused': enabled, 'message': 'Paused. Pending approvals cleared. '
                    'An action already dispatched cannot be recalled; decline any open Windows dialog.'
                    if enabled else 'Actions resumed. Each action still needs approval.'}

    def clear(self):
        with self._lock:
            self.pending = None
            self._generation += 1
            self._events.clear()
        return {'message': 'Session activity and pending approval cleared.'}
