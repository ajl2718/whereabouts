create table addrtext_with_tokens as
select *, regexp_replace(addr, '[A-Z]+', '') numeric_token
from addrtext limit 5;