"""Bounded, read-only HTTPS release checks. No accounts or provider calls."""
import argparse
import json
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def inspect_health(raw):
    body = json.loads(raw)
    if body.get('status') != 'ok' or not body.get('schema_version'):
        raise ValueError('Database readiness or migration version missing')
    if body.get('demo') is not False or body.get('test_environment') is not False:
        raise ValueError('Recorded mode or acceptance-test schema enabled')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin', help='Public HTTPS origin, e.g. https://practice.example.com')
    args = parser.parse_args()
    parsed = urlsplit(args.origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
            parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        parser.error('Supply an HTTPS origin without credentials, path, query or fragment')
    origin = args.origin.rstrip('/')
    opener = build_opener(NoRedirects(), HTTPSHandler(context=ssl.create_default_context()))
    checks = [('/', 200, 'html'), ('/privacy', 200, 'html'),
              ('/api/v2/health', 200, 'health'), ('/api/v2/history', 401, 'private')]
    failed = False
    for path, expected, kind in checks:
        try:
            request = Request(origin + path, headers={'User-Agent': 'PrepCrew-release-smoke/1'})
            try:
                response = opener.open(request, timeout=8)
            except HTTPError as error:
                response = error
            with response:
                raw = response.read(65537)
                if response.status != expected:
                    raise ValueError(f'Expected HTTP {expected}, got {response.status}')
                if len(raw) > 65536:
                    raise ValueError('Response exceeds smoke-check limit')
                if kind == 'health':
                    inspect_health(raw)
                if kind == 'html' and (b'<html' not in raw.lower() or b'<script' not in raw.lower()):
                    raise ValueError('Frontend HTML/script missing')
                if kind == 'private' and response.headers.get('Cache-Control') != 'no-store':
                    raise ValueError('Private response missing no-store policy')
            print(f'PASS {path}')
        except (URLError, OSError, ValueError, TimeoutError) as error:
            # Do not print server bodies or URLs: they may contain private data.
            print(f'FAIL {path}: {type(error).__name__}')
            failed = True
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
