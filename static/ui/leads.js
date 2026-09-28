(function(){
var LP=window.LP;
LP.renderLeads=async function(){
  var root=LP.$("#view-leads");LP.page(root,"Pipeline","Leads","Review prospects or inspect company rollups.");
  var panel=LP.card([]),tabs=LP.el("div",{className:"tabs"});
  [["pending","Review"],["approved","Approved"],["rejected","Rejected"],["companies","Companies"]].forEach(function(x){tabs.appendChild(LP.el("button",{className:"tab-btn "+(LP.state.leadTab===x[0]?"active":""),text:x[1],onClick:function(){LP.state.leadTab=x[0];LP.renderLeads();}}))});
  panel.appendChild(tabs);panel.appendChild(LP.el("div",{id:"lead-body"}));root.appendChild(panel);
  root.appendChild(LP.el("div",{className:"actions",style:"justify-content:flex-start"},[
    LP.button("Add lead","btn-secondary",LP.openLeadModal),
    LP.button("CSV / advanced contacts","btn-secondary",function(){window.open("/static/old/index.html","_blank")})
  ]));
  await LP.drawLeads();
};
LP.drawLeads=async function(){
  var root=LP.$("#lead-body");LP.clear(root);
  if(LP.state.leadTab==="companies"){
    var c=await LP.api("/api/companies");var companies=c.companies||[];
    if(!companies.length){root.appendChild(LP.el("div",{className:"empty",text:"No companies yet."}));return;}
    var table='<div class="table-wrap"><table class="table"><thead><tr><th>Company</th><th>Leads</th><th>Qualified</th><th>Score</th></tr></thead><tbody>';
    companies.forEach(function(x){table+='<tr><td>'+LP.esc(x.company_name)+'</td><td>'+Number(x.lead_count||0)+'</td><td>'+Number(x.qualified_leads||0)+'</td><td>'+Number(x.best_score||0)+'</td></tr>';});
    table+="</tbody></table></div>";root.innerHTML=table;return;
  }
  var status=LP.state.leadTab==="pending"?"pending_review":LP.state.leadTab,rows=await LP.api("/api/prospects?status="+status);
  if(!rows.length){root.appendChild(LP.el("div",{className:"empty",text:"No leads here."}));return;}
  var table='<div class="table-wrap"><table class="table"><thead><tr><th>Company</th><th>Email</th><th>Score</th><th>Why matched</th><th>Action</th></tr></thead><tbody>';
  rows.forEach(function(x){
    var action=LP.state.leadTab==="pending"?"<button class='btn-good one-a' data-id='"+Number(x.id)+"'>Approve</button><button class='btn-danger one-r' data-id='"+Number(x.id)+"'>Reject</button>":
      LP.state.leadTab==="rejected"?"<button class='btn-secondary one-s' data-id='"+Number(x.id)+"'>Restore</button>":"<span class='pill good'>Approved</span>";
    table+="<tr><td>"+LP.esc(x.company_name||"")+"</td><td>"+LP.esc(x.business_email||"")+"</td><td>"+Math.round(x.relevance_score||0)+"</td><td>"+LP.esc(x.why_matched||"—")+"</td><td>"+action+"</td></tr>";
  });
  table+="</tbody></table></div>";root.innerHTML=table;
  root.querySelectorAll(".one-a").forEach(function(b){b.onclick=function(){LP.leadAction("approve",Number(b.dataset.id))}});
  root.querySelectorAll(".one-r").forEach(function(b){b.onclick=function(){LP.leadAction("reject",Number(b.dataset.id))}});
  root.querySelectorAll(".one-s").forEach(function(b){b.onclick=function(){LP.leadAction("restore",Number(b.dataset.id))}});
};
LP.leadAction=async function(a,id){
  try{
    if(a==="approve")await LP.api("/api/approve",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:id,reason:"Approved from LeadPilot review"})});
    else if(a==="reject")await LP.api("/api/reject_selected",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({ids:[id]})});
    else await LP.api("/api/restore",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:id})});
    LP.toast("Lead updated","good");await LP.drawLeads();
  }catch(e){LP.toast(e.message,"error")}
};
LP.openLeadModal=function(){
  var body=LP.modal("Add lead","Manual entry still uses the existing backend validation.");
  body.innerHTML='<div class="grid two"><div class="field"><label>Company</label><input id="m-company" class="input"></div><div class="field"><label>Business email</label><input id="m-email" class="input" type="email"></div><div class="field"><label>Campaign</label><input id="m-campaign" class="input"></div></div><div class="actions"><button id="m-add" class="btn-good">Add lead</button></div>';
  $("#m-add").onclick=async function(){
    try{
      var d=await LP.api("/api/prospects/manual_add",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({company_name:$("#m-company").value,email:$("#m-email").value,campaign:$("#m-campaign").value})});
      if(!d.success)throw new Error(d.error);LP.toast("Lead added","good");LP.closeModal();LP.renderLeads();
    }catch(e){LP.toast(e.message,"error")}
  };
};
})();