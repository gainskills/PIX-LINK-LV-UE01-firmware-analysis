(function(){
  'use strict';
  var form=document.getElementById('ap-login');if(!form)return;
  var zh=/^zh\b/i.test((navigator.languages&&navigator.languages[0])||navigator.language||'');
  var attempted=false;
  try{attempted=sessionStorage.getItem('ap-signin-pending')==='1';}catch(_){}
  var invalid=attempted;
  function render(){
    document.documentElement.lang=zh?'zh-CN':'en';document.title=zh?'登录管理页面':'Sign in';
    document.getElementById('login-language').value=zh?'zh':'en';
    document.getElementById('login-title').textContent=zh?'登录管理页面':'Sign in';
    document.getElementById('login-user-label').textContent=zh?'用户名':'Username';
    document.getElementById('login-pass-label').textContent=zh?'密码':'Password';
    document.getElementById('login-submit').textContent=zh?'登录':'Sign in';
    document.getElementById('login-status').textContent=invalid?(zh?'登录未成功，请检查用户名和密码。':'Sign-in was not accepted. Check your username and password.'):'';
  }
  document.getElementById('login-language').onchange=function(){zh=this.value==='zh';render();};
  form.onsubmit=function(event){
    event.preventDefault();var user=document.getElementById('login-user').value,pass=document.getElementById('login-password').value;
    if(!/^[!-~]{1,30}$/.test(user)||user.includes(':')||!/^[!-~]{1,30}$/.test(pass)){invalid=true;render();return;}
    document.cookie='Authorization=Basic '+btoa(user+':'+pass)+';path=/;SameSite=Lax';
    try{sessionStorage.setItem('ap-signin-pending','1');}catch(_){}
    location.assign('index.htm');
  };
  render();
}());
