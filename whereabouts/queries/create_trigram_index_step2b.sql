insert into trigramphraseinverted
with trigramphrase_chunk as (
    select addr_ids, 
    concat(str_split(t1.tokenphrase, ' ')[1][t2.col0:t2.col0+2], ' ', str_split(t1.tokenphrase, ' ')[2][t3.col0:t3.col0+2]) trigramphrase,
    frequency
    from phraseinverted_with_nums t1, numbers t2, numbers t3
    where row_num % 100 = ?
)
select cast(hash(trigramphrase) % 1000000000 as integer) trigramphrase, addr_ids, frequency -- use hashing to reduce the number of trigrams
from trigramphrase_chunk
where length(trigramphrase) >= 5