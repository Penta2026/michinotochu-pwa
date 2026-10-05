// DB 2.8.21 patch layer: keep generated app_data.js immutable.
// 定番・寄り道スポットは名称検索を正とし、座標は距離計算用として扱う。
(function(){
  const D=window.APP_DATA;
  if(!D||!Array.isArray(D.landmarks))return;

  for(const x of D.landmarks){
    if(x&&((x.level==='A')||(x.level==='B'))){
      x.navMode='name';
      if(!String(x.navQuery||'').trim()){
        x.navQuery=[x.prefecture||'',x.name||''].filter(Boolean).join(' ').trim();
      }
    }
  }

  const mazda=D.landmarks.find(x=>x&&x.name==='マツダミュージアム');
  if(mazda){
    mazda.prefecture='広島県';
    mazda.municipality='安芸郡府中町';
    mazda.lat=34.37802;
    mazda.lng=132.50252;
    mazda.latRaw='34.378020';
    mazda.lngRaw='132.502520';
    mazda.navMode='name';
    mazda.navQuery='広島県 マツダミュージアム';
    mazda.arrivalPointType='名称検索';
    mazda.sourceUrl='https://www.mazda.com/ja/experience/museum/access/';
    mazda.access='名称検索を正とする。公共交通機関利用時はマツダ本社1Fロビー集合後、専用バスでミュージアムへ移動。';
  }

  if(D.meta){
    D.meta.appVersion='2.8.21';
    D.meta.generated='2026-10-05 12:26:00';
  }
  if(window.DATA_META){
    window.DATA_META.appVersion='2.8.21';
    window.DATA_META.generated='2026-10-05 12:26:00';
  }
})();
