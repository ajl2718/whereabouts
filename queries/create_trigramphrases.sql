-- need to test different lengths of md5 substr
-- use phrase table rather than addrtext to generate trigram phrases
insert into trigramphrase
with tokens_pre as (
select addr_id, unnest(str_split(addr, ' ')) token from addrtext --limit 1024--20
),
tokens as (
select addr_id, token, row_number() over (partition by addr_id) row_num from tokens_pre
order by 
addr_id, row_num
),
trigrams as (
select addr_id, row_num, token, substr(token, n1, 3) trigram from tokens, seqs -- seqs
where trigram != ''
and
strlen(trigram) >= 3
order by addr_id, row_num
),
trigramphrases as 
(
select t1.addr_id, t1.trigram || ' ' || t2.trigram trigramphrase
from trigrams t1
left join trigrams t2
on (t1.addr_id, t1.row_num)=(t2.addr_id, t2.row_num-1)
where trigramphrase is not null
)
select addr_id, substr(md5(trigramphrase), 1, 6) md5phrase from trigramphrases;