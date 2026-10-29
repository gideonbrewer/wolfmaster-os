// Prepared endpoint only. Not deployed; no provider credential storage is wired.
import {createTickTickHandler,DISABLED_TICKTICK_POLICY} from '../_shared/ticktick-handler.mjs';

Deno.serve(createTickTickHandler({
  policy: DISABLED_TICKTICK_POLICY,
  authenticate: async (authorization: string) => {
    const base=Deno.env.get('SUPABASE_URL');
    const publishable=Deno.env.get('SUPABASE_ANON_KEY');
    if(!base||!publishable) return null;
    const url=new URL(base);
    if(url.protocol!=='https:'||!url.hostname.endsWith('.supabase.co')||url.pathname!=='/') return null;
    // Supabase verifies the access token server-side. Never trust decoded client
    // claims, body.userId, user_metadata, or a browser-provided TickTick token.
    const res=await fetch(new URL('/auth/v1/user',url),{
      headers:{Authorization:authorization,apikey:publishable},
      redirect:'error',signal:AbortSignal.timeout(10000),
    });
    if(!res.ok) return null;
    const user=await res.json();
    return {id:user.id,isAnonymous:user.is_anonymous};
  },
  // Replace only after separate secure provisioning and account/owner validation.
  // No token is read from env, browser storage, public tables or ChatGPT here.
  resolveCredential: async () => null,
  operationStore: null,
  rateLimiter: null,
}));
