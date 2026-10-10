import re

with open('src/pages/Dashboard.jsx', 'r') as f:
    content = f.read()

content = content.replace('className="dashboard-page"', 'className="flex flex-col space-y-6"')
content = content.replace('className="severity-filter"', 'className="flex flex-wrap items-center gap-3 bg-white dark:bg-gray-800 p-4 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm"')
content = content.replace('className="dashboard-toolbar"', 'className="flex flex-wrap items-center justify-between"')
content = content.replace('className="dashboard-toolbar-actions"', 'className="flex items-center gap-3"')
content = content.replace('className="range-pills"', 'className="flex items-center gap-1 p-1 bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md"')
content = content.replace('className="dashboard-stat-grid"', 'className="grid grid-cols-1 md:grid-cols-3 gap-4"')
content = content.replace('className="dashboard-stat"', 'className="relative overflow-hidden"')
content = content.replace('className="stat-foot"', 'className="text-xs text-gray-500"')
content = content.replace('className="stat-sparkline"', 'className="absolute right-4 bottom-3 flex items-end gap-[2px] h-8 opacity-70"')
content = content.replace('className="stat-highlight"', 'className="absolute left-4 right-4 bottom-0 h-1 bg-blue-600"')
content = content.replace('className="dashboard-card-heading"', 'className="flex items-start justify-between min-h-[38px] mb-2"')
content = content.replace('className="chart-total"', 'className="text-lg font-bold text-gray-900 dark:text-gray-100 tabular-nums"')
content = content.replace('className="dashboard-chart"', 'className="w-full h-64 mt-2 relative"')
content = content.replace('className="category-chips"', 'className="flex flex-wrap gap-2 mt-4"')
content = content.replace('className="category-chip"', 'className="inline-flex items-center gap-3 px-3 py-1.5 bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100 text-xs rounded-full border border-gray-200 dark:border-gray-700 capitalize"')

# Separation div
sep_div = '<div className="my-8 border-t border-gray-200 dark:border-gray-700 pt-6"><h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Device Telemetry & Alerts</h2></div>\n      <section className="c dashboard-device-card">'
content = content.replace('<section className="c dashboard-device-card">', sep_div)

with open('src/pages/Dashboard.jsx', 'w') as f:
    f.write(content)

