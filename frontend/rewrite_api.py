import re

with open('frontend/src/services/api.js', 'r') as f:
    content = f.read()

caching_code = """
const getCached = (key) => {
  try {
    const item = localStorage.getItem(key);
    if (!item) return null;
    const parsed = JSON.parse(item);
    if (Date.now() > parsed.expiry) return null;
    return parsed.value;
  } catch (e) { return null; }
};
const setCached = (key, value, ttlMs = 300000) => {
  localStorage.setItem(key, JSON.stringify({ value, expiry: Date.now() + ttlMs }));
};
"""

if "getCached" not in content:
    content = content.replace("export const getMetrics", caching_code + "\nexport const getMetrics")

content = re.sub(
    r"export const getMetrics = async \(params = \{\}\) => \{\n\s*const response = await request\('/get-metrics', \{ query: params \}\);\n\s*return response\?.data \?\? response;\n\};",
    """export const getMetrics = async (params = {}) => {
  const cacheKey = 'metrics_' + JSON.stringify(params);
  const cached = getCached(cacheKey);
  if (cached) return cached;
  const response = await request('/get-metrics', { query: params });
  const res = response?.data ?? response;
  setCached(cacheKey, res, 120000);
  return res;
};""",
    content
)

content = re.sub(
    r"export const getLogs = async \(params = \{\}\) => \{\n\s*const response = await request\('/get-logs', \{ query: params \}\);\n\s*const data = response\?.data \?\? response;\n\s*if \(Array\.isArray\(data\)\) \{\n\s*return \{\n\s*data,\n\s*total: response\?\.total \?\? response\?\.meta\?\.total \?\? data\.length,\n\s*page: response\?\.page \?\? response\?\.meta\?\.page \?\? params\.page \?\? 1,\n\s*page_size: response\?\.page_size \?\? response\?\.meta\?\.page_size \?\? params\.page_size \?\? data\.length,\n\s*\};\n\s*\}\n\s*if \(\!Array\.isArray\(data\?\.data\)\) return data;\n\s*return \{\n\s*\.\.\.data,\n\s*data: data\.data,\n\s*total: data\.total \?\? data\.meta\?\.total \?\? data\.meta\?\.total_returned \?\? data\.data\.length,\n\s*page: data\.page \?\? data\.meta\?\.page \?\? params\.page \?\? 1,\n\s*page_size: data\.page_size \?\? data\.meta\?\.page_size \?\? params\.page_size \?\? data\.data\.length,\n\s*\};\n\};",
    """export const getLogs = async (params = {}) => {
  const cacheKey = 'logs_' + JSON.stringify(params);
  const cached = getCached(cacheKey);
  if (cached) return cached;
  const response = await request('/get-logs', { query: params });
  const data = response?.data ?? response;
  if (Array.isArray(data)) {
    const res = {
      data,
      total: response?.total ?? response?.meta?.total ?? data.length,
      page: response?.page ?? response?.meta?.page ?? params.page ?? 1,
      page_size: response?.page_size ?? response?.meta?.page_size ?? params.page_size ?? data.length,
    };
    setCached(cacheKey, res, 120000);
    return res;
  }
  if (!Array.isArray(data?.data)) return data;
  const res2 = {
    ...data,
    data: data.data,
    total: data.total ?? data.meta?.total ?? data.meta?.total_returned ?? data.data.length,
    page: data.page ?? data.meta?.page ?? params.page ?? 1,
    page_size: data.page_size ?? data.meta?.page_size ?? params.page_size ?? data.data.length,
  };
  setCached(cacheKey, res2, 120000);
  return res2;
};""",
    content
)

with open('frontend/src/services/api.js', 'w') as f:
    f.write(content)
