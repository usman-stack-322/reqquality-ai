"""Serve only the explicitly prepared local demo database on loopback."""
import argparse
from prepare_demo import DEFAULT_DIRECTORY, configure

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=__import__('pathlib').Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not (directory / 'demo.db').is_file():
        raise SystemExit('Run prepare_demo.py first. No database was created.')
    configure(directory)
    import app
    app.app.config.update(LOCAL_HTTP_DEVELOPMENT=True, SESSION_COOKIE_SECURE=False)
    app.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
