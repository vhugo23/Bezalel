// getRandomValues also works on a LAN HTTP drawing page; microphone access
// still requires HTTPS. Never replace capability entropy with Math.random.
export function randomId(bytes=16){
 return Array.from(crypto.getRandomValues(new Uint8Array(bytes)),b=>b.toString(16).padStart(2,'0')).join('');
}

export function pairingLink(origin:string,code:string){
 try{
  const url=new URL(origin);
  if(!['http:','https:'].includes(url.protocol)||url.username||url.password)return '';
  return `${url.origin}/pair/${encodeURIComponent(code)}`;
 }catch{return '';}
}
