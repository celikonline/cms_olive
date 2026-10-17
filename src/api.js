let csrf = '';
export async function api(path, options = {}) {
  if (!csrf && path !== '/session') {
    const r = await fetch('/api/session');
    csrf = (await r.json()).csrf;
  }
  const isForm = options.body instanceof FormData;
  const response = await fetch('/api' + path, {
    ...options,
    headers: { ...(!isForm ? { 'Content-Type': 'application/json' } : {}), 'X-CSRF-Token': csrf, ...options.headers },
    body: options.body ? isForm ? options.body : JSON.stringify(options.body) : undefined,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'İşlem tamamlanamadı.');
  if (data.csrf) csrf = data.csrf;
  if (path === '/logout') csrf = '';
  return data;
}
export const money = n => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0);
export const slugify = s => s.toLocaleLowerCase('tr').replace(/ı/g,'i').replace(/ğ/g,'g').replace(/ü/g,'u').replace(/ş/g,'s').replace(/ö/g,'o').replace(/ç/g,'c').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
