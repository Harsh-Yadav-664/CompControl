"""One-use expiring approvals and fast-path execution broker. All execution passes through this boundary."""
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass

from .actions import collect_system_telemetry, destination, validate
from .consent import classify_risk, requires_native_popup
from .models import Action, Plan
from .planner import clean, plan_request


class BrokerError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


class DemoExecutor:
    def execute(self, action, gate, valid):
        def _sim():
            if action.kind == 'system_control' and action.target in {
                'system_info', 'network_status', 'battery_status', 'disk_space', 'top_processes'
            }:
                info = collect_system_telemetry(action.target)
                return {
                    'status': 'simulated',
                    'message': f'{info}\n\n(Preview mode — desktop mutations are simulated.)',
                }
            dest = destination(action) if action.kind not in {'installed_app', 'workspace_patch'} else action.target
            return {
                'status': 'simulated',
                'message': f'Executed in simulation mode: {action.kind} → {dest}\n'
                           'Run CompControl natively on Windows for live desktop execution.',
            }
        return gate(_sim)


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
        self._interpretation = None

    def _record(self, title, status):
        self._counter += 1
        # Metadata only. No prompts, URLs, search queries, AI messages or credentials.
        self._events.appendleft({
            'id': self._counter,
            'title': title,
            'status': status,
            'time': time.strftime('%H:%M'),
        })

    def _expire(self):
        if self.pending and self.clock() >= self.pending.expires:
            self._record(self.pending.plan.title, 'expired')
            self.pending = None

    def state(self):
        with self._lock:
            self._expire()
            return {
                'paused': self.paused,
                'activity': list(self._events),
                'pending_id': self.pending.id if self.pending else None,
                'busy': self._execution_lock.locked(),
            }

    def _invalidate(self):
        self._generation += 1
        self._interpretation = None
        if self.pending:
            self._record(self.pending.plan.title, 'superseded')
        self.pending = None

    def invalidate(self):
        """Input/browser edits revoke old work without erasing activity."""
        with self._lock:
            self._invalidate()

    def _offer(self, plan, source='local'):
        if not isinstance(plan, Plan) or not isinstance(plan.actions, tuple):
            raise BrokerError('Invalid plan.')
        if plan.intent:
            if plan.actions or plan.intent not in {'find_app', 'file_workspace'} or clean(plan.query, 300) != plan.query:
                raise BrokerError('Invalid follow-up intent.')
        elif plan.query:
            raise BrokerError('Unexpected follow-up query.')
        if len(plan.actions) > 1:
            raise BrokerError('Multi-action execution is disabled.')
        for action in plan.actions:
            validate(action)

        risk = classify_risk(plan.actions[0]) if plan.actions else 'none'
        popup_needed = requires_native_popup(plan.actions[0]) if plan.actions else False

        result = plan.to_dict()
        result.update(
            destinations=[
                self.executor.describe(a) if a.kind in {'installed_app', 'workspace_patch'} else destination(a)
                for a in plan.actions
            ],
            approval_id=None,
            expires_in=0,
            source=source,
            risk=risk,
            requires_popup=popup_needed,
        )
        if plan.actions:
            if self.paused:
                raise BrokerError('Actions are paused. Resume explicitly to create an approval.')
            pending = Pending(secrets.token_urlsafe(24), plan, self.clock() + self.ttl)
            self.pending = pending
            result.update(approval_id=pending.id, expires_in=self.ttl)
            self._record(plan.title, 'awaiting approval')
        return result

    def plan(self, text, browser='default'):
        with self._lock:
            self._invalidate()
            if self._execution_lock.locked():
                raise BrokerError('Finish the Windows approval dialog before sending another request.')
            return self._offer(plan_request(text, browser))

    def select_app(self, token):
        """Native picker entry. Prepares a verified launch plan."""
        with self._lock:
            self._invalidate()
            if self.demo or self._execution_lock.locked():
                raise BrokerError('App selection is unavailable in demo mode or during approval.')
            try:
                target = self.executor.catalog.get(token)
            except Exception:
                raise BrokerError('App selection expired or could not be resolved. Scan and select it again.') from None
            from .executable_target import ExecutableTarget
            is_executable = isinstance(target, ExecutableTarget)
            if not is_executable and not target.packaged:
                raise BrokerError('Classic Start-menu shortcuts may hide arguments. Select the actual .exe instead.')
            name = target.name
            note = (
                'Launching locally observed Windows application registration.'
                if not is_executable else
                'Launching selected local executable with your Windows user permissions.'
            )
            return self._offer(Plan('Launch ' + name, note, (Action('installed_app', token),)))

    def offer_patch_export(self, token):
        """Native UI only: exact reviewed patch destination, one-use approval."""
        with self._lock:
            self._invalidate()
            if self.demo or self._execution_lock.locked():
                raise BrokerError('Patch export is unavailable in demo mode or during approval.')
            return self._offer(Plan(
                'Export reviewed patch',
                'Creates a new patch outside the project. Original files remain unchanged.',
                (Action('workspace_patch', token),),
            ))

    def begin_interpretation(self):
        with self._lock:
            self._invalidate()
            if self.demo:
                raise BrokerError('AI is disabled in demo mode.')
            if self.paused or self._execution_lock.locked():
                raise BrokerError('Resume actions and finish any approval before asking AI to plan.')
            ticket = secrets.token_urlsafe(24)
            self._interpretation = (ticket, self._generation, self.clock() + self.ttl)
            return ticket

    def complete_interpretation(self, ticket, plan):
        """Accept a validated proposal. A ticket is consumed once."""
        with self._lock:
            pending = self._interpretation
            if (not pending or not isinstance(ticket, str) or not secrets.compare_digest(ticket, pending[0])
                    or pending[1] != self._generation or self.clock() >= pending[2]
                    or self.paused or self._execution_lock.locked()):
                raise BrokerError('AI result discarded because the request changed or was cancelled.')
            self._interpretation = None
            self._generation += 1
            if any(a.kind in {'installed_app', 'workspace_patch'} for a in plan.actions):
                raise BrokerError('AI cannot supply local selection handles. Use the native picker.')
            return self._offer(plan, source='ai')

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
                pending, self.pending = self.pending, None
                generation = self._generation
            try:
                def valid():
                    with self._lock:
                        return not self.paused and generation == self._generation and self.clock() < pending.expires

                def gate(dispatch):
                    with self._lock:
                        if self.paused or generation != self._generation or self.clock() >= pending.expires:
                            return {
                                'status': 'cancelled',
                                'message': 'Approval expired or was revoked while waiting. Nothing was dispatched.',
                            }
                    return dispatch()

                outcome = self.executor.execute(pending.plan.actions[0], gate, valid)
            except Exception as exc:
                with self._lock:
                    self._record(pending.plan.title, 'failed')
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
                self._generation += 1
                self.pending = None
                return {'message': 'Cancelled. No action was dispatched.'}
            raise BrokerError('This approval is no longer pending.')

    def pause(self, enabled):
        with self._lock:
            self.paused = enabled
            self._interpretation = None
            self._generation += 1
            if enabled:
                self.pending = None
            self._record('Action control', 'paused' if enabled else 'resumed')
            return {
                'paused': enabled,
                'message': (
                    'Paused. Pending approvals cleared. '
                    'An action already dispatched cannot be recalled; decline any open Windows dialog.'
                    if enabled else
                    'Actions resumed. Ready for instant execution.'
                ),
            }

    def clear(self):
        with self._lock:
            self.pending = None
            self._interpretation = None
            self._generation += 1
            self._events.clear()
        return {'message': 'Session activity and pending approval cleared.'}
