insert into skipphrase
with addrtext_with_row_num as (
    select 
    addr_id,
    addr,
    row_number() over () row_num
    from addrtext_with_detail
),
addrtext_subset as (
    select * from addrtext_with_row_num
    where row_num % 100 == ?
),
tokens_pre1 as 
(
select addr_id, unnest(string_to_array(regexp_replace(trim(addr), '[^A-ZÀÂĀÆÇÉÈÊËÎÏÔŌŒÙÛÜŸ0-9ĄĆĘŁŃÓŚŹŻ]+', ' ', 'g'), ' ')) token
from addrtext_subset
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
on (t1.addr_id, t1.row_num)=(t2.addr_id, t2.row_num-2) -- 2 for skipphrases, 1 for standard phrases
where tokenphrase is not null;