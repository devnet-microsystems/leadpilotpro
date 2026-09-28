(function(){
var LP=window.LP;
LP.renderHome=async function(){
  var root=LP.$("#view-home"); LP.page(root,"LeadPilot Pro","Your customer pipeline","Product → discovery → review → controlled outreach.");
  try{
    var s=await LP.api("/api/status"),d=await LP.api("/api/dashboard_stats");
    root.appendChild(LP.el("div",{className:"card hero"},[
      LP.el("div",{},[
        LP.el("div",{className:"eyebrow",text:"Start here"}),
        LP.el("h2",{text:"Find customers for something you already sell."}),
        LP.el("p",{text:"Choose a ready product, run discovery, review evidence and move to controlled outreach."}),
        LP.button("Find customers","btn-good",function(){LP.nav("find");})
      ]),
      LP.el("div",{className:"hero-side"},[
        LP.el("div",{className:"next-step"},[
          LP.el("small",{text:"Review queue"}),LP.el("strong",{text:String(Number(s.pending||0))+" leads"}),
          LP.el("small",{text:String(Number(s.sent||0))+" emails sent",style:"display:block;margin-top:10px"})
        ])
      ])
    ]));
    var stats=LP.el("div",{className:"grid stats"});
    [["Leads found",s.total||0],["Qualified",d.qualified_leads||0],["Approved",s.approved||0],["Sent",s.sent||0]].forEach(function(p){
      stats.appendChild(LP.el("div",{className:"card stat"},[LP.el("div",{className:"label",text:p[0]}),LP.el("div",{className:"value",text:String(p[1])})]));
    });
    root.appendChild(stats); root.appendChild(LP.card([LP.note("Main path: Product → discovery → evidence → outreach. Technical controls stay out of this path.","good")]));
  }catch(e){root.appendChild(LP.note(e.message,"bad"))}
};
})();