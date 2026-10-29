import { PGlite } from '@electric-sql/pglite';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const migration=new URL('../../supabase/migrations/20261029091011_finance_snapshots_owner_scope.sql',import.meta.url);
const db=new PGlite();
const A='11111111-1111-4111-8111-111111111111',B='22222222-2222-4222-8222-222222222222';
let checks=0;
const eq=(actual,expected,label)=>{assert.deepEqual(actual,expected,label);checks++;};
async function deny(sql,params=[],code='42501'){await assert.rejects(db.query(sql,params),e=>e.code===code,sql);checks++;}
async function role(name,user,claims={is_anonymous:false}){
 await db.exec('reset role');
 await db.query("select set_config('request.jwt.claims',$1,false)",[JSON.stringify({sub:user,...claims})]);
 await db.exec('set role '+name);
}
try{
 // Only in-memory scaffolding. No Supabase endpoint, account creation, or live rows.
 await db.exec(`create role anon nologin;create role authenticated nologin;
 create schema auth;create table auth.users(id uuid primary key);
 create function auth.jwt() returns jsonb language sql stable as $$ select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb $$;
 create function auth.uid() returns uuid language sql stable as $$ select nullif(auth.jwt()->>'sub','')::uuid $$;
 grant usage on schema public,auth to anon,authenticated;
 grant execute on function auth.jwt(),auth.uid() to anon,authenticated;
 create table public.legacy_sentinel(id int primary key,value text);
 insert into public.legacy_sentinel values (1,'untouched');
 alter default privileges in schema public grant all on tables to anon,authenticated;`);
 await db.query('insert into auth.users values ($1),($2)',[A,B]);
 await db.exec(await readFile(migration,'utf8'));
 const flags=(await db.query("select relrowsecurity,relforcerowsecurity from pg_class where oid='public.finance_snapshots'::regclass")).rows[0];
 eq(flags,{relrowsecurity:true,relforcerowsecurity:true},'RLS enabled and forced');
 eq((await db.query("select value from public.legacy_sentinel")).rows[0].value,'untouched');
 eq((await db.query("select count(*)::int n from pg_policies where tablename='finance_snapshots'")).rows[0].n,5);
 for(const privilege of ['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'])eq((await db.query("select has_table_privilege('anon','public.finance_snapshots',$1) allowed",[privilege])).rows[0].allowed,false,'anon '+privilege);
 for(const privilege of ['TRUNCATE','REFERENCES','TRIGGER'])eq((await db.query("select has_table_privilege('authenticated','public.finance_snapshots',$1) allowed",[privilege])).rows[0].allowed,false,'authenticated '+privilege);
 await role('authenticated',A);
 const insert="insert into public.finance_snapshots(kind,as_of_date,currency,coverage,work) values ('earnings','2026-01-01','USD','Synthetic coverage',100) returning id,user_id,revision";
 const a=(await db.query(insert)).rows[0];eq(a.user_id,A);eq(Number(a.revision),1);
 const update=(await db.query('update public.finance_snapshots set work=125,revision=99 where id=$1 and revision=1 returning work,revision',[a.id])).rows[0];eq(update.work,'125.00');eq(Number(update.revision),2);
 eq((await db.query('update public.finance_snapshots set work=150 where id=$1 and revision=1 returning id',[a.id])).rows.length,0,'stale revision cannot overwrite');
 await deny('update public.finance_snapshots set user_id=$1 where id=$2',[B,a.id]);
 await deny("insert into public.finance_snapshots(user_id,kind,as_of_date,currency,coverage,assets,liabilities) values ($1,'worth','2026-01-01','USD','Synthetic',100,0)",[B]);
 await deny('update public.finance_snapshots set id=gen_random_uuid() where id=$1',[a.id],'23514');
 for(const [column,value] of [['work','NaN'],['work','-1'],['mining_expenses','-1'],['assets','1']])await deny(`update public.finance_snapshots set ${column}=$1 where id=$2`,[value,a.id],'23514');
 await deny("update public.finance_snapshots set as_of_date=current_date+1 where id=$1",[a.id],'23514');
 await deny("update public.finance_snapshots set coverage='' where id=$1",[a.id],'23514');
 await deny('truncate public.finance_snapshots');
 await role('authenticated',B);
 eq((await db.query('select * from public.finance_snapshots')).rows.length,0,'B cannot see A');
 eq((await db.query('update public.finance_snapshots set work=999 where id=$1 returning id',[a.id])).rows.length,0,'B cannot update A');
 eq((await db.query('delete from public.finance_snapshots where id=$1 returning id',[a.id])).rows.length,0,'B cannot delete A');
 const b=(await db.query(insert)).rows[0];eq(b.user_id,B,'same date/currency allowed for another owner');
 await deny("insert into public.finance_snapshots(id,user_id,kind,as_of_date,currency,coverage,work) values ($1,$2,'earnings','2026-01-01','USD','Attack',999) on conflict(id) do update set work=999",[a.id,A]);
 await role('authenticated',A,{is_anonymous:true});
 eq((await db.query('select * from public.finance_snapshots')).rows.length,0,'anonymous auth user cannot read own data');await deny(insert);
 await role('authenticated',A,{});eq((await db.query('select * from public.finance_snapshots')).rows.length,0,'missing anonymous flag denied');await deny(insert);
 await role('authenticated',null);eq((await db.query('select * from public.finance_snapshots')).rows.length,0,'missing user denied');await deny(insert);
 await role('anon',A);await deny('select * from public.finance_snapshots');await deny(insert);await deny('update public.finance_snapshots set work=0');await deny('delete from public.finance_snapshots');
 await role('authenticated',A);eq((await db.query('delete from public.finance_snapshots where id=$1 returning id',[a.id])).rows.length,1,'owner delete');
 await role('authenticated',B);eq((await db.query('select id from public.finance_snapshots')).rows.length,1,'owner isolation after deletion');
 console.log(`Finance RLS: ${checks} assertions passed against the exact migration in isolated PostgreSQL (PGlite). No live Supabase access.`);
}finally{await db.close();}
