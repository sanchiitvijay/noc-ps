with open("src/components/AlertDrawer.jsx", "r") as f:
    c = f.read()

c = c.replace('<aside id="dr" className="on">', '<div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-sm">\n      <aside id="dr" className="w-full max-w-lg bg-white dark:bg-gray-800 h-full overflow-y-auto p-6 shadow-2xl border-l border-gray-200 dark:border-gray-700">')
c = c.replace('<aside id="dr" />', '<aside id="dr" className="hidden" />')
c = c.replace('</aside>', '</aside>\n    </div>')

c = c.replace('className="c"', 'className="bg-white dark:bg-gray-800 p-4 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm mb-4"')
c = c.replace('className="c historical-incidents-card"', 'className="bg-white dark:bg-gray-800 p-4 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm mb-4 overflow-hidden"')
c = c.replace('className="mu"', 'className="text-xs text-gray-500 uppercase tracking-wider"')

with open("src/components/AlertDrawer.jsx", "w") as f:
    f.write(c)

