"""CompControl launch and terminal entry points."""
import argparse
import platform
import sys

from .broker import Broker, DemoExecutor


def cli(demo=False):
    if demo:
        executor = DemoExecutor()
    else:
        from .actions import WindowsExecutor
        executor = WindowsExecutor()
    broker = Broker(executor, demo=demo)
    print(f'CompControl • {"DEMO: no desktop effects" if demo else "Windows local mode"}')
    print('Type help. Every desktop action needs approval. Type quit or Ctrl+C to stop.')
    try:
        while True:
            text = input('\nYou > ')
            if text.strip().casefold() in {'quit', 'exit'}:
                break
            try:
                if text.strip().casefold() in {'pause', 'resume'}:
                    print(broker.pause(text.strip().casefold() == 'pause')['message'])
                    continue
                plan = broker.plan(text)
                print(plan['title'] + '\n' + plan['message'])
                if plan['approval_id']:
                    print('Exact destination: ' + '\n'.join(plan['destinations']))
                    if input('Type APPROVE to allow this once, anything else to cancel: ') == 'APPROVE':
                        print(broker.confirm(plan['approval_id'])['message'])
                    else:
                        print(broker.cancel(plan['approval_id'])['message'])
            except ValueError as exc:
                print(str(exc))
    except (EOFError, KeyboardInterrupt):
        print('\nStopped.')


def main():
    parser = argparse.ArgumentParser(description='CompControl • local-first Windows command center')
    parser.add_argument('--cli', action='store_true', help='use the terminal instead of the command center')
    parser.add_argument('--ui', action='store_true', help='open the command center (default)')
    parser.add_argument('--demo', action='store_true', help='simulate actions; disable desktop access and AI')
    parser.add_argument('--host', default='127.0.0.1', help='UI bind address; external binds require --demo')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-open', action='store_true', help='do not automatically open a browser')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('Port must be in 0–65535.')
    if not args.demo and platform.system() != 'Windows':
        parser.error('Windows is required for desktop execution. Use --demo for a safe preview on this system.')
    try:
        if args.cli:
            cli(args.demo)
        else:
            from .server import serve
            serve(args.host, args.port, args.demo, not args.no_open)
    except (ValueError, OSError) as exc:
        print(f'Could not start CompControl: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
