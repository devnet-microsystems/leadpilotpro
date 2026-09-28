(function(){
"use strict";
window.LP = window.LP || {};
LP.state = { view:"home", products:[], productId:null, pipeline:null, evidence:[], leadTab:"pending", outTab:"queue", poll:null };
LP.$ = function(s,r){ return (r||document).querySelector(s); };
LP.$$ = function(s,r){ return Array.prototype.slice.call((r||document).querySelectorAll(s)); };
LP.clear = function(n){ while(n && n.firstChild)n.removeChild(n.firstChild); };
LP.esc = function(v){ var d=document.createElement("div"); d.textContent=String(v==null?"":v); return d.innerHTML; };
LP.api = async function(url,opts){
  var r=await fetch(url,opts||{}),d={}; try{d=await r.json();}catch(e){}
  if(!r.ok)throw new Error(d.detail||d.error||"Request failed"); return d;
};
LP.toast = function(message,kind){
  var root=LP.$("#toast-root"),n=document.createElement("div"); n.className="toast "+(kind||""); n.textContent=message; root.appendChild(n);
  setTimeout(function(){n.remove();},3400);
};
window.showToast=LP.toast;
LP.el=function(tag,attrs,children){
  var n=document.createElement(tag),k; attrs=attrs||{};
  for(k in attrs){if(!Object.prototype.hasOwnProperty.call(attrs,k))continue;
    if(k==="text")n.textContent=attrs[k]; else if(k==="className")n.className=attrs[k];
    else if(k.indexOf("on")===0)n.addEventListener(k.slice(2).toLowerCase(),attrs[k]); else n.setAttribute(k,attrs[k]);
  }
  (children||[]).forEach(function(c){n.appendChild(typeof c==="string"?document.createTextNode(c):c);}); return n;
};
LP.page=function(root,kicker,title,subtitle){
  LP.clear(root); root.appendChild(LP.el("div",{className:"page-head"},[
    LP.el("div",{},[LP.el("div",{className:"eyebrow",text:kicker}),LP.el("h1",{text:title}),LP.el("p",{text:subtitle})])
  ]));
};
LP.card=function(children,extra){return LP.el("div",{className:"card pad "+(extra||"")},children)};
LP.button=function(label,kind,fn){return LP.el("button",{className:kind||"btn-primary",text:label,onClick:fn})};
LP.note=function(text,kind){return LP.el("div",{className:"notice "+(kind||""),text:text})};
LP.modal=function(title,subtitle){
  var root=LP.$("#modal-root"); LP.clear(root);
  root.appendChild(LP.el("div",{className:"modal-backdrop"},[
    LP.el("div",{className:"modal"},[
      LP.el("div",{className:"section-title"},[
        LP.el("div",{},[LP.el("h3",{text:title}),LP.el("p",{text:subtitle||""})]),
        LP.button("Close","btn-secondary",LP.closeModal)
      ]),
      LP.el("div",{id:"modal-body"})
    ])
  ]));
  return LP.$("#modal-body");
};
LP.closeModal=function(){LP.clear(LP.$("#modal-root"));};
LP.nav=function(view){
  LP.state.view=view;
  LP.$$(".nav-btn").forEach(function(b){b.classList.toggle("active",b.dataset.view===view)});
  LP.$$(".view").forEach(function(v){v.classList.remove("active")});
  var target=LP.$("#view-"+view); if(target)target.classList.add("active");
  if(view==="home"&&LP.renderHome)LP.renderHome();
  if(view==="find"&&LP.renderFind)LP.renderFind();
  if(view==="leads"&&LP.renderLeads)LP.renderLeads();
  if(view==="outreach"&&LP.renderOutreach)LP.renderOutreach();
  if(view==="settings"&&LP.renderSettings)LP.renderSettings();
  if(view==="advanced"&&LP.renderAdvanced)LP.renderAdvanced();
};
window.switchTab=function(v){
  if(v==="overview")return LP.nav("home"); if(v==="orchestrator")return LP.nav("find");
  if(v==="pending"||v==="approved"||v==="rejected"||v==="leads")return LP.nav("leads");
  if(v==="sales_campaigns"||v==="send")return LP.nav("outreach"); if(v==="products")return LP.nav("advanced");
  if(v==="settings"||v==="providers")return LP.nav("settings"); return LP.nav("advanced");
};
})();