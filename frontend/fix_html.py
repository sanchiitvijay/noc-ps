with open("index.html", "r") as f:
    c = f.read()

import re
c = re.sub(r'<body className="[^"]*">', '<body>', c)

with open("index.html", "w") as f:
    f.write(c)
