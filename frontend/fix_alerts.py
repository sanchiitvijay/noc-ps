with open("src/pages/Alerts.jsx", "r") as f:
    c = f.read()

c = c.replace('className="alerts-filter-form"', 'className="flex flex-wrap items-center gap-3 mb-4"')
c = c.replace('className="alerts-search-button"', 'className="flex items-center justify-center p-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"')
c = c.replace('className="alerts-results-toolbar"', 'className="flex items-center justify-between mb-4 border-b border-gray-200 dark:border-gray-700 pb-3"')
c = c.replace('className="alerts-export-button"', 'className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors border border-gray-300 dark:border-gray-600"')
c = c.replace('className="event-new-tab-button"', 'className="block w-full text-center px-2 py-1 text-xs text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 rounded"')
c = c.replace('className="alerts-pagination"', 'className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200 dark:border-gray-700"')
c = c.replace('className="alerts-page-numbers"', 'className="flex items-center gap-1 overflow-x-auto"')

import re
# Make pagination buttons look nice
c = re.sub(r'<button\s*key={page}\s*type="button"\s*className={page === logPage \? \'is-active\' : \'\'}',
           r'<button key={page} type="button" className={`px-3 py-1 rounded text-sm ${page === logPage ? "bg-blue-600 text-white" : "bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"}`}', c)

with open("src/pages/Alerts.jsx", "w") as f:
    f.write(c)
