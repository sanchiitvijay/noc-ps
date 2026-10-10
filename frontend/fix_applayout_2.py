with open("src/layouts/AppLayout.jsx", "r") as f:
    c = f.read()

# Header
c = c.replace('<header>', '<header className="sticky top-0 z-40 flex h-[62px] items-center gap-4 px-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm">')

# Form
c = c.replace('className="header-search-form"', 'className="relative flex items-center w-full max-w-md ml-4"')
c = c.replace('className="header-search-clear"', 'className="absolute right-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"')

# Theme Cycle
c = c.replace('className={`theme-cycle${isDark ? \' is-dark\' : \'\'}`}', 'className="relative flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors ml-4"')
c = c.replace('<span className="theme-cycle-sun" />', '<span className="text-xs text-yellow-500">☼</span>')
c = c.replace('<span className="theme-cycle-moon" />', '<span className="text-xs hidden dark:block text-blue-300">☾</span>')
c = c.replace('<i className="theme-cycle-star theme-cycle-star-one" />', '')
c = c.replace('<i className="theme-cycle-star theme-cycle-star-two" />', '')

# Sidebar Nav
c = c.replace('<nav>', '<nav className={`flex flex-col bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex-shrink-0 transition-all duration-300 ${sidebarCollapsed ? "w-16" : "w-64"}`}>')
c = c.replace('className="sidebar-heading"', 'className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 h-[62px]"')
c = c.replace('className="sidebar-heading-label"', 'className="text-xs font-bold text-gray-500 uppercase tracking-wider overflow-hidden"')
c = c.replace('className="sidebar-toggle"', 'className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded"')

# NavLinks
c = c.replace("className={({ isActive }) => isActive ? 'on' : ''}", 'className={({ isActive }) => `flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors ${isActive ? "bg-blue-50 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400 border-r-2 border-blue-600" : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50"}`}')
c = c.replace('className="nav-icon"', 'className="flex items-center justify-center w-6 h-6 flex-shrink-0"')
c = c.replace('className="nav-label"', 'className={`truncate transition-opacity duration-300 ${sidebarCollapsed ? "opacity-0 hidden" : "opacity-100"}`}')

# Header Buttons
c = c.replace('<button\n          aria-label=', '<button className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-red-600 bg-red-50 dark:bg-red-900/20 dark:text-red-400 rounded-full hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"\n          aria-label=')

# Main shell wrap
c = c.replace('className={`flex min-h-[calc(100vh-62px)] bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100 transition-all duration-300 ${sidebarCollapsed ? \'pl-16\' : \'\'}`}', 'className="flex flex-1 min-h-[calc(100vh-62px)] bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100"')

# Shell old replacement fallback
c = c.replace('className={`shell${sidebarCollapsed ? \' sidebar-collapsed\' : \'\'}`}', 'className="flex flex-1 min-h-[calc(100vh-62px)] bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-100"')

with open("src/layouts/AppLayout.jsx", "w") as f:
    f.write(c)
