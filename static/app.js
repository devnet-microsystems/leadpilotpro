(function(){
"use strict";
window.addEventListener("beforeunload",function(){if(window.LP&&LP.state&&LP.state.poll)clearInterval(LP.state.poll);});
if(window.LP)LP.nav("home");
})();