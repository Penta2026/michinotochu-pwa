'use strict';
(function(){
  const PREFS=new Set(['新潟県','富山県','石川県','福井県','山梨県','長野県','岐阜県','静岡県','愛知県']);
  const SUMMARIES={};
  const ALIASES={};
  //__INSERT__
  const norm=s=>String(s||'').normalize('NFKC').replace(/^道の駅\s*/,'').replace(/[\s　・･「」『』（）()]/g,'').toLowerCase();
  const byNorm=new Map(Object.entries(SUMMARIES).map(([k,v])=>[norm(k),v]));
  Object.entries(ALIASES).forEach(([a,k])=>{const v=SUMMARIES[k];if(v)byNorm.set(norm(a),v);});
  const roads=(window.APP_DATA&&Array.isArray(window.APP_DATA.roads))?window.APP_DATA.roads:[];
  let applied=0,unmatched=[];
  roads.forEach(x=>{
    if(!PREFS.has(x.prefecture))return;
    const v=byNorm.get(norm(x.name));
    if(v){x.summary=v;applied++;}else unmatched.push({prefecture:x.prefecture,name:x.name});
  });
  window.ROAD_SUMMARIES_CHUBU_META={
    version:'2026-10-06-review1',
    defined:Object.keys(SUMMARIES).length,
    applied,
    unmatched
  };
})();
