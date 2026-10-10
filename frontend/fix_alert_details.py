with open("src/pages/AlertEventDetails.jsx", "r") as f:
    c = f.read()

c = c.replace('className="alert-event-detail event-detail-page"', 'className="w-full max-w-6xl mx-auto p-4 md:p-8 bg-white dark:bg-gray-900 min-h-screen"')
c = c.replace('className="alert-detail-actions"', 'className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200 dark:border-gray-700"')
c = c.replace('className="alert-detail-hero"', 'className="mb-6"')
c = c.replace('className="alert-detail-grid g"', 'className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"')
c = c.replace('className="c"', 'className="bg-white dark:bg-gray-800 p-5 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm"')
c = c.replace('className="c historical-incidents-card"', 'className="bg-white dark:bg-gray-800 p-5 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm overflow-hidden lg:col-span-2"')
c = c.replace('className="mu"', 'className="text-xs text-gray-500 uppercase tracking-wider"')

with open("src/pages/AlertEventDetails.jsx", "w") as f:
    f.write(c)

