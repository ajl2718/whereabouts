insert into trigramphraseinverted3
with trigramphrase_chunk as (
    select trigramphrase, addr_ids, frequency 
    from trigramphraseinverted2
    where row_num % 100 = ?
)
select trigramphrase, flatten(array_agg(addr_ids)), sum(frequency) frequency
from trigramphrase_chunk
group by trigramphrase