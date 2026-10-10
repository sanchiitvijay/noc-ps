import re

def replace_classes(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Layout classes
    content = content.replace('className="shell"', 'className="flex min-h-[calc(100vh-62px)] bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100"')
    content = content.replace('className={`shell${sidebarCollapsed ? \' sidebar-collapsed\' : \'\'}`}', 'className={`flex min-h-[calc(100vh-62px)] bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100 transition-all duration-300 ${sidebarCollapsed ? \'pl-16\' : \'\'}`}')
    content = content.replace('className="lg"', 'className="flex items-center gap-2 mr-2"')
    content = content.replace('className="sr header-search-input"', 'className="w-full max-w-sm px-3 py-1.5 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-md"')
    content = content.replace('className="banner"', 'className="relative overflow-hidden px-8 py-10 text-white bg-gradient-to-r from-blue-900 to-blue-800 border-b border-gray-200 dark:border-gray-800 mb-6"')
    content = content.replace('className="bt"', 'className="flex items-center gap-5 flex-wrap"')
    
    # Generic wrapper
    content = content.replace('className="ct"', 'className="flex-1 min-w-0 flex flex-col"')
    content = content.replace('<main>', '<main className="w-full max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 py-6">')
    
    # Cards and Grids
    content = content.replace('className="c"', 'className="bg-white dark:bg-gray-800 p-5 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm flex flex-col mb-4 hover:border-blue-500 transition-colors"')
    content = content.replace('className="g"', 'className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"')
    content = content.replace('className="dashboard-kpi-grid"', 'className="grid auto-rows-[320px] items-stretch"')
    content = content.replace('className="mu"', 'className="text-xs text-gray-500 uppercase tracking-wider"')
    content = content.replace('className="k"', 'className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-gray-100 tabular-nums"')
    
    # Table stuff
    content = content.replace('className="alerts-table"', 'className="w-full min-w-[1120px] table-fixed text-left text-sm"')
    content = content.replace('className="tw"', 'className="overflow-x-auto border border-gray-200 dark:border-gray-700 rounded-md"')
    content = content.replace('className="h"', 'className="border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors"')
    
    with open(filepath, 'w') as f:
        f.write(content)

replace_classes('src/layouts/AppLayout.jsx')
replace_classes('src/pages/Dashboard.jsx')
replace_classes('src/pages/Alerts.jsx')

