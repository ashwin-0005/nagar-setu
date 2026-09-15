import sys; sys.path.insert(0, '.')
from streamlit.testing.v1 import AppTest


def show(test, key):
    try:
        return ascii(test.session_state[key])
    except KeyError:
        return "<unset>"


# hero prompt submit -> jumps to File with text prefilled
b = AppTest.from_file('app.py', default_timeout=240)
b.run()
assert not list(b.exception), "initial render failed"
b.text_area(key="hero_text").set_value("paani nahi aa raha 3 din se").run()
b.button(key="hero_go").click().run()
errs = list(b.exception)
print('HERO-SUBMIT-EXCEPTIONS:', len(errs))
for e in errs[:2]:
    print(type(e.value).__name__, str(e.value)[:160])
print('SECTION-AFTER-HERO:', show(b, "section"))
print('MY-TEXT:', str(show(b, "my_text"))[:40])

# closing CTA form
c = AppTest.from_file('app.py', default_timeout=240)
c.run()
c.text_input(key="cta_text").set_value("pothole on main road").run()
c.button(key="cta_go").click().run()
print('CTA-EXCEPTIONS:', len(list(c.exception)))
print('SECTION-AFTER-CTA:', show(c, "section"))
print('MY-TEXT-CTA:', str(show(c, "my_text"))[:40])

# old core paths still green
d = AppTest.from_file('app.py', default_timeout=240)
d.run()
d.radio(key="section").set_value("📊 Command").run()
print('COMMAND-EXCEPTIONS:', len(list(d.exception)))
print('BOLT-FLOWS-OK')
