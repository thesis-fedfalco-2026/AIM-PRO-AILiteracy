"""Run the Authoring API on this host with settings from the environment (see role-applications.md)."""

import argparse
import sys

from pydantic import ValidationError

from services.authoring_api.app import create_app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=58000)
    args = parser.parse_args(argv)
    try:
        app = create_app()
    except (ValueError, OSError) as error:
        message = 'invalid settings or identity map' if isinstance(error, ValidationError) else str(error)
        print('API not started: ' + message, file=sys.stderr)
        return 2
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, proxy_headers=False, server_header=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
