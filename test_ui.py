import sys; sys.path.insert(0, '.')
from streamlit.testing.v1 import AppTest
a = AppTest.from_file('app.py', default_timeout=180)
a.run()
errs = list(a.exception)
print('EXCEPTIONS:', len(errs))
for e in errs[:3]:
    print(type(e.value).__name__, str(e.value)[:200])
print('BUTTONS:', len(a.button))
print('TABS:', len(a.tabs))
print('METRICS-HTML-OK')
