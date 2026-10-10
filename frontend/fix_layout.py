with open("src/layouts/AppLayout.jsx", "r") as f:
    c = f.read()

c = c.replace('className="pm"', 'className="relative pm"')
c = c.replace('className="av"', 'className="flex items-center justify-center w-8 h-8 rounded bg-blue-600 text-white font-semibold cursor-pointer"')
c = c.replace('className="pd"', 'className="absolute right-0 top-12 mt-2 w-48 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg p-3 z-50"')
c = c.replace('<b>{me.name} | {me.role === \'ADMIN\' ? \'Admin\' : \'NOC Analyst\'}</b>', '<b className="block text-sm mb-3 pb-2 border-b border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-100">{me.name} <br/><span className="text-xs text-gray-500 font-normal">{me.role === \'ADMIN\' ? \'Admin\' : \'NOC Analyst\'}</span></b>')
c = c.replace('<button\n              onClick={() => {', '<button className="w-full text-left px-2 py-1.5 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded" onClick={() => {')

with open("src/layouts/AppLayout.jsx", "w") as f:
    f.write(c)
