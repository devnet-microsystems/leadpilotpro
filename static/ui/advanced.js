(function(){
var LP=window.LP;
LP.renderAdvanced=function(){
  var r=LP.$("view-advanced");
  LP.page(r,"Advanced","System tools","Product management and diagnostics live here. Full research tooling is preserved in static/old.");
  r.innerHTML+='<div class="grid two"><div class="card pad"><h3>Products</h3><p>Create, analyze and delete products.</p><button id="open-products" class="btn-secondary">Open</button></div><div class="card pad"><h3>Diagnostics</h3><p>Health, providers and raw logs.</p><button id="open-diagnostics" class="btn-secondary">Open</button></div><div class="card pad"><h3>Archived advanced tools</h3><p>Manual search, Query Studio, Templates and the full campaign builder.</p><a class="btn-secondary" target="_blank" style="text-decoration:none;display:inline-block;margin-top:12px" href="/static/old/index.html">Open old UI</a></div></div><div id="advanced-body" class="section"></div>';
  LP.$("open-products").onclick=LP.renderProducts;
  LP.$("open-diagnostics").onclick=LP.renderDiagnostics;
};
LP.renderProducts=async function(){
  var r=LP.$("advanced-body"),rows=await LP.api("/api/products");
  r.innerHTML='<div class="card pad"><div class="section-title"><div><h3>Product library</h3><p>'+rows.length+' products</p></div><button id="new-product" class="btn-good">Add product</button></div><div class="table-wrap"><table class="table"><thead><tr><th>ID</th><th>Name</th><th>Status</th><th></th></tr></thead><tbody>'+rows.map(function(p){return'<tr><td>'+Number(p.id)+'</td><td>'+LP.esc(p.name)+'</td><td>'+LP.esc(p.status)+'</td><td><button class="btn-danger delp" data-id="'+Number(p.id)+'">Delete</button></td></tr>'}).join("")+'</tbody></table></div></div>';
  LP.$("new-product").onclick=LP.openProduct;
  r.querySelectorAll(".delp").forEach(function(b){b.onclick=function(){LP.deleteProduct(Number(b.dataset.id))}});
};
LP.openProduct=function(){
  var body=LP.modal("New product","Add URL, PDF or text and start Product Intelligence.");
  body.innerHTML='<div class="grid two"><div class="field"><label>Name</label><input id="prod-name" class="input"></div><div class="field"><label>Source</label><select id="prod-type" class="control"><option value="URL">URL</option><option value="PDF">PDF</option><option value="TEXT">Text</option></select></div></div><div id="prod-source"></div><div class="actions"><button id="prod-create" class="btn-good">Create & analyze</button></div>';
  function draw(){var t=LP.$("prod-type").value;LP.$("prod-source").innerHTML=t==="URL"?'<div class="field"><label>URL</label><input id="prod-url" class="input"></div>':t==="PDF"?'<div class="field"><label>PDF</label><input id="prod-pdf" class="input" type="file" accept=".pdf,application/pdf"></div>':'<div class="field"><label>Text</label><textarea id="prod-text" rows="9"></textarea></div>'}
  draw();LP.$("prod-type").onchange=draw;
  LP.$("prod-create").onclick=async function(){
    try{
      var p=await LP.api("/api/products",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:LP.$("prod-name").value.trim()})});
      if(LP.$("prod-type").value==="URL")await LP.api("/api/products/"+p.id+"/sources",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source_type:"URL",content:LP.$("prod-url").value})});
      else if(LP.$("prod-type").value==="TEXT")await LP.api("/api/products/"+p.id+"/sources",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({source_type:"TEXT",content:LP.$("prod-text").value})});
      else{var f=LP.$("prod-pdf").files[0];if(!f)throw Error("Select a PDF");var fd=new FormData();fd.append("file",f);await LP.api("/api/products/"+p.id+"/sources/pdf",{method:"POST",body:fd})}
      await LP.api("/api/products/"+p.id+"/analyze",{method:"POST"});LP.closeModal();LP.toast("Product analysis started","good");LP.renderProducts();
    }catch(e){LP.toast(e.message,"error")}
  };
};
LP.deleteProduct=async function(id){
  var p=await LP.api("/api/products/"+id);if(!confirm("Delete "+p.name+"? Product-owned data is removed; global prospects remain."))return;
  try{await LP.api("/api/products/"+id,{method:"DELETE"});LP.toast("Product deleted","good");LP.renderProducts()}catch(e){LP.toast(e.message,"error")}
};
LP.renderDiagnostics=async function(){
  var r=LP.$("advanced-body");LP.clear(r);
  try{
    var h=await LP.api("/health"),p=await LP.api("/api/search_providers");
    r.appendChild(LP.card([LP.note("Health: "+(h.status||"unknown")+" · database: "+String(h.database),h.status==="ok"?"good":"bad")]));
    p.forEach(function(x){
      r.appendChild(LP.card([LP.el("div",{className:"provider"},[
        LP.el("div",{},[LP.el("strong",{text:x.name}),LP.el("small",{text:"Enabled: "+String(x.enabled)})]),
        LP.el("span",{className:"pill "+(x.enabled?"good":"warn"),text:x.enabled?"ON":"OFF"})
      ])]));
    });
    var logs=await Promise.all([
      LP.api("/api/system_logs").catch(function(){return{logs:""}}),
      LP.api("/api/research_logs").catch(function(){return{logs:""}}),
      LP.api("/api/send_logs").catch(function(){return{logs:""}})
    ]);
    ["System log","Research log","Sender log"].forEach(function(name,i){
      r.appendChild(LP.card([LP.el("h3",{text:name}),LP.el("pre",{className:"logbox",text:logs[i].logs||""})]));
    });
  }catch(e){r.appendChild(LP.note(e.message,"bad"))}
}
})();