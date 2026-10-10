with open("src/components/AlertSimulation.jsx", "r") as f:
    c = f.read()

c = c.replace('className="c alert-simulation-panel"', 'className="bg-white dark:bg-gray-800 p-4 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm mb-4"')
c = c.replace('className="alert-simulation-heading"', 'className="flex flex-wrap items-center justify-between gap-4"')
c = c.replace('className="mu"', 'className="text-xs text-gray-500 uppercase tracking-wider"')
c = c.replace('className="alert-simulation-error"', 'className="mt-3 text-sm text-red-600"')
c = c.replace('className="alert-simulation-status"', 'className="mt-3 text-sm text-blue-600 dark:text-blue-400 font-medium"')
c = c.replace('<button type="button"', '<button type="button" className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm transition-colors disabled:opacity-50"')

with open("src/components/AlertSimulation.jsx", "w") as f:
    f.write(c)

