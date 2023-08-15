create table phraseinverted_with_nums as 
select tokenphrase, addr_ids, frequency, row_number() over () row_num
from phraseinverted