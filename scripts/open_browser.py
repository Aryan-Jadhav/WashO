"""Used by start.bat: wait until the WashO server answers, then open it in the default browser.

WHY wait: if the browser opens before the server is ready, the person sees an error page.
"""
import os
import sys
import time
import urllib.error
import urllib.request
import webbrowser

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

for _ in range(60):  # try for up to ~30 seconds
    try:
        urllib.request.urlopen(URL, timeout=2)
        break
    except urllib.error.HTTPError:
        break  # the server answered (even an error page means it is up)
    except (urllib.error.URLError, OSError):
        time.sleep(0.5)
else:
    sys.exit(1)  # server never came up; start.bat shows the error in its own window

if os.environ.get("WASHO_NO_BROWSER") != "1":  # set by automated tests only
    webbrowser.open(URL)
