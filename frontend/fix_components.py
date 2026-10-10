with open("src/components/Tag.jsx", "w") as f:
    f.write("""export default function Tag({ s }) {
  const colors = {
    Critical: 'bg-red-600 text-white',
    Warning: 'bg-orange-500 text-gray-900',
    Info: 'bg-blue-500 text-gray-900',
    Unknown: 'bg-gray-500 text-white',
    P1: 'bg-red-600 text-white',
    P2: 'bg-orange-500 text-gray-900',
    P3: 'bg-blue-500 text-gray-900',
    P4: 'bg-gray-500 text-white',
    Healthy: 'bg-green-500 text-gray-900',
  };
  const color = colors[s] || 'bg-gray-500 text-white';
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${color}`}>{s}</span>;
}
""")

with open("src/components/RelatedTickets.jsx", "r") as f:
    c = f.read()

c = c.replace('className="related-ticket-empty"', 'className="py-2"')
c = c.replace('className="related-ticket-toggle"', 'className="inline-flex items-center gap-2 px-3 py-1.5 text-[10px] font-semibold bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800 rounded-full hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors whitespace-nowrap"')
c = c.replace('className="related-ticket-empty-details"', 'className="mt-2 p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md text-xs"')
c = c.replace('className="mu"', 'className="text-[10px] text-gray-500 uppercase tracking-wider"')
c = c.replace('className="related-ticket-list"', 'className="flex flex-col mt-2"')
c = c.replace('className="related-ticket"', 'className="min-w-0 border-b border-gray-200 dark:border-gray-700 last:border-0 py-2"')
c = c.replace('className="related-ticket-summary"', 'className="flex items-center justify-between gap-3"')
c = c.replace('className="related-ticket-copy"', 'className="flex flex-col gap-1 min-w-0"')
c = c.replace('className="related-ticket-heading"', 'className="flex items-center gap-2"')
c = c.replace('className="related-ticket-state"', 'className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-full text-[10px] text-gray-800 dark:text-gray-200"')
c = c.replace('className="related-ticket-short-description"', 'className="block text-sm text-gray-700 dark:text-gray-300 truncate"')
c = c.replace('className="related-ticket-details"', 'className="mt-3 p-4 bg-gray-50 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 rounded-md"')
c = c.replace('className="related-ticket-header"', 'className="flex justify-between items-center pb-2 border-b border-gray-200 dark:border-gray-700"')
c = c.replace('className="related-ticket-description"', 'className="py-3 border-b border-gray-200 dark:border-gray-700"')
c = c.replace('className="related-ticket-fields"', 'className="grid grid-cols-2 gap-3 my-3 text-xs"')
c = c.replace('className="related-ticket-notes"', 'className="pt-3 border-t border-gray-200 dark:border-gray-700 text-xs overflow-auto max-h-60"')
c = c.replace('className={`related-ticket-chevron${expanded ? \' expanded\' : \'\'}`}', 'className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}')
c = c.replace('<h4>', '<h4 className="font-bold text-blue-600 dark:text-blue-400 mt-1">')

with open("src/components/RelatedTickets.jsx", "w") as f:
    f.write(c)

