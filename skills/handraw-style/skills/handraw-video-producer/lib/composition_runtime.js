// Unified frame compositor. Each native renderer has its own window and state.
(() => {
  const C = window.COMPOSITION, cv = document.getElementById('stage');
  cv.width = C.width; cv.height = C.height;
  const g = cv.getContext('2d', {willReadFrequently:true}), W=C.width,H=C.height;
  const resources = new Map(), clamp = n => Math.max(0,Math.min(1,n));
  const sceneBuffers = new Map();
  const subtitleMasks = new Map();
  const key = (s,l) => s.id + '/' + l.id;
  const buffer = () => {const b=document.createElement('canvas');b.width=W;b.height=H;return b;};
  const image = url => new Promise((resolve,reject) => {const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(new Error('Cannot load '+url));im.src=url;});
  const sleep = ms => new Promise(r=>setTimeout(r,ms));
  function interpolate(keys, at, field, fallback) {
    if (!keys || !keys.length) return fallback;
    if (at<=keys[0].at_frame) return keys[0][field];
    let a=keys[0];
    for(let i=1;i<keys.length;i++) {
      const b=keys[i];
      if(at<=b.at_frame) {let p=(at-a.at_frame)/(b.at_frame-a.at_frame);const e=b.easing||'linear';
        if(e==='ease_in')p=p*p;else if(e==='ease_out')p=1-(1-p)*(1-p);else if(e==='ease_in_out')p=p<.5?2*p*p:1-2*(1-p)*(1-p);
        return Array.isArray(a[field])?a[field].map((v,j)=>v+(b[field][j]-v)*p):a[field]+(b[field]-a[field])*p;}
      a=b;
    }
    return a[field];
  }
  function layersAt(scene,f) {
    const events = Object.fromEntries((scene.events||[]).map(x=>[x.id,x.at_frame]));
    return scene.layers.filter(l=>f>=(l.start_frame??0)&&f<(l.end_frame??scene.end_frame-scene.start_frame)
      &&(!l.show_after||f>=events[l.show_after])&&(!l.hide_after||f<events[l.hide_after]));
  }
  function applyMotion(region,m,f){
    if(!m)return region;const r=region.slice(),p=clamp((f-m.start_frame)/(m.end_frame-m.start_frame)),at=Math.max(m.start_frame,Math.min(m.end_frame,f))-m.start_frame;
    let dx=0,dy=0;
    if(m.type==='translate'){dx=m.delta[0]*p;dy=m.delta[1]*p;}
    else if(m.type==='oscillate'||m.type==='orbit'){
      const v=m.amplitude||m.radius,a=2*Math.PI*at/m.period_frames+(m.phase||0),phase=m.phase||0;
      dx=v[0]*(Math.sin(a)-Math.sin(phase));dy=v[1]*((m.type==='orbit'?Math.cos(a):Math.sin(a))-(m.type==='orbit'?Math.cos(phase):Math.sin(phase)));
    }else if(m.type==='path'){
      const q=m.points,u=1-p;let pt;
      if(q.length===2)pt=q[0].map((v,i)=>v+(q[1][i]-v)*p);
      else pt=[0,1].map(i=>u*u*u*q[0][i]+3*u*u*p*q[1][i]+3*u*p*p*q[2][i]+p*p*p*q[3][i]);
      dx=pt[0]-q[0][0];dy=pt[1]-q[0][1];
    }
    r[0]+=dx;r[1]+=dy;return r;
  }
  function active(frame) {
    frame=Math.max(0,Math.min(C.duration_frames-1,frame));
    const i=C.shots.findIndex(s=>frame>=s.start_frame&&frame<s.end_frame),s=C.shots[i];
    const f=frame-s.start_frame, transition=s.transition||{type:'cut',frames:0};
    const n=transition.frames||0;
    return {s,f,previous:i>0&&f<n?C.shots[i-1]:null,p:n?(f+1)/n:1,transition};
  }
  async function pageResource(url,size=[W,H]) {
    const el=document.createElement('iframe');el.style.cssText='position:absolute;left:-100000px;width:'+W+'px;height:'+H+'px;border:0';
    const loaded=new Promise((resolve,reject)=>{el.onload=resolve;el.onerror=()=>reject(new Error('Adapter load failed '+url));});
    el.src=url;document.body.appendChild(el);await loaded;
    const w=el.contentWindow;
    const deadline=performance.now()+30000;
    while(!w.__ready&&!w.ready) {
      if(w.__bootFailed)throw new Error(w.__bootFailed);
      if(performance.now()>deadline)throw new Error('Adapter must expose ready or __ready: '+url);
      await sleep(20);
    }
    if(w.ready) {
      let timer;
      try {await Promise.race([w.ready,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Adapter readiness timed out: '+url)),30000);})]);}
      finally {clearTimeout(timer);}
    }
    await w.document.fonts.ready;
    if(w.__bootFailed)throw new Error(w.__bootFailed);
    if(typeof w.renderFrame!=='function')throw new Error('Adapter lacks renderFrame: '+url);
    const canvas=w.__canvas||w.document.querySelector('canvas');
    if(!canvas||canvas.width!==size[0]||canvas.height!==size[1])throw new Error('Adapter canvas size mismatch: '+url);
    // Errors in isolated documents must fail the parent too.
    w.addEventListener('error', e=>{window.__adapterError=String(e.message);});
    w.addEventListener('unhandledrejection', e=>{window.__adapterError=String(e.reason);});
    return {w,canvas};
  }
  async function boot() {
    await document.fonts.ready;
    for(const s of C.shots) {
      sceneBuffers.set(s.id,buffer());
      for(const l of s.layers) {
        const k=key(s,l);
        if(['image','sprite'].includes(l.adapter))resources.set(k,await image(l.url));
        else if(l.adapter==='video') {
          resources.set(k,{frames:new Map(),current:null});
        } else if(['html'].includes(l.adapter))resources.set(k,await pageResource(l.url,l.native_size));
      }
    }
    window.__ready=true;
  }
  window.ready=boot();
  async function prepareScene(s,f) {
    for(const l of layersAt(s,f)) {
      const r=resources.get(key(s,l));
      if(l.adapter==='video') {
        const index=f-(l.start_frame||0)+1;
        if(index<1||index>l.frame_count)throw new Error('Decoded video frame outside visible range');
        if(!r.frames.has(index))r.frames.set(index,await image(l.frame_base+String(index).padStart(6,'0')+'.png'));
        r.current=r.frames.get(index);
        if(r.frames.size>32)r.frames.delete(r.frames.keys().next().value);
      } else if(r&&r.w) {
        for(const animation of r.w.document.getAnimations()){animation.pause();animation.currentTime=f*1000/C.fps;}
        if(typeof r.w.prepareFrame==='function')await r.w.prepareFrame(f/C.fps);
        await r.w.renderFrame(f/C.fps);
      }
    }
  }
  window.prepareFrame=async t=>{
    await window.ready;
    const a=active(Math.round(t*C.fps));await prepareScene(a.s,a.f);
    if(a.previous)await prepareScene(a.previous,a.previous.end_frame-a.previous.start_frame-1);
    if(window.__adapterError)throw new Error(window.__adapterError);
  };
  function fit(c,source,region,rect,mode='contain') {
    const [x,y,w,h]=region;const iw=source.videoWidth||source.naturalWidth||source.width,ih=source.videoHeight||source.naturalHeight||source.height;
    rect=rect||[0,0,iw,ih];const [sx,sy,sw,sh]=rect;
    if(mode==='stretch') {c.drawImage(source,sx,sy,sw,sh,x,y,w,h);return;}
    const ratio=mode==='cover'?Math.max(w/sw,h/sh):Math.min(w/sw,h/sh),dw=sw*ratio,dh=sh*ratio;
    c.save();c.beginPath();c.rect(x,y,w,h);c.clip();c.drawImage(source,sx,sy,sw,sh,x+(w-dw)/2,y+(h-dh)/2,dw,dh);c.restore();
  }
  function text(c,value,region,scale,color,weight=600) {
    const [x,y,w,h]=region,size=scale||Math.min(W,H)*.045;
    c.font=`${weight} ${size}px "Microsoft YaHei",sans-serif`;c.textBaseline='top';c.fillStyle=color||'#242b38';
    const lines=[];let current='';
    for(const ch of String(value)) {
      if(ch==='\n'){lines.push(current);current='';continue;}
      if(c.measureText(current+ch).width>w&&current){lines.push(current);current='';}
      if(c.measureText(ch).width>w)throw new Error('Text region too narrow');current+=ch;
    }
    if(current)lines.push(current);
    if(lines.length*size*1.3>h)throw new Error('Text overflows; shorten or reflow: '+value);
    lines.forEach((line,i)=>c.fillText(line,x,y+i*size*1.3));
  }
  function drawScene(s,f) {
    const b=sceneBuffers.get(s.id),c=b.getContext('2d',{willReadFrequently:true});
    c.resetTransform();c.clearRect(0,0,W,H);c.fillStyle=s.paper||C.paper;c.fillRect(0,0,W,H);
    c.save();const view=interpolate(s.camera?.keyframes,f,'view',[0,0,1,1]);
    c.scale(1/view[2],1/view[3]);c.translate(-view[0]*W,-view[1]*H);
    for(const l of layersAt(s,f)) {
      c.save();const r=resources.get(key(s,l));
      let rn=interpolate(l.keyframes,f,'region',l.region||[0,0,1,1]);rn=applyMotion(rn,l.motion,f);const region=[rn[0]*W,rn[1]*H,rn[2]*W,rn[3]*H];
      const rotation=interpolate(l.rotation_keyframes,f,'rotation',l.rotation||0);if(rotation){c.translate(region[0]+region[2]/2,region[1]+region[3]/2);c.rotate(rotation*Math.PI/180);c.translate(-region[0]-region[2]/2,-region[1]-region[3]/2);}
      c.globalAlpha=interpolate(l.opacity_keyframes,f,'opacity',l.opacity??1);
      if(l.reveal_frames)c.globalAlpha*=clamp((f-(l.start_frame||0)+1)/l.reveal_frames);
      if(['image','video','sprite'].includes(l.adapter)) {
        let rect=l.source_rect;
        const frames=l.frames||[];
        if(frames.length) {let selected=frames[0];for(const q of frames)if(q.at_frame<=f)selected=q;rect=selected.source_rect;}
        fit(c,l.adapter==='video'?r.current:r,region,rect,l.fit||'contain');
      } else if(r&&r.w) {
        fit(c,r.canvas,region,null,l.fit||'stretch');
      } else if(l.adapter==='highlight') {
        if(l.fill){c.fillStyle=l.fill;c.fillRect(...region);}
        c.strokeStyle=l.color||'#f6762b';c.lineWidth=l.line_width||Math.min(W,H)*.008;
        c.strokeRect(...region);
      } else if(l.adapter==='text')text(c,l.text,region,l.font_size,l.color,l.weight);
      else if(l.adapter==='path') {
        const p=l.reveal_frames?clamp((f-(l.start_frame||0)+1)/l.reveal_frames):1;
        const points=l.points.map(v=>[region[0]+v[0]*region[2],region[1]+v[1]*region[3]]);
        const lengths=points.slice(1).map((v,i)=>Math.hypot(v[0]-points[i][0],v[1]-points[i][1]));let remain=lengths.reduce((a,b)=>a+b,0)*p;
        c.strokeStyle=l.color||'#194ac8';c.lineWidth=l.line_width||Math.min(W,H)*.005;c.lineCap='round';c.lineJoin='round';c.beginPath();c.moveTo(...points[0]);
        for(let i=0;i<lengths.length&&remain>0;i++){const k=Math.min(1,remain/(lengths[i]||1));c.lineTo(points[i][0]+(points[i+1][0]-points[i][0])*k,points[i][1]+(points[i+1][1]-points[i][1])*k);remain-=lengths[i];}c.stroke();
      }
      c.restore();
    }
    c.restore();return b;
  }
  window.renderFrame=async t=>{
    await window.prepareFrame(t);
    const frame=Math.max(0,Math.min(C.duration_frames-1,Math.round(t*C.fps))),a=active(frame);
    g.resetTransform();g.clearRect(0,0,W,H);
    if(a.previous) {
      g.drawImage(drawScene(a.previous,a.previous.end_frame-a.previous.start_frame-1),0,0);
      g.save();
      if(a.transition.type==='wipe'){g.beginPath();g.rect(0,0,W*a.p,H);g.clip();}else g.globalAlpha=a.p;
      g.drawImage(drawScene(a.s,a.f),0,0);g.restore();
    }else g.drawImage(drawScene(a.s,a.f),0,0);
    if(C.subtitle_mode==='burn-in') {
      const sub=C.subtitles.find(q=>frame/C.fps>=q.start&&frame/C.fps<q.end);
      if(sub){
        // Explicit integer blending avoids GPU/CPU alpha rounding changes after reload.
        const x=Math.round(W*.05),y=Math.round(H*.84),w=Math.round(W*.9),h=Math.round(H*.13);
        if(!subtitleMasks.has(sub.text)){
          const mask=buffer(),mc=mask.getContext('2d',{willReadFrequently:true});
          text(mc,sub.text,[W*.08,H*.86,W*.84,H*.09],Math.min(W,H)*.032);
          subtitleMasks.set(sub.text,mc.getImageData(x,y,w,h).data);
        }
        const panel=g.getImageData(x,y,w,h),d=panel.data,color=[252,247,234],mask=subtitleMasks.get(sub.text);
        for(let i=0;i<d.length;i+=4){
          const a=mask[i+3]/255;
          for(let c=0;c<3;c++)d[i+c]=Math.round(Math.round(d[i+c]*.06+color[c]*.94)*(1-a)+mask[i+c]*a);
          d[i+3]=255;
        }
        g.putImageData(panel,x,y);
      }
    }
    if(window.__adapterError)throw new Error(window.__adapterError);
    return cv.toDataURL('image/png').split(',')[1];
  };
})();
