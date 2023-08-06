-- insert values into addrtext

-- Creates the two token phrases
-- to do: create the phrase made from pairs of trigrams
insert into phrase
with tokens_pre1 as 
(
select addr_id, unnest(string_to_array(regexp_replace(trim(addr), '[^A-Z0-9]+', ' ', 'g'), ' ')) token
from addrtext
),
tokens_pre2 as 
(
select addr_id, row_number() over () row_num, token
from tokens_pre1
),
tokens as 
(
select addr_id, row_number() over (partition by addr_id order by row_num) row_num, token from tokens_pre2
)
select t1.addr_id, t1.token || ' ' || t2.token tokenphrase
from tokens t1
left join tokens t2
on (t1.addr_id, t1.row_num)=(t2.addr_id, t2.row_num-1)
where tokenphrase is not null;