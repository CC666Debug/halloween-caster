"""Weekly station check for Halloween Caster.

1. Tries every channel's stream (and its data saver version) and lists the ones that don't send audio.
2. Checks every channel's song info is still updating (a renamed channel keeps playing but its old song info freezes).
3. Lists Halloween Radio channels on the station's server that the app doesn't use (new or renamed ones).

It only writes a report (Markdown, to stdout); the first line says PROBLEMS when a stream or song info is broken.
Nothing in the app changes until the owner OKs it. Standard library only.
"""
import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

UA = 'HalloweenCasterStationCheck/1.0 (+https://cc666debug.github.io/halloween-caster/)'
ROOT = Path(__file__).resolve().parents[2]
API = 'https://radio1.streamserver.link/api/'
STALE_HOURS = 3   # no new song for this long means the song info is stuck
SKIP = {'halloween_radio_premium'}   # supporters only, set up on the phone

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def stations():
    """The STATIONS list in index.html: name, song info code, stream and data saver addresses."""
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    block = re.search(r'const STATIONS = \[(.*?)\n\];', html, re.S).group(1)
    out = []
    for m in re.finditer(r"\{ id: '([^']+)'.*?name: '([^']+)'.*?code: '([^']+)'.*?url: '([^']+)'(.*?)\}", block, re.S):
        lite = re.search(r"lite: '([^']+)'", m.group(5))
        out.append({'id': m.group(1), 'name': m.group(2), 'code': m.group(3), 'url': m.group(4), 'lite': lite and lite.group(1)})
    return out


def probe(url, tries=2):
    """Returns '' if the stream answers with audio, else a short reason."""
    reason = ''
    for attempt in range(tries):
        if attempt:
            time.sleep(4)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Icy-MetaData': '0'})
            with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as r:
                ctype = (r.headers.get('Content-Type') or '').lower()
                data = r.read(4096)
                if not data:
                    reason = 'answers but sends nothing'
                elif 'text/html' in ctype:
                    reason = 'sends a web page, not audio'
                else:
                    return ''
        except urllib.error.HTTPError as e:
            reason = f'HTTP {e.code}'
        except (socket.timeout, TimeoutError):
            reason = 'no answer (timed out)'
        except urllib.error.URLError as e:
            reason = 'can’t connect (' + str(e.reason)[:60] + ')'
        except Exception as e:
            reason = type(e).__name__ + ': ' + str(e)[:60]
    return reason


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=20, context=SSL_CTX) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    chans = stations()
    problems = 0
    out = [f'# Station check · {date.today():%b %d, %Y}', '']

    # 1. Streams
    dead = []
    for s in chans:
        for label, url in (('stream', s['url']), ('data saver stream', s['lite'])):
            if url:
                why = probe(url)
                if why:
                    dead.append(f'- {s["name"]} {label}: {why}')
    problems += len(dead)
    out += ['## Streams', '']
    out += dead or ['Every stream sends audio. 🎃']
    out.append('')

    # 2. Song info
    stuck = []
    now = time.time()
    for s in chans:
        try:
            d = get_json(API + f'nowplaying_static/{s["code"]}.json')
            age = (now - d['now_playing']['played_at']) / 3600
            if age > STALE_HOURS:
                stuck.append(f'- {s["name"]} (`{s["code"]}`): no new song for {age:.0f} hours'
                             f' (stuck on “{d["now_playing"]["song"].get("text", "")}”). The channel may have been renamed; see below.')
        except Exception as e:
            stuck.append(f'- {s["name"]} (`{s["code"]}`): song info won’t load ({type(e).__name__})')
    problems += len(stuck)
    out += ['## Song info', '']
    out += stuck or ['Every channel’s song info is updating.']
    out.append('')

    # 3. Channels on the server the app doesn't use
    try:
        used = {s['code'] for s in chans}
        extra = []
        for d in get_json(API + 'nowplaying'):
            st = d['station']
            if st['shortcode'].startswith('halloween_radio') and st['shortcode'] not in used | SKIP:
                mounts = ', '.join(m['url'] for m in st.get('mounts', [])) or 'no stream listed'
                extra.append(f'- **{st["name"]}** (`{st["shortcode"]}`): {mounts}')
        # Not a problem on its own (a renamed channel also shows up as stuck song info above), just worth knowing.
        out += ['## Halloween Radio channels not in the app', '']
        out += extra or ['None. The app has every channel.']
    except Exception as e:
        out += ['## Halloween Radio channels not in the app', '', f'Couldn’t load the station list ({type(e).__name__}).']
    out.append('')

    print('PROBLEMS' if problems else 'OK')
    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
