import re

with open('frontend/src/pages/Dashboard.jsx', 'r') as f:
    content = f.read()

content = content.replace('<div><h2>Device Telemetry & Alerts</h2></div>', '<div className="my-8 border-t border-gray-200 dark:border-gray-700 pt-6"><h2 className="text-xl font-bold text-gray-800 dark:text-gray-100 mb-4">Device Telemetry & Alerts</h2></div>')
content = content.replace('<section aria-label="All-time event totals by severity">', '<section className="flex flex-wrap items-center gap-3 bg-white dark:bg-gray-800 p-4 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm" aria-label="All-time event totals by severity">')
content = content.replace('<section aria-busy={showChartLoader}>', '<section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6" aria-busy={showChartLoader}>')
content = content.replace('<section>', '<section className="mt-6 flex flex-col md:flex-row gap-6">')
content = content.replace('<article>', '<article className="bg-white dark:bg-gray-800 p-5 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm flex-1 relative overflow-hidden">')

# Add basic div wrapper to return
content = re.sub(r'return \(\n\s*<div>', 'return (\n    <div className="flex flex-col space-y-6">', content)

# Buttons
content = re.sub(r'<button key=\{severity\} onClick=\{([^}]+)\} aria-pressed=\{([^}]+)\}>', r'<button className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm border transition-colors ${selectedSeverities.includes(severity) ? "bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-900/30 dark:border-blue-800 dark:text-blue-300" : "bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100 dark:bg-gray-800/50 dark:border-gray-700 dark:text-gray-400"}`} key={severity} onClick={\1} aria-pressed={\2}>', content)

content = re.sub(r'<button key=\{item\.id\} onClick=\{([^}]+)\}>', r'<button className="px-3 py-1 text-sm rounded-md transition-colors hover:bg-gray-200 dark:hover:bg-gray-700" key={item.id} onClick={\1}>', content)

with open('frontend/src/pages/Dashboard.jsx', 'w') as f:
    f.write(content)

