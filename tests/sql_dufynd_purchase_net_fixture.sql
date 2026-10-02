-- CI-only deterministic HTTP transport; production consumes pg_net responses.
create schema net;
create table net._http_response(id bigserial primary key,status_code int,content text,created timestamptz default clock_timestamp(),timed_out boolean default false,error_msg text);
create function net.http_get(url text,headers jsonb,timeout_milliseconds int) returns bigint language plpgsql as $$
declare rid bigint;
begin
 insert into net._http_response(status_code,content) values(200,case when url like '%versandbedingungen' then 'pauschal mit 4,99 € pro Bestellung'
 else '<h1 id="product-name">Paco Rabanne 1 Million Eau de Toilette 100 ml</h1> "productName":"Paco Rabanne 1 Million Eau de Toilette 100 ml","productSku":"16978322","productPrice":"71.9000" <meta itemprop="gtin13" content="3349666007921" /> <meta itemprop="availability" content="InStock" />' end) returning id into rid;
 return rid;
end $$;
