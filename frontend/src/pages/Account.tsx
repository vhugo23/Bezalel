import { useState } from 'react';
import { Link } from 'react-router';
import { apiFetch, apiJson } from '../api/client';
import { useAuth } from '../components/Accounts';
import { Shell } from '../components/Shell';
import { Button, ErrorNotice } from '../components/ui';

export function AccountPage() {
 const auth=useAuth();const [busy,setBusy]=useState(false);const [error,setError]=useState<unknown>();const [done,setDone]=useState(false);
 async function download(){
  setBusy(true);setError(undefined);setDone(false);
  try{
   const response=await apiFetch('/account/export');
   if(!response.ok)throw new Error('Could not export your account. Please retry.');
   const data=await apiJson(response);
   const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
   const link=document.createElement('a');link.href=url;link.download='prepcrew-account.json';document.body.append(link);link.click();link.remove();
   window.setTimeout(()=>URL.revokeObjectURL(url),1000);setDone(true);
  }catch(e){setError(e);}finally{setBusy(false);}
 }
 return <Shell crumb="Account"><main className="page"><div className="wrap"><section className="card lesson-body">
  <h1>Your account</h1><p>{auth?.state?.user?.name} · {auth?.state?.user?.email}</p>
  <h2>Download your practice</h2><p>Save a JSON copy of your account details and saved practice records. The download includes whiteboard elements and snapshot metadata; image files and downloaded speech models are excluded.</p>
  <ErrorNotice error={error}/><Button disabled={busy} onClick={()=>void download()}>{busy?'Preparing download…':'Download my data'}</Button>{done&&<p role="status">Your export is ready. Check your browser downloads.</p>}
  <h2>Account access</h2><p>Password recovery and self-service account deletion are not available in this demo. Signing out keeps your saved practice available for your next sign-in.</p>
  <p><Link to="/privacy">Read about your practice data</Link></p>
 </section></div></main></Shell>;
}
