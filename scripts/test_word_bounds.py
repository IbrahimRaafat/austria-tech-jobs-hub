import re

text = 'Projektleitung Hochbau (m/w/d)'
print('Contains "it" substring:', 'it' in text.lower())
print('Contains "\\bit\\b" word:', bool(re.search(r'\bit\b', text.lower())))

text2 = 'Servicetechniker Elektrotechnik'
print('Contains "tech" substring:', 'tech' in text2.lower())
print('Contains "\\btech\\b" word:', bool(re.search(r'\btech\b', text2.lower())))
