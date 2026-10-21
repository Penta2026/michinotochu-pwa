"use strict";
/* Compact explanations on every category screen. Retains the full original wording. */
(function(){
function compactHelp(){
  const sections=document.querySelectorAll("section.view:not(#home)");
  let serial=0;
  for(const section of sections){
    const candidates=section.querySelectorAll(".screen-body .note, .screen-body .lead, #browse .note");
    for(const node of candidates){
      if(node.id || node.closest(".result,.spot-grid,.tour-selected,.tour-event-results,.tour-result-count,.trip-history-heading,.contact-form,.modal"))continue;
      if(node.matches("[role], [aria-live]") || node.querySelector("button,input,select,textarea,details,[role=status],[aria-live]"))continue;
      if(node.closest("details,.compact-help") || node.classList.contains("compact-help-done"))continue;
      if(!node.textContent || !node.textContent.trim())continue;
      const details=document.createElement("details");
      details.className="compact-help";
      details.id="compact-help-"+(++serial);
      const summary=document.createElement("summary");
      summary.setAttribute("aria-label","説明・注意事項を表示");
      summary.textContent="ⓘ 説明・注意";
      const content=document.createElement("div");
      content.className="compact-help-content";
      node.classList.add("compact-help-done");
      node.parentNode.insertBefore(details,node);
      content.appendChild(node);
      details.append(summary,content);
    }
  }
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",compactHelp,{once:true});
else compactHelp();
})();
