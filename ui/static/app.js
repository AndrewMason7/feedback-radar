const st = {cat:new Set(), imp:new Set(), src:new Set(), nodup:false, qw:false, q:""};
const cards = [...document.querySelectorAll('.card')];
function apply(){
  let n = 0;
  for(const el of cards){
    const d = el.dataset;
    let ok = true;
    if(st.cat.size && !st.cat.has(d.cat)) ok = false;
    if(st.imp.size && !st.imp.has(d.imp)) ok = false;
    if(st.src.size && !st.src.has(d.src)) ok = false;
    if(st.nodup && d.dup === "1") ok = false;
    if(st.qw && d.qw !== "1") ok = false;
    if(st.q && !el.textContent.toLowerCase().includes(st.q)) ok = false;
    el.classList.toggle('hidden', !ok);
    if(ok) n++;
  }
  document.getElementById('fcount').textContent = n + " of " + cards.length;
  document.getElementById('empty').classList.toggle('hidden', n > 0);
}
document.querySelectorAll('.fchip[data-g]').forEach(b => b.addEventListener('click', () => {
  const s = st[b.dataset.g], v = b.dataset.v;
  if(s.has(v)){ s.delete(v); b.classList.remove('on'); }
  else { s.add(v); b.classList.add('on'); }
  apply();
}));
document.querySelectorAll('.fchip[data-toggle]').forEach(b => b.addEventListener('click', () => {
  const k = b.dataset.toggle;
  st[k] = !st[k];
  b.classList.toggle('on', st[k]);
  apply();
}));
document.getElementById('fsearch').addEventListener('input', e => {
  st.q = e.target.value.trim().toLowerCase();
  apply();
});
apply();
