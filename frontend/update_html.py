with open("index.html", "r") as f:
    c = f.read()

c = c.replace('<body>', '<body className="bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 min-h-screen">')
with open("index.html", "w") as f:
    f.write(c)
