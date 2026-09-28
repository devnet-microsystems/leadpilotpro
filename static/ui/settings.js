(function(){
var LP=window.LP;
LP.renderSettings=async function(){
  var root=LP.LP.$("view-settings");LP.page(root,"Configuration","Settings","Company mail, AI and provider state.");
  try{
    var x=await Promise.all([LP.api("/api/settings"),LP.api("/api/search_providers")]),s=x[0],p=x[1];
    root.insertAdjacentHTML("beforeend",'<div class="settings-grid"><div id="mail-card"></div><div id="ai-card"></div></div><div id="provider-card" class="section"></div>');
    LP.$("mail-card").innerHTML='<div class="card pad"><h3>Company & mail</h3><div class="grid two">'+
      '<div class="field"><label>Company</label><input id="sn" class="input" value="'+LP.esc(s.company_name||"")+'"></div>'+
      '<div class="field"><label>Website</label><input id="sw" class="input" value="'+LP.esc(s.company_website||"")+'"></div>'+
      '<div class="field"><label>SMTP host</label><input id="sh" class="input" value="'+LP.esc(s.smtp_host||"")+'"></div>'+
      '<div class="field"><label>SMTP port</label><input id="sp" class="input" value="'+LP.esc(s.smtp_port||"")+'"></div>'+
      '<div class="field"><label>SMTP user</label><input id="su" class="input" value="'+LP.esc(s.smtp_user||"")+'"></div>'+
      '<div class="field"><label>SMTP password</label><input id="sx" class="input" type="password" value="'+LP.esc(s.smtp_password||"")+'"></div>'+
      '<div class="field"><label>From email</label><input id="sf" class="input" value="'+LP.esc(s.smtp_from_email||"")+'"></div>'+
      '<div class="field"><label>IMAP host</label><input id="ih" class="input" value="'+LP.esc(s.imap_host||"")+'"></div>'+
      '<div class="field"><label>IMAP port</label><input id="ip" class="input" value="'+LP.esc(s.imap_port||"993")+'"></div>'+
      '<div class="field"><label>Daily limit</label><input id="dl" class="input" value="'+LP.esc(s.daily_limit||"50")+'"></div>'+
      '<div class="field"><label>Min delay</label><input id="dm" class="input" value="'+LP.esc(s.delay_minimum||"30")+'"></div>'+
      '<div class="field"><label>Max delay</label><input id="dx" class="input" value="'+LP.esc(s.delay_maximum||"90")+'"></div>'+
      '</div><div class="actions"><button id="save-settings" class="btn-primary">Save settings</button></div></div>';
    LP.$("ai-card").innerHTML='<div class="card pad"><h3>AI provider</h3><div class="grid">'+
      '<div class="field"><label>API key</label><input id="ai-key" class="input" type="password" value="'+LP.esc(s.ai_api_key||"")+'"></div>'+
      '<div class="field"><label>Base URL</label><input id="ai-url" class="input" value="'+LP.esc(s.ai_base_url||"https://api.openai.com/v1")+'"></div>'+
      '<div class="field"><label>Model</label><input id="ai-model" class="input" value="'+LP.esc(s.ai_model||"gpt-4o")+'"></div>'+
      '</div></div>';
    var ph='<div class="card pad"><h3>Search providers</h3><p>Runtime switches. Browser fallback remains available when none is enabled.</p><div class="grid">';
    p.forEach(function(z){ph+='<div class="provider"><div><strong>'+LP.esc(z.name)+'</strong><small>'+LP.esc(z.name==="DuckDuckGo"?"Headless public-web search":"Configured provider")+'</small></div><input data-provider="'+LP.esc(z.id)+'" type="checkbox" '+(z.enabled?"checked":"")+'></div>'});
    ph+='</div><div class="actions"><button id="save-providers" class="btn-primary">Save providers</button></div></div>';
    LP.$("provider-card").innerHTML=ph;LP.$("save-settings").onclick=function(){save(s)};LP.$("save-providers").onclick=function(){save(s)};
  }catch(e){root.appendChild(LP.note(e.message,"bad"))}
};
async function save(old){
  function v(id){var x=LP.LP.$(""+id);return x?x.value:""}function on(id){var x=document.querySelector('[data-provider="'+id+'"]');return x&&x.checked?"true":"false"}
  var p={smtp_host:v("sh"),smtp_port:v("sp"),smtp_user:v("su"),smtp_password:v("sx"),smtp_from_email:v("sf"),company_name:v("sn"),company_website:v("sw"),daily_limit:v("dl"),delay_minimum:v("dm"),delay_maximum:v("dx"),ai_api_key:v("ai-key"),ai_base_url:v("ai-url"),ai_model:v("ai-model"),ddg_enabled:on("DuckDuckGoProvider"),searxng_enabled:on("SearXNGProvider"),searxng_url:old.searxng_url||"",brave_enabled:on("BraveProvider"),brave_api_key:old.brave_api_key||"",lusha_api_key:old.lusha_api_key||"",imap_host:v("ih"),imap_port:v("ip")};
  try{await LP.api("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)});LP.toast("Settings saved","good");LP.renderSettings()}catch(e){LP.toast(e.message,"error")}
}
})();